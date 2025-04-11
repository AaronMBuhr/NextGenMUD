import asyncio
from .command_handler_interface import CommandHandlerInterface
from .communication import Connection
from .structured_logger import StructuredLogger
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
import threading
from .nondb_models.character_interface import PermanentCharacterFlags
from .nondb_models.triggers import TriggerTimerTick
import time
from .constants import Constants
import logging
from .core_actions_interface import CoreActionsInterface


class MainProcess:
    _game_state: ComprehensiveGameState = live_game_state

    @classmethod
    def start_main_process(cls):
        logger = StructuredLogger(__name__, prefix="start_main_process()> ")
        # seems to do nothing:
        # logger.setLevel(logging.WARNING)
        # logger.set_detail_level(3)
        # logger.debug(f"logging level set to {logger.getEffectiveLevel()}")
        main_process_thread = threading.Thread(target=cls.run_main_game_loop)
        main_process_thread.start()

    @classmethod
    def run_main_game_loop(cls):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cls.main_game_loop())
        loop.close()
    

    @classmethod
    async def main_game_loop(cls):
        logger = StructuredLogger(__name__, prefix="main_game_loop()> ")
        logger.debug3("Game loop started")
        last_fighting_tick = cls._game_state.world_clock_tick
        while True:
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
            for trig in TriggerTimerTick.timer_tick_triggers_: 
                logger.debug3(f"running timer tick trigger for {trig.actor_.rid} ({trig.actor_.id}))")
                await trig.run(trig.actor_, "", {}, cls._game_state)

            # Handle fighting ticks
            if cls._game_state.world_clock_tick > last_fighting_tick + Constants.TICKS_PER_ROUND:
                logger.debug3("fighting tick")
                if len(cls._game_state.characters_fighting) > 0:
                    await cls.handle_periodic_fighting_tick()
                last_fighting_tick = cls._game_state.world_clock_tick

            # Process scheduled actions and check aggressive NPCs
            cls._game_state.perform_scheduled_actions(cls._game_state.world_clock_tick)
            await cls.check_aggressive_near_players()

            # Sleep for remaining tick time
            time_taken = time.time() - start_tick_time
            sleep_time = Constants.GAME_TICK_SEC - time_taken
            if sleep_time > 0:
                time.sleep(sleep_time)
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
            for char in p.location_room.get_characters():
                if char != p and char.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE) \
                    and char.fighting_whom == None and cls._game_state.can_see(char, p):
                    logger.critical(f"aggressive char {char.name} sees player {p.name}")
                    await CoreActionsInterface.get_instance().do_aggro(char)
        logger.debug3("done checking aggressive near players")