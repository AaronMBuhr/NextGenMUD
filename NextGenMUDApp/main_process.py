from .actions import worldMove
import asyncio
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
from .operating_state import operating_state
import threading
import time


def startMainProcess():
    print("Starting main game loop")
    main_process_thread = threading.Thread(target=run_main_game_loop)
    main_process_thread.start()

def run_main_game_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(mainGameLoop())
    loop.close()

async def mainGameLoop():
    logger = CustomDetailLogger(__name__, prefix="mainGameLoop()> ")
    print("Game loop started")
    while True:
        for conn in operating_state.connections_:
            logger.debug("processing input queue")
            if len(conn.input_queue) > 0:
                input = conn.input_queue.popleft()
                logger.debug(f"input: {input}")
                await processInput(conn, input)
        logger.debug("sleeping")
        time.sleep(2)


command_handlers = {
    "north": lambda conn, input: worldMove(conn.character, "north"),
    "south": lambda conn, input: worldMove(conn.character, "south"),
    "east": lambda conn, input: worldMove(conn.character, "east"),
    "west": lambda conn, input: worldMove(conn.character, "west"),
}

async def processInput(conn: Connection, input: str):
    logger = CustomDetailLogger(__name__, prefix="processInput()> ")
    print(f"processing input for character {conn.character.name_}: {input}")
    try:
        await command_handlers[input](conn, input)
    except KeyError:
        conn.send("dynamic", "Unknown command")
