from abc import abstractmethod
from collections import defaultdict
import copy
from ..structured_logger import StructuredLogger
from enum import Enum, auto, IntFlag
import json
import random
from typing import Dict, List, TYPE_CHECKING
from .actor_interface import ActorInterface, ActorType, ActorSpawnData
from ..basic_types import DescriptiveFlags
from ..communication import CommTypes
from .object_interface import ObjectInterface
from .trigger_interface import TriggerType
from ..utility import replace_vars, get_dice_parts, roll_dice, article_plus_name, set_vars, evaluate_functions_in_line
from ..command_handler_interface import CommandHandlerInterface
if TYPE_CHECKING:
    from .actor_states import ActorState, Cooldown
from .character_interface import TemporaryCharacterFlags
from ..constants import Constants as CONSTANTS


class Actor(ActorInterface):
    references_ = {}  # Class variable for storing references
    current_reference_num_ = 1  # Class variable for tracking the current reference number

    def __init__(self, actor_type: ActorType, id: str, name: str = "", create_reference=False):
        self.actor_type = actor_type
        self.id = id
        self.name = name
        self.article = "" if name == "" else "a" if name[0].lower() in "aeiou" else "an" if name else ""
        self.pronoun_subject = "it"
        self.pronoun_object = "it"
        self.pronoun_possessive = "its"
        self.triggers_by_type = defaultdict(list)
        self.reference_number = None
        self.temp_variables = {}
        self.perm_variables = {}
        self.spawned_from: ActorSpawnData = None
        self.spawned: List[Actor] = []
        self.is_deleted = False
        self.states: List["ActorState"] = []
        self.cooldowns: List["Cooldown"] = []
        self.recovers_at = 0
        self.recovery_ticks = CONSTANTS.RECOVERY_TICKS
        self.command_queue: List[str] = []
        if create_reference:
            self.create_reference()

    def create_reference(self) -> str:
        logger = StructuredLogger(__name__, prefix="Actor.create_reference()> ")
        logger.debug3(f"creating reference for {self.name} ({self.id})")
        reference_prefix = self.actor_type.name[0]  # First character of ActorType
        self.reference_number = reference_prefix + str(Actor.current_reference_num_)
        Actor.references_[self.reference_number] = self
        Actor.current_reference_num_ += 1
        return self.reference_number

    @classmethod
    def references(self):
        return Actor.references_
    
    @property
    def rid(self):
        if not self.reference_number:
            raise Exception("self.reference_number_ is None for actor: " + self.name + " (" + self.id + ")")
        return self.reference_number + "{" + self.id + "}"

    def to_dict(self):
        return {'actor_type': self.actor_type.name, 'id': self.id, 'name': self.name, 'reference_number': self.reference_number}

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    @classmethod
    def get_reference(cls, reference_number):
        try:
            return cls.references_[reference_number]
        except KeyError:
            return None
    
    @classmethod
    def dereference(cls, reference_number):
        if reference_number in cls.references_:
            del cls.references_[reference_number]

    def dereference(self):
        Actor.dereference_(self.reference_number)

    async def send_text(self, text_type: CommTypes, text: str):
        pass

    def apply_state(self, state: "ActorState"):
        self.states.append(state)

    def remove_state(self, state: "ActorState"):
        self.states.remove(state)
        
    def can_act(self, allow_if_hindered=False) -> tuple[bool, str]:
        if self.has_temp_flags(TemporaryCharacterFlags.IS_DEAD):
            return False, "You are dead!"
        if self.has_temp_flags(TemporaryCharacterFlags.IS_FROZEN):
            return False, "You are frozen!"
        if self.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            return False, "You are sleeping!"
        if self.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            return False, "You are stunned!"
        if self.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) and \
            (
                allow_if_hindered \
                    or not self.has_temp_flags(TemporaryCharacterFlags.IS_SITTING)
            ):
            return False, "You are sitting!"
        return True, ""
            

    def actor_vars(self, name: str) -> dict:
        # Using dictionary comprehension to prefix keys and combine dictionaries
        return {f"{name}.{key}": value for d in [self.temp_variables, self.perm_variables] for key, value in d.items()}

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: 'GameStateInterface' = None, skip_triggers: bool = False) -> bool:
        # note that you probably want to run this last in the child class implementation
        logger = StructuredLogger(__name__, prefix="Actor.echo()> ")
        logger.debug3("running")
        logger.debug3(f"text before: {text}")
        logger.debug3(f"vars: {vars}")
        # Ensure text is a string before processing
        processed_text = text if text is not None else ""
        if not already_substituted:
            processed_text = evaluate_functions_in_line(replace_vars(processed_text, vars), vars, game_state)
        logger.debug3(f"text after: {processed_text}")
        # check room triggers
        if exceptions and self in exceptions:
            return False
        if skip_triggers:
            logger.debug3("skipping triggers")
        else:
            logger.debug3(f"triggers:\n{self.triggers_by_type}")
            for trigger_type in [ TriggerType.CATCH_ANY ]:
                if trigger_type in self.triggers_by_type:
                    logger.debug3(f"checking trigger_type: {trigger_type}")
                    for trigger in self.triggers_by_type[trigger_type]:
                        logger.debug3(f"checking trigger: {trigger.to_dict()}")
                        await trigger.run(self, processed_text, vars, game_state)
        return True
    
    def mark_deleted(self):
        self.is_deleted = True

    @classmethod
    def is_deleted(cls, actor: 'Actor'):
        return actor.is_deleted

    def get_vars(self, name: str) -> dict:
        # Using dictionary comprehension to prefix keys and combine dictionaries
        return {f"{name}.{key}": value for d in [self.temp_variables, self.perm_variables] for key, value in d.items()}

    @property
    def location_room(self) -> 'Room':
        raise Exception("location_room must be implemented in child class")

    @location_room.setter
    def location_room(self, room: 'Room'):
        raise Exception("location_room must be implemented in child class")

    def get_temp_var(self, varname, default):
        return self.temp_variables.get(varname, default)
    
    def get_perm_var(self, varname, default):
        return self.perm_variables.get(varname, default)
    
    def get_recovery_modifier(self):
        return sum([state.recovery_modifier for state in self.states if isinstance(state, CharacterStateRecoveryModifier)])
    
    def make_busy_until(self, game_tick: int):
        self.recovers_at = game_tick
        # you can only have one busy cooldown at a time
        self.cooldowns = [c for c in self.cooldowns if c.cooldown_name != "busy"]
        busy_cooldown = Cooldown(self, "busy", self.game_state, cooldown_source=self, cooldown_vars=None, cooldown_end_fn=become_ready)
        busy_cooldown.start(self.game_state.current_tick, 0, game_tick)

    def make_busy_for(self, game_ticks: int):
        self.make_busy_until(self.game_state.current_tick + game_ticks)

    def is_busy(self, current_tick: int) -> bool:
        return current_tick <= self.recovers_at

    async def become_ready(self):
        self.recovers_at = 0
        if self.command_queue:
            next_command = self.command_queue.pop(0)
            try:
                await CommandHandlerInterface.get_instance().process_command(self, next_command)
            except Exception as e:
                logger = StructuredLogger(__name__, prefix="Actor.become_ready()> ")
                logger.error(f"Error processing queued command: {e}")

