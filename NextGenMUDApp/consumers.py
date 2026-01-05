from channels.generic.websocket import AsyncWebsocketConsumer
from collections import deque
from enum import Enum, auto
from .structured_logger import StructuredLogger
import json
from . import state_handler


class LoginState(Enum):
    """States for the login state machine."""
    AWAITING_NAME = auto()
    AWAITING_PASSWORD = auto()
    AWAITING_NEW_PASSWORD = auto()
    AWAITING_PASSWORD_CONFIRM = auto()
    LOGGED_IN = auto()


class MyWebsocketConsumer(AsyncWebsocketConsumer):

    game_state = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .comprehensive_game_state import ComprehensiveGameState, live_game_state
        MyWebsocketConsumer.game_state = live_game_state 
        self.input_queue_ = deque()
        self.login_state = LoginState.AWAITING_NAME
        self.pending_character_name = None
        self.pending_password = None
        self.connection_obj = None  # Will hold the Connection object

    @property
    def input_queue(self):
        return self.input_queue_
    
    async def connect(self):
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.connect()> ")
        logger.debug("accepting connection")
        await self.accept()
        logger.debug("connection accepted, starting login flow")
        await self.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Welcome to NextGenMUD!'
        }))
        await self.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': ''
        }))
        await self.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Enter your character name:'
        }))

    async def disconnect(self, close_code):
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.disconnect()> ")
        logger.debug("disconnecting")
        try:
            if MyWebsocketConsumer.game_state is not None and self.login_state == LoginState.LOGGED_IN:
                # Only handle character disconnect if they were logged in
                await MyWebsocketConsumer.game_state.handle_disconnect(self)
            # Clear the input queue
            self.input_queue_.clear()
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Ensure parent class disconnect is called
            await super().disconnect(close_code)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.receive()> ")
        logger.debug3(f"message: {message}, login_state: {self.login_state}")
        
        # Handle login state machine
        if self.login_state != LoginState.LOGGED_IN:
            await self._handle_login_input(message)
        else:
            # Normal game input
            self.input_queue_.append(message)
    
    async def _handle_login_input(self, message: str):
        """Handle input during the login process."""
        from .player_save_manager import player_save_manager
        
        logger = StructuredLogger(__name__, prefix="_handle_login_input()> ")
        message = message.strip()
        
        if self.login_state == LoginState.AWAITING_NAME:
            if not message:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Please enter a character name:'
                }))
                return
                
            self.pending_character_name = message
            
            if player_save_manager.character_exists(message):
                # Existing character - ask for password
                self.login_state = LoginState.AWAITING_PASSWORD
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Password:'
                }))
            else:
                # New character - ask to create password
                self.login_state = LoginState.AWAITING_NEW_PASSWORD
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': f'Character "{message}" not found. Creating new character.'
                }))
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Enter a password for your new character:'
                }))
                
        elif self.login_state == LoginState.AWAITING_PASSWORD:
            if not message:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Please enter your password:'
                }))
                return
                
            if player_save_manager.verify_password(self.pending_character_name, message):
                # Password correct - complete login
                await self._complete_login()
            else:
                # Wrong password
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Incorrect password. Please try again:'
                }))
                
        elif self.login_state == LoginState.AWAITING_NEW_PASSWORD:
            if not message or len(message) < 4:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Password must be at least 4 characters. Try again:'
                }))
                return
                
            self.pending_password = message
            self.login_state = LoginState.AWAITING_PASSWORD_CONFIRM
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Confirm your password:'
            }))
            
        elif self.login_state == LoginState.AWAITING_PASSWORD_CONFIRM:
            if message != self.pending_password:
                self.pending_password = None
                self.login_state = LoginState.AWAITING_NEW_PASSWORD
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Passwords do not match. Enter a password for your new character:'
                }))
                return
            
            # Create new character save file
            if player_save_manager.create_new_character(self.pending_character_name, self.pending_password):
                await self._complete_login(is_new=True)
            else:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Error creating character. Please try a different name.'
                }))
                self.login_state = LoginState.AWAITING_NAME
                self.pending_character_name = None
                self.pending_password = None
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Enter your character name:'
                }))
    
    async def _complete_login(self, is_new: bool = False):
        """Complete the login process and load the character into the game."""
        logger = StructuredLogger(__name__, prefix="_complete_login()> ")
        
        try:
            self.login_state = LoginState.LOGGED_IN
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            
            if is_new:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': f'Welcome, {self.pending_character_name}! Your adventure begins...'
                }))
            else:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': f'Welcome back, {self.pending_character_name}!'
                }))
            
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            
            # Let the game state handle the rest
            await MyWebsocketConsumer.game_state.complete_login(
                self, 
                self.pending_character_name,
                is_new
            )
            
            # Clear pending data
            self.pending_password = None
            
        except Exception as e:
            logger.error(f"Error completing login: {e}")
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Error during login. Please reconnect.'
            }))

    async def send(self, text_data):
        logger = StructuredLogger(__name__, prefix="MyWebsocketConsumer.send()> ")
        # Call parent's send method directly to avoid the assertion error
        await AsyncWebsocketConsumer.send(self, text_data=text_data)
