import asyncio
from .command_handler import CommandHandler
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
import threading
from .nondb_models.triggers import TriggerTimerTick
import time
from .constants import Constants
import logging
from .core_actions import CoreActions


class MainProcess:
    game_state_: ComprehensiveGameState = live_game_state

    @classmethod
    def start_main_process(cls):
        logger = CustomDetailLogger(__name__, prefix="start_main_process()> ")
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
        logger = CustomDetailLogger(__name__, prefix="main_game_loop()> ")
        logger.debug3("Game loop started")
        last_fighting_tick = time.time()
        while True:
            start_tick_time = time.time()
            for conn in cls.game_state_.connections_:
                logger.debug3("processing input queue")
                if len(conn.input_queue) > 0:
                    input = conn.input_queue.popleft()
                    logger.debug3(f"input: {input}")
                    await cls.process_input(conn, input)
            for trig in TriggerTimerTick.timer_tick_triggers_: 
                logger.debug3(f"running timer tick trigger for {trig.actor_.rid} ({trig.actor_.id_}))")
                # print(trig.actor_.rid)
                # print(trig.actor_)
                await trig.run(trig.actor_, "", {})
            if time.time() > last_fighting_tick + (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND):
                logger.debug3("fighting tick")
                last_fighting_tick = time.time()
                await cls.handle_periodic_fighting_tick()
            # logger.debug3("sleeping")
            time_taken = time.time() - start_tick_time
            sleep_time = Constants.GAME_TICK_SEC - time_taken
            if sleep_time > 0:
                time.sleep(sleep_time)
            # TODO:H: hit point recovery
            cls.game_state_.world_clock_tick_ += 1


    @classmethod
    async def handle_periodic_fighting_tick(cls):
        logger = CustomDetailLogger(__name__, prefix="handle_periodic_fighting_tick()> ")
        logger.debug3("handling periodic fighting tick")
        # logger.set_detail_level(1)
        # logger.debug3("handling periodic fighting tick")
        await CoreActions.process_fighting()


    @classmethod
    async def process_input(cls, conn: Connection, input: str):
        logger = CustomDetailLogger(__name__, prefix="processInput()> ")
        logger.debug3(f"processing input for character {conn.character.name_}: {input}")
        # command = input.split(" ")[0]
        # if not command in command_handlers:
        #     conn.send("dynamic", "Unknown command")
        # else:
        #     try:
        #         await command_handlers[command](conn.character, input)
        #     except KeyError:
        #         logger.error(f"KeyError processing command {command}")
        #         conn.send("dynamic", "Command failure.")
        await CommandHandler.process_command(conn.character, input)
