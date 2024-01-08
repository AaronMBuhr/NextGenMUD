from channels.generic.websocket import AsyncWebsocketConsumer
from collections import deque
from custom_detail_logger import CustomDetailLogger
import json
from . import state_handler

class MyWebsocketConsumer(AsyncWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_queue_ = deque()

    @property
    def input_queue(self):
        return self.input_queue_
    
    async def connect(self):
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.connect()> ")
        logger.debug("accepting connection")
        await self.accept()
        logger.debug("connection accepted, loading character")
        await self.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Incoming connection'
        }))
        await state_handler.start_connection(self)
        logger.debug("character loaded")

    async def disconnect(self, close_code):
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.disconnect()> ")
        logger.debug("disconnecting and removing character")
        state_handler.remove_character(self)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.receive()> ")
        logger.debug(f"message: {message}")
        self.input_queue_.append(message)


    # def send(self, text_data):
    #     super().send(text_data=text_data)
    #     # await self.send(text_data=json.dumps({ 
    #     #     'text_type': 'static',
    #     #     'text': 'Hello World!'
    #     # }))

    #     # await self.send(text_data=json.dumps({
    #     #     'text_type': 'dynamic',
    #     #     'text': 'received'
    #     # }))
