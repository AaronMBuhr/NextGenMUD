from .actions import world_move, do_single_attack
import asyncio
from .command_handler import process_command
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
from .operating_state import operating_state
import threading
from .nondb_models.triggers import TriggerTimerTick
import time
from .constants import Constants
from .actions import process_fighting
import logging


def start_main_process():
    logger = CustomDetailLogger(__name__, prefix="start_main_process()> ")
    # seems to do nothing:
    # logger.setLevel(logging.WARNING)
    # logger.set_detail_level(3)
    # logger.debug(f"logging level set to {logger.getEffectiveLevel()}")
    main_process_thread = threading.Thread(target=run_main_game_loop)
    main_process_thread.start()

def run_main_game_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_game_loop())
    loop.close()

async def main_game_loop():
    logger = CustomDetailLogger(__name__, prefix="main_game_loop()> ")
    logger.debug3("Game loop started")
    last_fighting_tick = time.time()
    while True:
        for conn in operating_state.connections_:
            logger.debug3("processing input queue")
            if len(conn.input_queue) > 0:
                input = conn.input_queue.popleft()
                logger.debug3(f"input: {input}")
                await process_input(conn, input)
        for trig in TriggerTimerTick.timer_tick_triggers_: 
            logger.debug3(f"running timer tick trigger for {trig.actor_.rid} ({trig.actor_.id_}))")
            # print(trig.actor_.rid)
            # print(trig.actor_)
            await trig.run(trig.actor_, "", {})
        if time.time() > last_fighting_tick + (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND):
            # logger.debug3("fighting tick")
            last_fighting_tick = time.time()
            handle_periodic_fighting_tick()
        # logger.debug3("sleeping")
        time.sleep(Constants.GAME_TICK_SEC)



async def handle_periodic_fighting_tick():
    logger = CustomDetailLogger(__name__, prefix="handle_periodic_fighting_tick()> ")
    # logger.set_detail_level(1)
    # logger.debug3("handling periodic fighting tick")
    process_fighting()

async def process_input(conn: Connection, input: str):
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
    await process_command(conn.character, input)
