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
    AWAITING_CLASS_SELECTION = auto()
    AWAITING_STAT_ALLOCATION = auto()  # Allocating stats one at a time
    LOGGED_IN = auto()


# Stats for allocation, in order
STAT_ALLOCATION_ORDER = ['STRENGTH', 'DEXTERITY', 'CONSTITUTION', 'INTELLIGENCE', 'WISDOM', 'CHARISMA']
STAT_DESCRIPTIONS = {
    'STRENGTH': 'Melee damage and carrying capacity',
    'DEXTERITY': 'Reflex saves, hit chance, and agility',
    'CONSTITUTION': 'Fortitude saves and hit points',
    'INTELLIGENCE': 'Spell power for mages, knowledge skills',
    'WISDOM': 'Will saves, healing power, perception',
    'CHARISMA': 'Social interactions and leadership'
}
POINTS_PER_STAT = 10  # 10 points per stat = 60 total
MAX_STAT_AT_CREATION = 25
MIN_STAT_AT_CREATION = 1


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
        self.pending_class = None  # Selected class for new characters
        self.connection_obj = None  # Will hold the Connection object
        # Stat allocation tracking
        self.stat_allocation_index = 0  # Which stat we're currently allocating
        self.stat_points_remaining = 0  # Points left to allocate
        self.allocated_stats = {}  # Stats allocated so far

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
                # Password correct - check if this is a stub save (needs character creation)
                # or a fresh character (level 1, full skill points) for the welcome message
                is_stub = player_save_manager.is_stub_save(self.pending_character_name)
                is_fresh = player_save_manager.is_fresh_character(self.pending_character_name)
                if is_stub:
                    # Get the selected class from the save file
                    self.pending_class = player_save_manager.get_selected_class(self.pending_character_name)
                await self._complete_login(is_new=is_fresh)
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
            
            # Password confirmed - now ask for class selection
            self.login_state = LoginState.AWAITING_CLASS_SELECTION
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '=== Choose Your Class ==='
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '1. Fighter - A master of martial combat, strong and resilient.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '          High HP, stamina-based skills, melee specialist.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '2. Rogue   - A cunning trickster, quick and deadly.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '          Dual-wielding, stealth, high critical damage.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '3. Mage    - A wielder of arcane power, fragile but devastating.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '          Mana-based spells, elemental damage, crowd control.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '4. Cleric  - A divine servant, healer and protector.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': '          Healing spells, buffs, holy damage.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Enter the number or name of your class:'
            }))
            
        elif self.login_state == LoginState.AWAITING_CLASS_SELECTION:
            # Parse class selection
            selected_class = self._parse_class_selection(message)
            if not selected_class:
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': 'Invalid selection. Enter 1-4 or the class name (fighter, rogue, mage, cleric):'
                }))
                return
            
            self.pending_class = selected_class
            
            # Start stat allocation
            await self._start_stat_allocation()
        
        elif self.login_state == LoginState.AWAITING_STAT_ALLOCATION:
            await self._handle_stat_allocation(message)
    
    def _parse_class_selection(self, message: str) -> str:
        """Parse class selection input. Returns class name or None if invalid."""
        message = message.strip().lower()
        
        # Accept numbers 1-4
        if message == '1' or message == 'fighter':
            return 'fighter'
        elif message == '2' or message == 'rogue':
            return 'rogue'
        elif message == '3' or message == 'mage':
            return 'mage'
        elif message == '4' or message == 'cleric':
            return 'cleric'
        
        # Accept partial matches
        if 'fighter'.startswith(message) and len(message) >= 1:
            return 'fighter'
        elif 'rogue'.startswith(message) and len(message) >= 1:
            return 'rogue'
        elif 'mage'.startswith(message) and len(message) >= 1:
            return 'mage'
        elif 'cleric'.startswith(message) and len(message) >= 1:
            return 'cleric'
        
        return None

    async def _start_stat_allocation(self):
        """Begin the stat allocation process."""
        total_points = POINTS_PER_STAT * len(STAT_ALLOCATION_ORDER)
        self.stat_points_remaining = total_points
        self.stat_allocation_index = 0
        self.allocated_stats = {}
        
        # Show introduction (in static display area)
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': ''
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': '=== Character Attribute Allocation ==='
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': ''
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': f'You have {total_points} attribute points to distribute among your stats.'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': f'Each stat can be set between {MIN_STAT_AT_CREATION} and {MAX_STAT_AT_CREATION}.'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': ''
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': 'The stats you will allocate are:'
        }))
        
        # Show all stats with descriptions
        for stat_name in STAT_ALLOCATION_ORDER:
            desc = STAT_DESCRIPTIONS.get(stat_name, '')
            display_name = stat_name.replace('_', ' ').title()
            await self.send(text_data=json.dumps({
                'text_type': 'static',
                'text': f'  {display_name:15} - {desc}'
            }))
        
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': ''
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'static',
            'text': 'Tip: Enter "0" at any time to start over and reallocate your stats.'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': ''
        }))
        
        self.login_state = LoginState.AWAITING_STAT_ALLOCATION
        await self._prompt_for_next_stat()
    
    async def _prompt_for_next_stat(self):
        """Prompt for the next stat to allocate."""
        if self.stat_allocation_index >= len(STAT_ALLOCATION_ORDER):
            # All stats allocated, complete character creation
            await self._complete_stat_allocation()
            return
        
        stat_name = STAT_ALLOCATION_ORDER[self.stat_allocation_index]
        display_name = stat_name.replace('_', ' ').title()
        desc = STAT_DESCRIPTIONS.get(stat_name, '')
        
        # Calculate min/max based on remaining points and remaining stats
        remaining_stats = len(STAT_ALLOCATION_ORDER) - self.stat_allocation_index - 1
        # Must leave at least MIN_STAT_AT_CREATION for each remaining stat
        max_for_this = min(MAX_STAT_AT_CREATION, 
                          self.stat_points_remaining - (remaining_stats * MIN_STAT_AT_CREATION))
        # Must use at least enough to not exceed MAX for remaining stats
        min_for_this = max(MIN_STAT_AT_CREATION,
                          self.stat_points_remaining - (remaining_stats * MAX_STAT_AT_CREATION))
        
        # Ensure max is at least min (should never happen with proper point allocation, but safety check)
        if max_for_this < min_for_this:
            max_for_this = min_for_this
        
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': f'Points remaining: {self.stat_points_remaining}'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': f'{display_name} ({desc})'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': f'Enter a value between {min_for_this} and {max_for_this} (or "0" to start over):'
        }))
    
    async def _handle_stat_allocation(self, message: str):
        """Handle input during stat allocation."""
        from .player_save_manager import player_save_manager
        
        message = message.strip()
        
        # Check for "0" to start over
        if message == '0':
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Starting over...'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self._start_stat_allocation()
            return
        
        # Try to parse the number
        try:
            value = int(message)
        except ValueError:
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Please enter a number (or "0" to start over).'
            }))
            await self._prompt_for_next_stat()
            return
        
        stat_name = STAT_ALLOCATION_ORDER[self.stat_allocation_index]
        remaining_stats = len(STAT_ALLOCATION_ORDER) - self.stat_allocation_index - 1
        
        # Calculate valid range
        max_for_this = min(MAX_STAT_AT_CREATION, 
                          self.stat_points_remaining - (remaining_stats * MIN_STAT_AT_CREATION))
        min_for_this = max(MIN_STAT_AT_CREATION,
                          self.stat_points_remaining - (remaining_stats * MAX_STAT_AT_CREATION))
        
        # Ensure max is at least min (should never happen with proper point allocation, but safety check)
        if max_for_this < min_for_this:
            max_for_this = min_for_this
        
        if value < min_for_this or value > max_for_this:
            if remaining_stats > 0:
                reason = f' (must reserve {remaining_stats * MIN_STAT_AT_CREATION} point{"s" if remaining_stats * MIN_STAT_AT_CREATION != 1 else ""} for remaining stat{"s" if remaining_stats > 1 else ""})'
            else:
                reason = ''
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': f'Value must be between {min_for_this} and {max_for_this}.{reason}'
            }))
            await self._prompt_for_next_stat()
            return
        
        # Accept the value
        self.allocated_stats[stat_name] = value
        self.stat_points_remaining -= value
        self.stat_allocation_index += 1
        
        display_name = stat_name.replace('_', ' ').title()
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': f'{display_name} set to {value}.'
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': ''
        }))
        
        # Prompt for next stat or complete
        await self._prompt_for_next_stat()
    
    async def _complete_stat_allocation(self):
        """Complete stat allocation and create the character."""
        from .player_save_manager import player_save_manager
        
        # Validate that all points have been used
        total_points = POINTS_PER_STAT * len(STAT_ALLOCATION_ORDER)
        if self.stat_points_remaining > 0:
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': f'Error: You have {self.stat_points_remaining} point{"s" if self.stat_points_remaining > 1 else ""} remaining out of {total_points} total points.'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'You must use all available points. Starting over...'
            }))
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': ''
            }))
            await self._start_stat_allocation()
            return
        
        # Show summary
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': ''
        }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': '=== Final Attributes ==='
        }))
        for stat_name in STAT_ALLOCATION_ORDER:
            display_name = stat_name.replace('_', ' ').title()
            value = self.allocated_stats.get(stat_name, 10)
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': f'  {display_name}: {value}'
            }))
        await self.send(text_data=json.dumps({
            'text_type': 'dynamic',
            'text': ''
        }))
        
        # Create new character save file with selected class and stats
        if player_save_manager.create_new_character(
            self.pending_character_name, 
            self.pending_password,
            selected_class=self.pending_class,
            allocated_stats=self.allocated_stats
        ):
            await self._complete_login(is_new=True)
        else:
            await self.send(text_data=json.dumps({
                'text_type': 'dynamic',
                'text': 'Error creating character. Please try a different name.'
            }))
            self.login_state = LoginState.AWAITING_NAME
            self.pending_character_name = None
            self.pending_password = None
            self.pending_class = None
            self.allocated_stats = {}
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
                class_display = self.pending_class.title() if self.pending_class else "Adventurer"
                await self.send(text_data=json.dumps({
                    'text_type': 'dynamic',
                    'text': f'Welcome, {self.pending_character_name} the {class_display}! Your adventure begins...'
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
                is_new,
                selected_class=self.pending_class
            )
            
            # Clear pending data
            self.pending_password = None
            self.pending_class = None
            
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
