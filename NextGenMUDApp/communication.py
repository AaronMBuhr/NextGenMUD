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
        # raise Exception("Connection.send() #1")
        logger = StructuredLogger(__name__, prefix="Connection.send()> ")
        if isinstance(text_type, CommTypes):
            text_type = text_type.text
        logger.debug3(f"text_type: {text_type}")
        logger.debug3(f"text_data: {text_data}")
        # Ensure writes are serialized to avoid overlapping writes on Windows Proactor loop
        if not hasattr(self.consumer_, "_send_lock"):
            import asyncio
            self.consumer_._send_lock = asyncio.Lock()
        async with self.consumer_._send_lock:
            await self.consumer_.send(text_data=json.dumps({
                'text_type': text_type,
                'text': text_data
            }))
            import asyncio
            await asyncio.sleep(0)  # yield control to allow write completion

