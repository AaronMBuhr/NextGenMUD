from channels.generic.websocket import AsyncWebsocketConsumer
from collections import deque
from .structured_logger import StructuredLogger
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
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.connect()> ")
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
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.disconnect()> ")
        logger.debug("disconnecting and removing character")
        try:
            if MyWebsocketConsumer.game_state is not None:
                MyWebsocketConsumer.game_state.remove_connection(self)
            # Clear the input queue
            self.input_queue_.clear()
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
        finally:
            # Ensure parent class disconnect is called
            await super().disconnect(close_code)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.receive()> ")
        logger.debug3(f"message: {message}")
        self.input_queue_.append(message)


    async def send(self, text_data):
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.send()> ")
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
