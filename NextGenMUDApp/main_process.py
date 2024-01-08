from .actions import worldMove
import asyncio
from .command_handlers import command_handlers
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
from .operating_state import operating_state
import threading
import time


def start_main_process():
    print("Starting main game loop")
    main_process_thread = threading.Thread(target=run_main_game_loop)
    main_process_thread.start()

def run_main_game_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_game_loop())
    loop.close()

async def main_game_loop():
    logger = CustomDetailLogger(__name__, prefix="mainGameLoop()> ")
    print("Game loop started")
    while True:
        for conn in operating_state.connections_:
            logger.debug("processing input queue")
            if len(conn.input_queue) > 0:
                input = conn.input_queue.popleft()
                logger.debug(f"input: {input}")
                await process_input(conn, input)
        logger.debug("sleeping")
        time.sleep(2)


async def process_input(conn: Connection, input: str):
    logger = CustomDetailLogger(__name__, prefix="processInput()> ")
    print(f"processing input for character {conn.character.name_}: {input}")
    command = input.split(" ")[0]
    if not command in command_handlers:
        conn.send("dynamic", "Unknown command")
    else:
        try:
            await command_handlers[command](conn.character, input)
        except KeyError:
            logger.error(f"KeyError processing command {command}")
            conn.send("dynamic", "Command failure.")
