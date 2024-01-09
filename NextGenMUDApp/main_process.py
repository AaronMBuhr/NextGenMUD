from .actions import world_move
import asyncio
from .command_handler import process_command
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
from .operating_state import operating_state
import threading
from .nondb_models.triggers import TriggerTimerTick
import time

TICK_SEC = 2

def start_main_process():
    logger = CustomDetailLogger(__name__, prefix="start_main_process()> ")
    main_process_thread = threading.Thread(target=run_main_game_loop)
    main_process_thread.start()

def run_main_game_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_game_loop())
    loop.close()

async def main_game_loop():
    logger = CustomDetailLogger(__name__, prefix="main_game_loop()> ")
    logger.debug("Game loop started")
    while True:
        for conn in operating_state.connections_:
            logger.debug("processing input queue")
            if len(conn.input_queue) > 0:
                input = conn.input_queue.popleft()
                logger.debug(f"input: {input}")
                await process_input(conn, input)
        for trig in TriggerTimerTick.timer_tick_triggers_: 
            logger.debug(f"running timer tick trigger for {trig.actor_.rid}")
            await trig.run(trig.actor_, "", {})
        logger.debug("sleeping")
        time.sleep(TICK_SEC)


async def process_input(conn: Connection, input: str):
    logger = CustomDetailLogger(__name__, prefix="processInput()> ")
    logger.debug(f"processing input for character {conn.character.name_}: {input}")
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
