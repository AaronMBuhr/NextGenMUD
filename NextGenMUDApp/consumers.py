from channels.generic.websocket import AsyncWebsocketConsumer
from collections import deque
from custom_detail_logger import CustomDetailLogger
import json
from . import state_handler

# class MyWebsocketConsumerStateHandlerInterface:
#     @classmethod
#     async def start_connection(self, consumer: 'MyWebsocketConsumer'):
#         pass

#     @classmethod
#     def remove_character(self, connection: 'Connection'):
#         pass

class MyWebsocketConsumer(AsyncWebsocketConsumer):

    game_state = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .comprehensive_game_state import ComprehensiveGameState, live_game_state
        MyWebsocketConsumer.game_state = live_game_state 
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
        await MyWebsocketConsumer.game_state.start_connection(self)
        logger.debug("character loaded")

    async def disconnect(self, close_code):
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.disconnect()> ")
        logger.debug("disconnecting and removing character")
        await MyWebsocketConsumer.game_state.remove_character(self)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.receive()> ")
        logger.debug3(f"message: {message}")
        self.input_queue_.append(message)


    async def send(self, text_data):
        logger = CustomDetailLogger(__name__, prefix="MyWebsocketConsumer.send()> ")
        logger.warning(f"text_data: {text_data}")
        await super().send(text_data=text_data)
        # await self.send(text_data=json.dumps({ 
        #     'text_type': 'static',
        #     'text': 'Hello World!'
        # }))

    #     # await self.send(text_data=json.dumps({
    #     #     'text_type': 'dynamic',
    #     #     'text': 'received'
    #     # }))
