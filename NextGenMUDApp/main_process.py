import asyncio
from .communication import Connection
from .structured_logger import StructuredLogger
import threading
import time
from .constants import Constants
import logging
import signal
import sys

# NOTE: Heavy game imports (Actor, CoreActionsInterface, etc.) have been moved
# inside methods to prevent blocking the main thread during server startup.


class MainProcess:
    """Game loop and process control. live_game_state is loaded lazily to avoid blocking main thread on import."""

    _shutdown_flag = False

    @classmethod
    def _get_game_state(cls):
        from .comprehensive_game_state import live_game_state
        return live_game_state

    @classmethod
    def register_signal_handler(cls):
        """Register SIGINT handler. Must be called from the main thread (e.g. in AppConfig.ready())."""
        logger = StructuredLogger(__name__, prefix="register_signal_handler()> ")
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        def signal_handler(signum, frame):
            logger.info("Received shutdown signal (SIGINT). Setting game state shutdown flags.")
            cls.shutdown()
            if callable(original_sigint_handler):
                original_sigint_handler(signum, frame)
            elif original_sigint_handler == signal.SIG_DFL:
                sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

    @classmethod
    def start_main_process(cls):
        """Start the main game loop thread. Call after world is loaded (e.g. from loader thread)."""
        logger = StructuredLogger(__name__, prefix="start_main_process()> ")
        logger.set_detail_level(1)  # Set to debug level 1
        cls._shutdown_flag = False

        main_process_thread = threading.Thread(target=cls.run_main_game_loop, daemon=True)
        main_process_thread.start()
    
    @classmethod
    def shutdown(cls):
        """Signal the main game loop to stop."""
        cls._shutdown_flag = True
        cls._get_game_state().shutting_down = True

    @classmethod
    def run_main_game_loop(cls):
        # Lazy imports: load heavy dependencies only when the loop thread starts
        from .core_actions_interface import CoreActionsInterface
        from .nondb_models.triggers import TriggerTimerTick
        from .nondb_models.actors import Actor
        from .nondb_models.actor_interface import ActorType
        from .nondb_models.character_interface import PermanentCharacterFlags
        from .command_handler_interface import CommandHandlerInterface
        from .command_handler import CommandHandler

        # On Windows, use SelectorEventLoopPolicy to avoid Proactor overlaps issues
        try:
            policy = asyncio.WindowsSelectorEventLoopPolicy()
            asyncio.set_event_loop_policy(policy)
        except AttributeError:
            pass  # Not on Windows or policy unavailable
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Add custom exception handler to capture and log asyncio callback exceptions at debug3 level
        def handle_asyncio_exception(loop, context):
            logger = StructuredLogger(__name__, prefix="asyncio_exception_handler()> ")
            msg = context.get("message", "")
            exc = context.get("exception")
            # Deduplicate identical errors: skip if same message and exception repr
            key = (msg, repr(exc))
            if getattr(handle_asyncio_exception, "last_key", None) == key:
                return
            handle_asyncio_exception.last_key = key
            logger.debug3(f"Asyncio exception in callback: {msg}")
            if exc:
                logger.debug3(f"Exception details: {exc}")
        loop.set_exception_handler(handle_asyncio_exception)
        
        try:
            loop.run_until_complete(cls.main_game_loop())
        except asyncio.CancelledError:
            pass  # Expected on shutdown
        finally:
            loop.close()
    

    @classmethod
    async def main_game_loop(cls):
        from .nondb_models.triggers import TriggerTimerTick
        from .nondb_models.actors import Actor
        from .nondb_models.actor_interface import ActorType
        from .nondb_models.character_interface import PermanentCharacterFlags
        from .command_handler import CommandHandler
        from .command_handler_interface import CommandHandlerInterface

        logger = StructuredLogger(__name__, prefix="main_game_loop()> ")
        logger.debug3("Game loop started")
        gs = cls._get_game_state()
        last_fighting_tick = gs.world_clock_tick
        last_linkdead_check_tick = gs.world_clock_tick
        # Check linkdead every ~5 seconds (10 ticks at 0.5s per tick)
        linkdead_check_interval = int(5 / Constants.GAME_TICK_SEC)
        
        while not cls._shutdown_flag:
            logger.debug3(f"tick {gs.world_clock_tick}")
            start_tick_time = time.time()
            # Process input queues
            for conn in gs.connections:
                logger.debug3("processing input queue")
                if len(conn.input_queue) > 0:
                    input = conn.input_queue.popleft()
                    logger.debug3(f"input: {input}")
                    await cls.process_input(conn, input)
            
            # Process timer tick triggers
            triggers_to_run = list(TriggerTimerTick.timer_tick_triggers_)
            for trig in triggers_to_run: 
                if trig.actor_ == None:
                    logger.warning(f"timer tick trigger for {trig.event_type} ({trig.event_type.name}) is None")
                    continue
                # Skip triggers on definitions (no reference_number means it's not an instance)
                if not trig.actor_.reference_number:
                    TriggerTimerTick.timer_tick_triggers_.discard(trig)
                    continue
                logger.debug3(f"running timer tick trigger for {trig.actor_.rid} ({trig.actor_.id}))")
                await trig.run(trig.actor_, "", {}, gs)

            # Process command queues for non-busy characters (NPCs and PCs)
            # This gives natural reaction timing (~0.5s per tick)
            # PCs use this for system-queued commands like walkto; direct input goes through input_queue
            # Instant commands are processed immediately without waiting for a tick
            for ref_id, actor in list(Actor.references_.items()):
                if actor.actor_type == ActorType.CHARACTER and actor.command_queue:
                    if not actor.is_busy(gs.world_clock_tick):
                        # Process commands - instant commands are processed immediately,
                        # non-instant commands wait for next tick
                        await CommandHandler.process_command_queue(actor, gs)

            # Handle fighting ticks
            if gs.world_clock_tick > last_fighting_tick + Constants.TICKS_PER_ROUND:
                logger.debug3("fighting tick")
                if len(gs.characters_fighting) > 0:
                    await cls.handle_periodic_fighting_tick()
                last_fighting_tick = gs.world_clock_tick

            # Check linkdead timeouts periodically
            if gs.world_clock_tick > last_linkdead_check_tick + linkdead_check_interval:
                await gs.check_linkdead_timeouts()
                last_linkdead_check_tick = gs.world_clock_tick

            # Regenerate mana/stamina for all characters
            for ref_id, actor in Actor.references_.items():
                if actor.actor_type == ActorType.CHARACTER:
                    resources_changed = actor.regenerate_resources()
                    # Send status update to PCs when their resources change
                    if resources_changed and actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                        await actor.send_status_update()

            # Process scheduled actions and check aggressive NPCs
            await gs.perform_scheduled_events(gs.world_clock_tick)
            await cls.check_aggressive_near_players()

            # Sleep for remaining tick time (use asyncio.sleep for better signal handling)
            time_taken = time.time() - start_tick_time
            sleep_time = Constants.GAME_TICK_SEC - time_taken
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            gs.world_clock_tick += 1


    @classmethod
    async def handle_periodic_fighting_tick(cls):
        from .core_actions_interface import CoreActionsInterface
        logger = StructuredLogger(__name__, prefix="handle_periodic_fighting_tick()> ")
        logger.debug3("handling periodic fighting tick")
        await CoreActionsInterface.get_instance().process_fighting()


    @classmethod
    async def process_input(cls, conn: Connection, input: str):
        from .command_handler_interface import CommandHandlerInterface
        logger = StructuredLogger(__name__, prefix="processInput()> ")
        logger.debug3(f"processing input for character {conn.character.name}: {input}")
        await CommandHandlerInterface.get_instance().process_command(conn.character, input)

    @classmethod
    async def check_aggressive_near_players(cls):
        from .nondb_models.character_interface import PermanentCharacterFlags
        from .core_actions_interface import CoreActionsInterface
        logger = StructuredLogger(__name__, prefix="check_aggressive_near_players()> ")
        logger.debug3("checking aggressive near players")
        for p in cls._get_game_state().players:
            logger.debug3(f"checking player {p.name}")
            if p.location_room != None:
                for char in p.location_room.get_characters():
                    if char != p and not char.has_perm_flags(PermanentCharacterFlags.IS_PC) \
                        and char.fighting_whom is None:
                        await CoreActionsInterface.get_instance().do_aggro(char)
        logger.debug3("done checking aggressive near players")