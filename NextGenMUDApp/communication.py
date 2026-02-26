from .structured_logger import StructuredLogger
from enum import Enum
import json


class CommTypes(Enum):
    STATIC = (1, 'static')
    DYNAMIC = (2, 'dynamic')
    CLEARSTATIC = (3, 'clearstatic')
    CLEARDYNAMIC = (4, 'cleardynamic')
    STATUS = (5, 'status')  # For vital stats HUD - updates in place, doesn't scroll

    def __init__(self, num, text):
        self._num = num
        self._text = text

    @property
    def number(self):
        return self._num

    @property
    def text(self):
        return self._text


class Connection:
    def __init__(self, consumer, character=None):
        self.consumer_ = consumer
        self.character_ = character

    @property
    def input_queue(self): 
        return self.consumer_.input_queue

    @property
    def character(self):
        return self.character_
    
    @character.setter
    def character(self, value):
        self.character_ = value

    async def send(self, text_type, text_data: str):
        import asyncio
        logger = StructuredLogger(__name__, prefix="Connection.send()> ")
        if isinstance(text_type, CommTypes):
            text_type = text_type.text
        # Coerce to string so client never receives non-string text (avoids display corruption)
        text_data = str(text_data) if text_data is not None else ""
        logger.debug3(f"text_type: {text_type}")
        logger.debug3(f"text_data: {text_data}")

        payload = json.dumps({'text_type': text_type, 'text': text_data})

        async def _do_send():
            await self.consumer_.send(text_data=payload)
            await asyncio.sleep(0)

        # Serialize writes per-consumer. The lock may have been created in a
        # different event loop (game-loop thread vs Channels ASGI thread), so
        # catch that and recreate the lock for the current loop.
        if not hasattr(self.consumer_, "_send_lock"):
            self.consumer_._send_lock = asyncio.Lock()
        try:
            async with self.consumer_._send_lock:
                await _do_send()
        except RuntimeError as exc:
            if "different event loop" in str(exc):
                self.consumer_._send_lock = asyncio.Lock()
                async with self.consumer_._send_lock:
                    await _do_send()
            else:
                raise

