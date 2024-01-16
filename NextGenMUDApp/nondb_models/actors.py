from abc import abstractmethod
import copy
from custom_detail_logger import CustomDetailLogger
from enum import Enum, auto, IntFlag
import json
import random
from typing import Dict, List
from .actor_interface import ActorInterface, ActorType, ActorSpawnData
from ..basic_types import DescriptiveFlags
from ..communication import CommTypes
from .object_interface import ObjectInterface
from .trigger_interface import TriggerType
from ..utility import replace_vars, get_dice_parts, roll_dice, article_plus_name, set_vars


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
        self.location_room = None
        self.triggers_by_type = {}
        self.reference_number = None
        self.temp_variables = {}
        self.perm_variables = {}
        self.spawned_from: ActorSpawnData = None
        self.spawned: List[Actor] = []
        self.is_deleted = False
        if create_reference:
            self.create_reference()

    def create_reference(self) -> str:
        logger = CustomDetailLogger(__name__, prefix="Actor.create_reference()> ")
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

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: 'GameStateInterface' = None, skip_triggers: bool = False) -> bool:
        # note that you probably want to run this last in the child class implementation
        logger = CustomDetailLogger(__name__, prefix="Actor.echo()> ")
        logger.critical("running")
        logger.critical(f"text before: {text}")
        logger.critical(f"vars: {vars}")
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical(f"text after: {text}")
        # check room triggers
        if exceptions and self in exceptions:
            return False
        if skip_triggers:
            logger.critical("skipping triggers")
        else:
            logger.critical(f"triggers:\n{self.triggers_by_type}")
            for trigger_type in [ TriggerType.CATCH_ANY ]:
                if trigger_type in self.triggers_by_type:
                    logger.critical(f"checking trigger_type: {trigger_type}")
                    for trigger in self.triggers_by_type[trigger_type]:
                        logger.critical(f"checking trigger: {trigger.to_dict()}")
                        await trigger.run(self, text, vars, game_state)
        return True
    
    def mark_deleted(self):
        self.is_deleted = True

    @classmethod
    def is_deleted(cls, actor: 'Actor'):
        return actor.is_deleted

    def get_vars(self, name: str) -> dict:
        # Using dictionary comprehension to prefix keys and combine dictionaries
        return {f"{name}.{key}": value for d in [self.temp_variables, self.perm_variables] for key, value in d.items()}




