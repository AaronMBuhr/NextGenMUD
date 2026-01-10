import asyncio
from .command_handler_interface import CommandHandlerInterface
from .communication import Connection
from .structured_logger import StructuredLogger
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
import threading
from .nondb_models.character_interface import PermanentCharacterFlags
from .nondb_models.actor_interface import ActorType
from .nondb_models.actors import Actor
from .nondb_models.triggers import TriggerTimerTick
import time
from .constants import Constants
import logging
from .core_actions_interface import CoreActionsInterface
import signal
import sys


class MainProcess:
    _game_state: ComprehensiveGameState = live_game_state

    _shutdown_flag = False
    
    @classmethod
    def start_main_process(cls):
        logger = StructuredLogger(__name__, prefix="start_main_process()> ")
        # seems to do nothing:
        # logger.setLevel(logging.WARNING)
        logger.set_detail_level(1)  # Set to debug level 1
        # logger.debug(f"logging level set to {logger.getEffectiveLevel()}")
        cls._shutdown_flag = False
        
        # Intercept SIGINT (Ctrl+C) to set shutdown flags BEFORE Uvicorn closes connections.
        # This ensures handle_disconnect sees shutting_down=True and skips linkdead timer.
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        def signal_handler(signum, frame):
            logger.info("Received shutdown signal (SIGINT). Setting game state shutdown flags.")
            
            # Set the flags immediately so handle_disconnect knows to skip linkdead
            cls.shutdown()
            
            # Call the original handler so Uvicorn/Django can shut down gracefully
            if callable(original_sigint_handler):
                original_sigint_handler(signum, frame)
            elif original_sigint_handler == signal.SIG_DFL:
                sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        
        main_process_thread = threading.Thread(target=cls.run_main_game_loop, daemon=True)
        main_process_thread.start()
    
    @classmethod
    def shutdown(cls):
        """Signal the main game loop to stop."""
        cls._shutdown_flag = True
        cls._game_state.shutting_down = True

    @classmethod
    def run_main_game_loop(cls):
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
        logger = StructuredLogger(__name__, prefix="main_game_loop()> ")
        logger.debug3("Game loop started")
        last_fighting_tick = cls._game_state.world_clock_tick
        last_linkdead_check_tick = cls._game_state.world_clock_tick
        # Check linkdead every ~5 seconds (10 ticks at 0.5s per tick)
        linkdead_check_interval = int(5 / Constants.GAME_TICK_SEC)
        
        while not cls._shutdown_flag:
            logger.debug3(f"tick {cls._game_state.world_clock_tick}")
            start_tick_time = time.time()
            # Process input queues
            for conn in cls._game_state.connections:
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
                await trig.run(trig.actor_, "", {}, cls._game_state)

            # Process command queues for non-busy characters (NPCs and PCs)
            # This gives natural reaction timing (~0.5s per tick)
            # PCs use this for system-queued commands like walkto; direct input goes through input_queue
            # Instant commands are processed immediately without waiting for a tick
            from .command_handler import CommandHandler
            for ref_id, actor in list(Actor.references_.items()):
                if actor.actor_type == ActorType.CHARACTER and actor.command_queue:
                    if not actor.is_busy(cls._game_state.world_clock_tick):
                        # Process commands - instant commands are processed immediately,
                        # non-instant commands wait for next tick
                        await CommandHandler.process_command_queue(actor, cls._game_state)

            # Handle fighting ticks
            if cls._game_state.world_clock_tick > last_fighting_tick + Constants.TICKS_PER_ROUND:
                logger.debug3("fighting tick")
                if len(cls._game_state.characters_fighting) > 0:
                    await cls.handle_periodic_fighting_tick()
                last_fighting_tick = cls._game_state.world_clock_tick

            # Check linkdead timeouts periodically
            if cls._game_state.world_clock_tick > last_linkdead_check_tick + linkdead_check_interval:
                await cls._game_state.check_linkdead_timeouts()
                last_linkdead_check_tick = cls._game_state.world_clock_tick

            # Regenerate mana/stamina for all characters
            for ref_id, actor in Actor.references_.items():
                if actor.actor_type == ActorType.CHARACTER:
                    resources_changed = actor.regenerate_resources()
                    # Send status update to PCs when their resources change
                    if resources_changed and actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                        await actor.send_status_update()

            # Process scheduled actions and check aggressive NPCs
            await cls._game_state.perform_scheduled_events(cls._game_state.world_clock_tick)
            await cls.check_aggressive_near_players()

            # Sleep for remaining tick time (use asyncio.sleep for better signal handling)
            time_taken = time.time() - start_tick_time
            sleep_time = Constants.GAME_TICK_SEC - time_taken
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            cls._game_state.world_clock_tick += 1


    @classmethod
    async def handle_periodic_fighting_tick(cls):
        logger = StructuredLogger(__name__, prefix="handle_periodic_fighting_tick()> ")
        logger.debug3("handling periodic fighting tick")
        # logger.set_detail_level(1)
        # logger.debug3("handling periodic fighting tick")
        await CoreActionsInterface.get_instance().process_fighting()


    @classmethod
    async def process_input(cls, conn: Connection, input: str):
        logger = StructuredLogger(__name__, prefix="processInput()> ")
        logger.debug3(f"processing input for character {conn.character.name}: {input}")
        # command = input.split(" ")[0]
        # if not command in command_handlers:
        #     conn.send("dynamic", "Unknown command")
        # else:
        #     try:
        #         await command_handlers[command](conn.character, input)
        #     except KeyError:
        #         logger.error(f"KeyError processing command {command}")
        #         conn.send("dynamic", "Command failure.")
        await CommandHandlerInterface.get_instance().process_command(conn.character, input)

    @classmethod
    async def check_aggressive_near_players(cls):
        logger = StructuredLogger(__name__, prefix="check_aggressive_near_players()> ")
        logger.debug3("checking aggressive near players")
        for p in cls._game_state.players:
            logger.debug3(f"checking player {p.name}")
            if p.location_room != None:
                for char in p.location_room.get_characters():
                    if char != p and char.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE) \
                        and char.fighting_whom == None and cls._game_state.can_see(char, p):
                        logger.debug3(f"aggressive char {char.name} sees player {p.name}")
                        await CoreActionsInterface.get_instance().do_aggro(char)
        logger.debug3("done checking aggressive near players")