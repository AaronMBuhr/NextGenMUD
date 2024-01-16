from abc import abstractmethod
from ..communication import CommTypes
from ..utility import replace_vars, get_dice_parts, roll_dice, article_plus_name, DescriptiveFlags, set_vars
from custom_detail_logger import CustomDetailLogger
from enum import Enum, auto, IntFlag
import json
from .triggers import TriggerType, Trigger
import random
from typing import Dict, List
import copy
from .game_state_interface import GameStateInterface

class ActorType(Enum):
    CHARACTER = 1
    OBJECT = 2
    ROOM = 3

class Actor:
    references_ = {}  # Class variable for storing references
    current_reference_num_ = 1  # Class variable for tracking the current reference number

    def __init__(self, actor_type: ActorType, id: str, name: str = "", create_reference=False):
        self.actor_type_ = actor_type
        self.id_ = id
        self.name_ = name
        self.article_ = "" if name == "" else "a" if name[0].lower() in "aeiou" else "an" if name else ""
        self.pronoun_subject_ = "it"
        self.pronoun_object_ = "it"
        self.pronoun_possessive_ = "its"
        self.location_room_ = None
        self.triggers_by_type_ = {}
        self.reference_number_ = None
        self.temp_variables_ = {}
        self.perm_variables_ = {}
        self.is_deleted_ = False
        if create_reference:
            self.create_reference()

    def create_reference(self) -> str:
        logger = CustomDetailLogger(__name__, prefix="Actor.create_reference()> ")
        logger.debug3(f"creating reference for {self.name_} ({self.id_})")
        reference_prefix = self.actor_type_.name[0]  # First character of ActorType
        self.reference_number_ = reference_prefix + str(Actor.current_reference_num_)
        Actor.references_[self.reference_number_] = self
        Actor.current_reference_num_ += 1
        return self.reference_number_

    @classmethod
    def references(self):
        return Actor.references_
    
    @property
    def rid(self):
        if not self.reference_number_:
            raise Exception("self.reference_number_ is None for actor: " + self.name_ + " (" + self.id_ + ")")
        return self.reference_number_ + "{" + self.id_ + "}"

    def to_dict(self):
        return {'actor_type': self.actor_type_.name, 'id': self.id_, 'name': self.name_, 'reference_number': self.reference_number_}

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
        Actor.dereference_(self.reference_number_)

    async def send_text(self, text_type: CommTypes, text: str):
        pass

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: GameStateInterface = None, skip_triggers: bool = False) -> bool:
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
            logger.critical(f"triggers:\n{self.triggers_by_type_}")
            for trigger_type in [ TriggerType.CATCH_ANY ]:
                if trigger_type in self.triggers_by_type_:
                    logger.critical(f"checking trigger_type: {trigger_type}")
                    for trigger in self.triggers_by_type_[trigger_type]:
                        logger.critical(f"checking trigger: {trigger.to_dict()}")
                        await trigger.run(self, text, vars, game_state)
        return True
    
    def mark_deleted(self):
        self.is_deleted_ = True

    @classmethod
    def is_deleted_(cls, actor: 'Actor'):
        return actor.is_deleted_


class RoomFlags(DescriptiveFlags):
    DARK = 2**0
    NO_MOB = 2**1
    INDOORS = 2**2
    NO_MAGIC = 2**3
    NO_SUMMON = 2**4
    FLIGHT_NEEDED = 2**5
    UNDERWATER = 2**6


class Room(Actor):
    from .world import Zone
    
    def __init__(self, id: str, zone: Zone, name: str = "", create_reference=False):
        super().__init__(ActorType.ROOM, id, name=name, create_reference=create_reference)
        self.definition_zone_ = zone
        self.exits_ = {}
        self.description_ = ""
        self.zone_ = None
        self.characters_ = []
        self.contents_ = []
        self.location_room_ = self
        self.triggers_by_type_ = {}

    def to_dict(self):
        return {
            'ref#': self.reference_number_,
            'id': self.id_,
            'name': self.name_,
            'description': self.description_,
            'zone': self.zone_.id_ if self.zone_ else None,
            'exits': self.exits_,
            'triggers': self.triggers_by_type_,
            # Convert complex objects to a serializable format, if necessary
            # 'zone': self.zone_.to_dict() if self.zone_ else None,
            # 'characters': [c.to_dict() for c in self.characters_],
            # 'objects': [o.to_dict() for o in self.contents_],
        }
    
    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def __str__(self):
        return self.__repr__()

    def from_yaml(self, zone, yaml_data: str):
        self.name_ = yaml_data['name']
        self.description_ = yaml_data['description']
        self.zone_ = zone

        for direction, exit_info in yaml_data['exits'].items():
            # logger.debug3(f"loading direction: {direction}")
            self.exits_[direction] = exit_info['destination']

        if 'triggers' in yaml_data:
            # print(f"triggers: {yaml_data['triggers']}")
            # raise NotImplementedError("Triggers not implemented yet.")
            # for trigger_type, trigger_info in yaml_data['triggers'].items():
            #     # logger.debug3(f"loading trigger_type: {trigger_type}")
            #     if not trigger_type in self.triggers_by_type_:
            #         self.triggers_by_type_[trigger_type] = []
            #     self.triggers_by_type_[trigger_type] += trigger_info
            for trig in yaml_data['triggers']:
                # logger.debug3(f"loading trigger_type: {trigger_type}")
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type_:
                    self.triggers_by_type_[new_trigger.trigger_type_] = []
                self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)


    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] =None, already_substituted: bool = False,
                   game_state: GameStateInterface = None, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Room.echo()> ")
        if text == False:
            raise Exception("text False")
        logger.critical("text before " + text)
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical("text after " + text)
        logger.debug3(f"checking characters: {self.characters_}")
        # if len(self.characters_) > 0:
        #     raise Exception("we found a character!")
        for c in self.characters_:
            logger.debug3(f"checking character {c.name_}")
            if exceptions is None or c not in exceptions:
                logger.debug3(f"sending '{text}' to {c.name_}")
                await c.echo(text_type, text, vars, exceptions, already_substituted=True,game_state=game_state, skip_triggers=skip_triggers)
        logger.debug3("running super, text: " + text)
        await super().echo(text_type, text, vars, exceptions, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        return True

    def remove_character(self, character: 'Character'):
        self.characters_.remove(character)

    def add_character(self, character: 'Character'):
        self.characters_.append(character)

    def remove_object(self, obj: 'Object'):
        self.contents_.remove(obj)
        obj.in_actor_ = None

    def add_object(self, obj: 'Object'):
        self.contents_.append(obj)
        obj.in_actor_ = self


class EquipLocation(Enum):
    MAIN_HAND = 1
    OFF_HAND = 2
    BOTH_HANDS = 3
    HEAD = 4
    NECK = 5
    SHOULDERS = 6
    ARMS = 7
    WRISTS = 8
    HANDS = 9
    LEFT_FINGER = 10
    RIGHT_FINGER = 11
    WAIST = 12
    LEGS = 13
    FEET = 14
    BODY = 15
    BACK = 16
    EYES = 17

    def word(self):
        return self.name.lower().replace("_", " ")
    
    def string_to_enum(equip_location_string):
        try:
            # Replace spaces with underscores and convert to uppercase
            enum_key = equip_location_string.replace(' ', '_').upper()
            # Find the enum member
            return EquipLocation[enum_key]
        except KeyError:
            return None


# class DescriptionMixin:
#     def describe(self):
#         # Accessing a hypothetical descriptions dictionary
#         return self._descriptions.get(self, "No description available")


class GamePermissionFlags(DescriptiveFlags):
    IS_ADMIN = 1
    CAN_INSPECT = 2
    CAN_MODIFY = 4

    @classmethod
    def field_name(cls, idx):
        return ["is admin", "can inspect", "can modify"][idx]


class PermanentCharacterFlags(DescriptiveFlags):
    IS_PC = 2**0
    IS_AGGRESSIVE = 2**1
    CAN_DUAL_WIELD = 2**2
    IS_INVISIBLE = 2**3
    SEE_INVISIBLE = 2**4

    @classmethod
    def field_name_unsafe(cls, idx):
        return ["is pc", "can dual wield"][idx]


class TemporaryCharacterFlags(DescriptiveFlags):
    IS_DEAD = 2**0
    IS_SITTING = 2**1
    IS_SLEEPING = 2**2
    IS_STUNNED = 2**3
    IS_DISARMED = 2**4
    IS_STEALTHED = 2**5
    IS_HIDDEN = 2**6
    SEE_INVISIBLE = 2**7
    IS_INVISIBLE = 2**8

    @classmethod
    def field_name_unsafe(cls, idx):
        return ["is dead", "is sitting", "is sleeping", "is stunned"][idx]

    
class Cooldown:
    def __init__(self, actor: Actor, cooldown_name: str, game_state: GameStateInterface,
                 cooldown_source=None, cooldown_vars: Dict=None, cooldown_end_fn: callable=None):
        self.cooldown_source_ = cooldown_source
        self.cooldown_name_ = cooldown_name
        self.actor_: Actor = actor
        self.cooldown_vars: Dict = cooldown_vars
        self.cooldown_start_tick_: int = 0
        self.cooldown_end_tick_: int = 0
        self.cooldown_duration: int = 0
        self.cooldown_end_fn_ = cooldown_end_fn
        self.game_state_ = game_state

    @classmethod
    def has_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return any([c for c in cooldowns if c.cooldown_source_ == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name_ == (cooldown_name or c.cooldown_name)])
    
    @classmethod
    def current_cooldowns(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return [c for c in cooldowns if c.cooldown_source_ == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name_ == (cooldown_name or c.cooldown_name)]
    
    @classmethod
    def last_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return max([c for c in Cooldown.current_cooldowns(cooldowns, cooldown_source, cooldown_name)],
                   key=lambda c: c.cooldown_end_tick_)
    
    def start(self, current_tick: int, cooldown_duration_ticks: int = None, cooldown_end_tick: int = None) -> bool:
        self.cooldown_start_tick_ = current_tick
        if cooldown_duration_ticks:
            self.cooldown_duration_ = cooldown_duration_ticks
            self.cooldown_end_tick_ = current_tick + cooldown_duration_ticks
        else:
            self.cooldown_end_tick_ = cooldown_end_tick
            self.cooldown_duration_ = cooldown_end_tick - current_tick
        return True

    def to_dict(self):
        return {
            'actor': self.actor_.rid,
            'cooldown_source': self.cooldown_source_,
            'cooldown_name': self.cooldown_name_,
            'cooldown_start_tick': self.cooldown_start_tick_,
            'cooldown_end_tick': self.cooldown_end_tick_,
            'cooldown_duration': self.cooldown_end_tick_ - self.cooldown_start_tick_
        }

    def cooldown_finished(self, current_tick: int) -> bool:
        return current_tick >= self.cooldown_end_tick_
    
    def ticks_remaining(self, current_tick: int) -> int:
        return max(self.cooldown_end_tick_ - current_tick, 0)

    def end_cooldown(self) -> bool:
        if self.cooldown_end_fn_:
            self.cooldown_end_fn_(self)
        return True


class ActorState:

    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, vars=None,tick_created=None):
        self.actor_: Actor = actor
        self.source_actor_: Actor = source_actor
        self.state_type_name_: str = state_type_name
        self.tick_created_: int = tick_created
        self.tick_started_: int = None
        self.tick_ending_: int = None
        self.last_tick_acted_: int = None
        self.next_tick_: int = None
        self.tick_period_: int = 0
        self.character_flags_affected_: TemporaryCharacterFlags = TemporaryCharacterFlags(0)
        self.affect_amount_: int = 0
        self.duration_remaining_: int = 0
        self.vars = vars
        self.game_state: GameStateInterface = game_state

    def to_dict(self):
        return {
            'class': self.__class__.__name__,
            'actor': self.actor_.rid,
            'tick_created': self.tick_created_,
            'tick_started': self.tick_started_,
            'tick_ending': self.tick_ending_,
            'last_tick_acted': self.last_tick_acted_,
            'next_tick': self.next_tick_,
            'tick_period': self.tick_period_
        }
    
    @abstractmethod
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        """
        Returns the next tick that the state should be applied.
        end_tick = 0 means it's indefinite
        """
        self.tick_started_ = start_tick
        self.tick_ending_ = end_tick
        self.next_tick_ = start_tick + self.tick_period_
        self.last_tick_acted_ = start_tick
        self.duration_remaining_ = self.tick_ending_ - self.tick_started_
        self.actor_.apply_state(self)
        return self.next_tick_

    @abstractmethod
    def remove_state(self, force=False) -> bool:
        """
        Returns True if the state was removed, False if it was not removed.
        """
        pass

    def does_affect_flag(self, flag: TemporaryCharacterFlags) -> bool:
        """
        Returns True if the state affects the given flag, False if it does not.
        """
        return self.character_flags_affected_.are_flags_set(flag)
    
    def perform_tick(self, tick_num: int) -> bool:
        self.duration_remaining_ = max(self.start_tick_ - tick_num, 0)
        self.last_tick_acted_ = tick_num
        if self.tick_ending_ != 0 and tick_num >= self.tick_ending_:
            self.remove_state()
        return True
    
    @abstractmethod
    def get_affect_amount(self):
        return self.affect_amount_


class CharacterStateForcedSitting(ActorState):
    from .. import CoreActions
    from ..command_handler import process_command
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_SITTING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"You knock %%t onto the ground."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} knocks you onto the ground."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} knocks %t% onto the ground."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor], game_state=cls.game_state_)
            self.actor_.temporary_character_flags_.add_flags(TemporaryCharacterFlags.IS_SITTING)
        return retval


    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s is not self and s.does_affect_flag(TemporaryCharacterFlags.IS_SITTING)]):
            return False
        retval = super().remove_state(force)
        if retval:
            self.actor_.remove_state(self)
        msg = "The dizziness wears off, you feel steady enough to stand again."
        set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
        msg = "%t% looks steady enough to stand again."
        set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars exceptions=[source_actor], game_state=cls.game_state_)
        if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
            and not self.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
            process_command(self.actor_, "stand")
        if self.location_room_ \
            and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor_.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
            CoreActions.do_aggro(self.actor_)

        return retval

    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateForcedSleeping(ActorState):
    from .. import CoreActions
    from ..command_handler import process_command
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_SLEEPING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            self.actor_.temporary_character_flags_.remove_flags(TemporaryCharacterFlags.IS_SITTING)
            self.actor_.temporary_character_flags_.add_flags(TemporaryCharacterFlags.IS_SLEEPING)
            if self.source_actor:
                msg = f"You put %t% to sleep."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} puts you to sleep."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} puts %t% to sleep."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars exceptions=[actor, source_actor], game_state=cls.game_state_)
        return retval



    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        retval = super().remove_state(force)
        if retval is not None:
            msg = "You don't feel sleepy anymore."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "%t% doesn't look sleepy anymore."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
                process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
            CoreActions.do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateStunned(ActorState):
    from .. import CoreActions
    from ..command_handler import process_command
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_STUNNED)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            self.actor_.add_flag(TemporaryCharacterFlags.IS_STUNNED)
            if self.source_actor:
                msg = f"You stun %t%."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg, game_state=cls.game_state_)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars exceptions=[actor, source_actor], game_state=cls.game_state_)
        return retval

    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        retval = super().remove_state(force)
        if retval is not None:
            msg = "You shake off the stun."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "%t% shakes off the stun."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
                process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
            CoreActions.do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateHitPenalty(ActorState):
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        # not gonna say anything for a hit penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
        #         self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars exceptions=[actor, source_actor])
        return retval

    def remove_state(self) -> bool:
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDisarmed(ActorState):
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if not retval is None:
            self.vars = {}
            mhw = self.vars["main hand weapon"] = self.actor_.equipment_[EquipLocation.MAIN_HAND]
            ohw = self.vars["off hand weapon"] = self.actor_.equipment_[EquipLocation.OFF_HAND]
            bhw = self.vars["both hands weapon"] = self.actor_.equipment_[EquipLocation.BOTH_HANDS]
            self.vars["main hand weapon"] = mhw
            self.vars["off hand weapon"] = ohw
            self.vars["both hands weapon"] = bhw
            if mhw == None and ohw == None and bhw == None:
                msg = "They aren't using any weapons."
                set_vars(self.actor_, self.source_actor_, self.actor_, msg)
                self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
                return
            if mhw:
                self.actor_.unequip_location(EquipLocation.MAIN_HAND)
                self.actor_.add_object(mhw)
            if ohw:
                self.actor_.unequip_location(EquipLocation.OFF_HAND)
                self.actor_.add_object(ohw)
            if bhw:
                self.actor_.unequip_location(EquipLocation.BOTH_HANDS)
                self.actor_.add_object(bhw)
            
            self.temporary_character_flags_.add_flags(TemporaryCharacterFlags.IS_DISARMED)
            msg = f"You disarm %%t!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg, game_state=cls.game_state_)
            self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} disarms you!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} disarms %t%!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars exceptions=[actor, source_actor])
        return retval
    

    def remove_state(self, force=True) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        mhw = self.vars["mhw"]
        ohw = self.vars["ohw"]
        bhw = self.vars["bhw"]
        if mhw and self.equipped_location_[EquipLocation.MAIN_HAND] is None:
            self.actor_.remove_object(mhw)
            self.actor_.equip_object(mhw)
        if ohw and self.equip_location_[EquipLocation.OFF_HAND] is None:
            self.actor_.remove_object(ohw)
            self.actor_.equip_object(ohw)
        if bhw and self.equip_location_[EquipLocation.BOTH_HANDS] is None:
            self.actor_.remove_object(bhw)
            self.actor_.equip_object(bhw)
        retval = super().remove_state(force)
        if retval is not None:
            self.temporary_character_flags_.remove_flag(TemporaryCharacterFlags.IS_DISARMED)
            self.actor_.remove_state(self)
            msg = "You ready your weapons again."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "$cap(%t%) readies %R% weapons again."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
                process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.permanent_character_flags_.are_flags_set(PermanentCharacterFlags.IS_PC):
            CoreActions.do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDodgePenalty(ActorState):
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        # not gonna say anything for a dodge penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
        #         self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars exceptions=[actor, source_actor])
        return retval
    
    def remove_state(self) -> bool:
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateStealthed(ActorState):
    def __init__(self, actor: Actor, game_state: GameStateInterface, source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        self.actor.TemporaryCharacterFlags_.add_flags(TemporaryCharacterFlags.IS_STEALTHED)
        self.vars = { "seen_by": [] }
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        return retval
    
    def remove_state(self) -> bool:
        self.actor.TemporaryCharacterFlags_.remove_flags(TemporaryCharacterFlags.IS_STEALTHED)
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)
    


class DamageType(Enum):
    SLASHING = 1
    PIERCING = 2
    BLUDGEONING = 3
    FIRE = 4
    COLD = 5
    LIGHTNING = 6
    ACID = 7
    POISON = 8
    DISEASE = 9
    HOLY = 10
    UNHOLY = 11
    ARCANE = 12
    PSYCHIC = 13
    FORCE = 14
    NECROTIC = 15
    RADIANT = 16

    def word(self):
        return self.name.lower()
    
    def verb(self):
        return ['slashes','pierces','bludgeons','burns','freezes','shocks',
                'corrodes','poisons','diseases','burns','corrupts','zaps',
                'mentally crushes','crushes','corrupts','burns'][self.value - 1]
    def noun(self):
        return ['slash','pierce','bludgeon','burn','freeze','shock',
                'corrode','poison','disease','burn','corrupt','zap',
                'mental crush','crush','corrupt','burn'][self.value - 1]
    


class DamageResistances:
    def __init__(self, profile=None):
        if profile:
            self.profile_ = profile
        else:
            self.profile_ = {loc: 1 for loc in DamageType}

    def to_dict(self):
        # return {EquipLocation[loc].name.lower(): dt.name.lower() for loc, dt in self.profile_.items()}
        return repr(self.profile_)

    def set(self, damage_type: DamageType, amount: float):
        self.profile_[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile_[damage_type]

class DamageReduction:
    def __init__(self, profile=None):
        if profile:
            self.profile_ = profile
        else:
            self.profile_ = {loc: 0 for loc in DamageType}

    def set(self, damage_type: DamageType, amount: float):
        self.profile_[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile_[damage_type]

    def to_dict(self):
        return repr(self.profile_)

class PotentialDamage:
    def __init__(self, damage_type: DamageType, damage_dice_number: int, damage_dice_type: int, damage_dice_bonus: int):
        self.damage_type_ = damage_type
        self.damage_dice_number_ = damage_dice_number
        self.damage_dice_type_ = damage_dice_type
        self.damage_dice_bonus_ = damage_dice_bonus
        self.min_damage_ = damage_dice_number + damage_dice_bonus
        self.max_damage_ = damage_dice_number * damage_dice_type + damage_dice_bonus
        self.glancing_damage_ = (self.max_damage_ - self.min_damage_) * 0.20 + self.min_damage_
        self.powerful_damage_ = (self.max_damage_ - self.min_damage_) * 0.80 + self.min_damage_

    def to_dict(self):
        return {
            "damage": f"{self.damage_dice_number_}d{self.damage_dice_type_}+{self.damage_dice_bonus_}",
            "damage_type": self.damage_type_.name.lower()
        }
    
    def roll_damage(self, critical_chance: int = 0, critical_multiplier: int = 2):
        total_damage = 0
        for i in range(self.damage_dice_number_):
            total_damage += random.randint(1, self.damage_dice_type_)
        total_damage += self.damage_dice_bonus_
        if random.randint(1, 100) <= critical_chance:
            total_damage *= critical_multiplier
        return total_damage
    
    def calc_susceptibility(self, damage_type: DamageType, damage_profile: List[DamageResistances]) -> float:
        logger = CustomDetailLogger(__name__, prefix="PotentialDamage.calc_susceptibility()> ")
        logger.debug(f"damage_type: {damage_type}, damage_profile: {[ x.to_dict() for x in damage_profile ]}")
        mult = 1
        for profile in damage_profile:
            mult *= profile.profile_[damage_type]
        return mult
    
    def damage_adjective(self, damage: int):
        if damage == 0:
            return "insignificant"
        if damage < self.glancing_damage_:
            return "minor"
        elif damage >= self.powerful_damage_:
            return "major"
        else:
            return "moderate"
        
    def damage_verb(self, damage: int):
        if damage == 0:
            return "whiffs"
        if damage < self.glancing_damage_:
            return "scratches"
        elif damage >= self.powerful_damage_:
            return "hits"
        else:
            return "whacks"




class AttackData():
    def __init__(self, 
                 damage_type: DamageType = None, 
                 damage_amount: str = None, 
                 damage_num_dice=None, 
                 damage_dice_size=None, 
                 damage_bonus=None, 
                 attack_bonus=0, 
                 attack_noun=None, 
                 attack_verb=None
                 ):
        logger = CustomDetailLogger(__name__, prefix="AttackData.__init__()> ")
        self.potential_damage_: List[PotentialDamage()] = []
        if damage_type and damage_amount:
            damage_parts = get_dice_parts(damage_amount)
            self.potential_damage_.append(PotentialDamage(damage_type, damage_parts[0], damage_parts[1], damage_parts[2]))
        elif damage_type and ((damage_num_dice and damage_dice_size) or damage_bonus):
            self.potential_damage_.append(PotentialDamage(damage_type, damage_num_dice or 0, damage_dice_size or 0, damage_bonus or 0))
        else:
            logger.error("AttackData() called without damage_type and damage_amount or damage_type and damage_num_dice and damage_dice_size or damage_bonus")
        self.attack_noun_ = attack_noun or "something"
        self.attack_verb_ = attack_verb or "hits"
        self.attack_bonus = attack_bonus

    def to_dict(self):
        return {
            "attack_bonus": self.attack_bonus,
            "potential_damage": [pd.to_dict() for pd in self.potential_damage_],
            # "attack_noun": self.attack_noun_,
            # "attack_verb": self.attack_verb_
        }


class CharacterClassRole(DescriptiveFlags):
    FIGHTER = 1
    ROGUE = 2
    MAGE = 4
    CLERIC = 8

    _name_to_value = {
        "fighter": FIGHTER,
        "rogue": ROGUE,
        "mage": MAGE,
        "cleric": CLERIC
    }

    @classmethod
    def field_name(cls, value):
        for name, val in cls._name_to_value.items():
            if value == val:
                return name
        raise ValueError(f"Unknown class value: {value}")

    @classmethod
    def from_field_name(cls, name):
        return cls._name_to_value.get(name.lower(), None)

class CharacterSkill():
    def __init__(self, character_class: CharacterClassRole, skill_number: int, skill_level: int=0):
        self.character_class = character_class
        self.skill_number = skill_number
        self.skill_level = skill_level

    def set_skill_level(self, skill_level: int):
        self.skill_level = skill_level

    def get_skill_level(self):
        return self.skill_level
    
    def add_points(self, points: int):
        self.skill_level += points


    

class CharacterClass:

    def __init__(self, role: CharacterClassRole):
        self.role_ = role



class CharacterAttributes(Enum):
    STRENGTH = 1
    DEXTERITY = 2
    CONSTITUTION = 3
    INTELLIGENCE = 4
    WISDOM = 5
    CHARISMA = 6

    def word(self):
        return self.name.lower()
    def __str__(self):
        return self.name.replace("_", " ").title()

class Character(Actor):
    
    def __init__(self, id: str, definition_zone: 'Zone', name: str = "", create_reference=True):
        super().__init__(ActorType.CHARACTER, id, name=name, create_reference=create_reference)
        self.definition_zone_ = definition_zone
        self.description_ = ""
        self.attributes_ = {}
        self.contents_ = []
        self.classes_: Dict[CharacterClassType, CharacterClassRole] = {}
        self.levels_ = Dict[CharacterClassType, int] = {}
        self.contents_: List[Object] = []
        self.permanent_character_flags_ = PermanentCharacterFlags(0)
        self.temporary_character_flags_ = TemporaryCharacterFlags(0)
        self.current_states_ = []
        self.connection_: 'Connection' = None
        self.fighting_whom_: Character = None
        self.equipped_: Dict[EquipLocation, Object] = {loc: None for loc in EquipLocation}
        self.damage_resistances_ = DamageResistances()
        self.current_damage_resistances_ = DamageResistances()
        self.damage_reduction_: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.current_damage_reduction_: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.natural_attacks_: List[AttackData] = []
        self.hit_modifier_: int = 80
        self.dodge_dice_number_: int = 1
        self.dodge_dice_size_: int = 50
        self.dodge_modifier_: int = 0
        self.critical_chance_: int = 0
        self.critical_multiplier_: int = 100
        self.hit_dice_ = 1
        self.hit_dice_size_ = 10
        self.hit_point_bonus_ = 0
        self.max_hit_points_ = 1
        self.current_hit_points_ = 1
        self.game_permission_flags_ = GamePermissionFlags(0)
        self.max_carrying_capacity_ = 100
        self.current_carrying_weight_ = 0
        self.num_main_hand_attacks_ = 1
        self.num_off_hand_attacks_ = 0
        self.skills_by_class_: Dict[CharacterClassType, List[CharacterSkill]] = {}
        self.cooldowns_ = List[Cooldown] = []
        self.skill_points_available_: int = 0


    def from_yaml(self, yaml_data: str):
        logger = CustomDetailLogger(__name__, prefix="Character.from_yaml()> ")
        # self.game_permission_flags_.set_flag(GamePermissionFlags.IS_ADMIN)
        # self.game_permission_flags_.set_flag(GamePermissionFlags.CAN_INSPECT)
        self.name_ = yaml_data['name']
        self.article_ = yaml_data['article'] if 'article' in yaml_data else "a" if self.name_[0].lower() in "aeiou" else "an" if self.name_ else ""
        self.description_ = yaml_data['description'] if 'description' in yaml_data else ''
        self.pronoun_subject_ = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
        self.pronoun_object_ = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
        self.pronoun_possessive_ = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
        # if 'character_flags' in yaml_data:
        #     for flag in yaml_data['character_flags']:
        #         self.permanent_character_flags_.set_flag(CharacterFlags[flag.upper()])
        if 'character_flags' in yaml_data:
            for flag in yaml_data['character_flags']:
                try:
                    self.permanent_character_flags_ = self.permanent_character_flags_.add_flag_name(flag)
                except KeyError as e:
                    logger.error(f"Error: {flag.upper()} is not a valid CharacterFlag. Details: {e}")
        # need attributes
        # need classes
        hit_point_parts = get_dice_parts(yaml_data['hit_dice'])
        self.hit_dice_, self.hit_dice_size_, self.hit_point_bonus_ = hit_point_parts[0], hit_point_parts[1], hit_point_parts[2]
        # need character flags
        # need damage resistances
        # print(yaml_data['natural_attacks'])
        for atk in yaml_data['natural_attacks']:
            new_attack = AttackData()
            new_attack.attack_noun_ = atk['attack_noun']
            new_attack.attack_verb_ = atk['attack_verb']
            for dmg in atk['potential_damage']:
                dice_parts = get_dice_parts(dmg['damage_dice'])
                num_dice, dice_size, dice_bonus = dice_parts[0],dice_parts[1],dice_parts[2]
                new_attack.potential_damage_.append(PotentialDamage(DamageType[dmg['damage_type'].upper()], num_dice, dice_size, dice_bonus))
            self.natural_attacks_.append(new_attack)
        # print(type(self.hit_dice_))
        # print(type(self.hit_dice_size_))
        # print(type(self.hit_point_bonus_))
        self.max_hit_points_ = roll_dice(self.hit_dice_, self.hit_dice_size_, self.hit_point_bonus_)
        self.current_hit_points_ = self.max_hit_points_
        self.hit_modifier_ = yaml_data['hit_modifier']
        dodge_parts = get_dice_parts(yaml_data['dodge_dice'])
        self.dodge_dice_number_, self.dodge_dice_size_, self.dodge_modifier_ = dodge_parts[0], dodge_parts[1], dodge_parts[2]
        self.critical_chance_ = yaml_data['critical_chance']
        self.critical_multiplier_ = yaml_data['critical_multiplier']
        if 'triggers' in yaml_data:
            for trig in yaml_data['triggers']:
                logger.debug(f"got trigger for {self.name_}: {trig}")
                # logger.debug3(f"loading trigger_type: {trigger_type}")
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type_:
                    self.triggers_by_type_[new_trigger.trigger_type_] = []
                self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)
        # unnecessary?
        # if 'triggers' in yaml_data:
        #     # print(f"triggers: {yaml_data['triggers']}")
        #     # raise NotImplementedError("Triggers not implemented yet.")
        #     # for trigger_type, trigger_info in yaml_data['triggers'].items():
        #     #     # logger.debug3(f"loading trigger_type: {trigger_type}")
        #     #     if not trigger_type in self.triggers_by_type_:
        #     #         self.triggers_by_type_[trigger_type] = []
        #     #     self.triggers_by_type_[trigger_type] += trigger_info
        #     logger.critical(f"def triggers first: {self.triggers_by_type_}")
        #     for trig in yaml_data['triggers']:
        #         logger.critical("in for loop for trigger")
        #         # logger.debug3(f"loading trigger_type: {trigger_type}")
        #         new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
        #         if not new_trigger.trigger_type_ in self.triggers_by_type_:
        #             self.triggers_by_type_[new_trigger.trigger_type_] = []
        #         self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)
        #     logger.critical(f"def triggers: {self.triggers_by_type_}")

    @property
    def art_name(self):
        return article_plus_name(self.article_, self.name_)
    
    @property
    def art_name_cap(self):
        return article_plus_name(self.article_, self.name_, cap=True)
    
    async def send_text(self, text_type: CommTypes, text: str) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Character.sendText()> ")
        logger.debug3(f"sendText: {text}")
        if self.connection_:
            logger.debug3(f"connection exists, sending text to {self.name_}")
            await self.connection_.send(text_type, text)
            logger.debug3("text sent")
            return True
        else:
            logger.debug3("no connection")
            return False

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: 'ComprehensiveGameState' = None, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Character.echo()> ")
        logger.critical("text before " + text)
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical("text after " + text)
        if exceptions and self in exceptions:
            retval = False
        else:
            retval = True
            logger.critical("sending text: " + text)
            await self.send_text(text_type, text)
        logger.debug3("running super")
        await super().echo(text_type, text, vars, exceptions, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        return retval

    @classmethod
    def create_from_definition(cls, char_def: 'Character') -> 'Character':
        logger = CustomDetailLogger(__name__, prefix="Character.create_from_definition()> ")
        logger.critical(f"char def triggers: {char_def.triggers_by_type_}")
        new_char = copy.deepcopy(char_def)
        logger.critical(f"new_char triggers: {char_def.triggers_by_type_}")
        if not new_char.reference_number_ or new_char.reference_number_ == char_def.reference_number_:
            new_char.create_reference()
        new_char.max_hit_points_ = roll_dice(new_char.hit_dice_, new_char.hit_dice_size_, new_char.hit_point_bonus_)
        new_char.current_hit_points_ = new_char.max_hit_points_
        new_char.contents_ = []
        new_char.connection_ = None
        new_char.fighting_whom_ = None
        new_char.equipped_ = {loc: None for loc in EquipLocation}
        for trig_type, trig_data in new_char.triggers_by_type_.items():
            for trig in trig_data:
                logger.debug(f"enabling trigger: {trig.to_dict()}")
                trig.actor_ = new_char
                trig.enable()
        return new_char
    
    def get_status_description(self):
        health_percent = self.current_hit_points_ * 100 / self.max_hit_points_
        if health_percent < 10:
            msg = "nearly dead"
        elif health_percent < 25:
            msg = "badly wounded"
        elif health_percent < 50:
            msg = "wounded"
        elif health_percent < 75:
            msg = "slightly wounded"
        elif health_percent < 90:
            msg = "in good health"
        else:
            msg = "in excellent health"
        # TODO:L: added statuses for burning, poisoned, etc.
        return msg

    def add_object(self, obj: 'Object', force=False):
        self.contents_.append(obj)
        obj.in_actor_ = self
        self.current_carrying_weight_ += obj.weight_

    def remove_object(self, obj: 'Object'):
        self.contents_.remove(obj)
        obj.in_actor_ = None
        self.current_carrying_weight_ -= obj.weight_

    def is_dead(self):
        return self.current_hit_points_ <= 0
    
    def equip_item(self, equip_location: EquipLocation, item: 'Object'):
        if self.equipped_[equip_location] != None:
            raise Exception("equip_location already in self.equipped_")
        item.equipped_location_ = equip_location
        item.in_actor_ = self
        self.equipped_[equip_location] = item
        self.calculate_damage_resistance()

    def unequip_location(self, equip_location: EquipLocation) -> 'Object':
        if equip_location not in self.equipped_:
            raise Exception("equip_location not in self.equipped_")
        item = self.equipped_[equip_location]
        item.equip_location_ = None
        item.in_actor_ = None
        self.equipped_[equip_location] = None
        self.calculate_damage_resistance()
        return item

    def calculate_damage_resistance(self):
        self.current_damage_resistances_ = copy.deepcopy(self.damage_resistances_)
        for item in self.equipped_.values():
            if item:
                for dt, mult in item.damage_resistances_.profile_.items():
                    self.current_damage_resistances_.profile_[dt] = self.current_damage_resistances_.profile_[dt] * mult
        # TODO:M: add status effects
                    
    # def get_character_states_flags(self, flags: TemporaryCharacterFlags) -> List[ActorState]:
    #     states = []
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_DEAD):
    #         states.append("dead")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_SITTING):
    #         states.append("sitting")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_SLEEPING):
    #         states.append("sleeping")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_STUNNED):
    #         states.append("stunned")
    #     return states
    
    def get_character_states_by_flag(self, flags: TemporaryCharacterFlags) -> List[ActorState]:
        return [s for s in self.current_states_ if s.does_affect_flag(flags)]
    
    def get_character_states_by_type(self, cls) -> List[ActorState]:
        return [state for state in self.current_states_ if isinstance(state, cls)]


    def add_state(self, state: ActorState) -> bool:
        self.current_states_.append(state)
        return True

    def remove_state(self, state: ActorState) -> bool:
        self.current_states_.remove(state)
        return True

    def total_levels(self):
        return sum(self.levels_.values())
    
    def has_cooldown(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.has_cooldown(self, cooldown_source, cooldown_name)
    
    def add_cooldown(self, cooldown: Cooldown):
        self.cooldowns_.append(cooldown)

    def remove_cooldown(self, cooldown: Cooldown):
        self.cooldowns_.remove(cooldown)

    def current_cooldowns(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.current_cooldowns(self, cooldown_source, cooldown_name)
    
    def last_cooldown(self, cooldown_source=None, cooldown_name: str=None):
        return Cooldown.last_cooldown(self, cooldown_source, cooldown_name)

    def get_states(self):
        return self.current_states_
    
    def has_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        return self.temporary_character_flags_.are_flags_set(flags)

    def has_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        return self.permanent_character_flags_.are_flags_set(flags)
    
    def has_game_flags(self, flags: GamePermissionFlags) -> bool:
        return self.game_permission_flags_.are_flags_set(flags)
    
    def add_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags_.add_flags(flags)
        return True
    
    def add_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags_.add_flags(flags)
        return True
    
    def add_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags_.add_flags(flags)
        return True
    
    def remove_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags_.remove_flags(flags)
        return True
    
    def remove_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags_.remove_Flags(flags)
        return True
    
    def remove_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags_.remove_Flags(flags)
        return True
    


class ObjectFlags(DescriptiveFlags):
    IS_ARMOR = 2**0
    IS_WEAPON = 2**1
    IS_CONTAINER = 2**2
    IS_CONTAINER_LOCKED = 2**3

    @classmethod
    def field_name(cls, idx):
        return ["armor", "weapon", "container", "container-locked"][idx]


class Object(Actor):
    def __init__(self, id: str, zone: 'Zone', name: str = "", create_reference=False):
        super().__init__(ActorType.OBJECT, id, name=name, create_reference=create_reference)
        self.definition_zone_: 'Zone' = zone
        self.name_: str = name
        self.article_ = "" if name == "" else "a" if name[0].lower() in "aeiou" else "an" if name else ""
        self.zone_: 'Zone' = None
        self.in_actor_: Actor = None
        self.object_flags_ = ObjectFlags(0)
        self.equipped_location_: EquipLocation = None
        self.equip_locations_: List[EquipLocation] = []
        # for armor
        self.damage_resistances_ = DamageResistances()
        self.damage_reduction_ = DamageReduction()
        # for weapons
        self.attack_bonus_: int = 0
        self.damage_type_: DamageType = None
        self.damage_num_dice_:int = 0
        self.damage_dice_size_:int = 0
        self.damage_bonus_:int = 0
        self.dodge_penalty_:int = 0
        self.weight_:int = 0
        self.value_:int = 0
        self.contents_: List[Object] = []


    def to_dict(self):
        return {
            'id': self.id_,
            'name': self.name_,
            'equip_locations': [ loc.name.lower() for loc in self.equip_locations_ ],
            'damage_resistances': self.damage_resistances_.to_dict(),
            'damage_reduction': self.damage_reduction_,
            'damage_type': self.damage_type_.name.lower() if self.damage_type_ else None,
            'damage_dice_number': self.damage_num_dice_,
            'damage_dice_size': self.damage_dice_size_,
            'damage_bonus': self.damage_bonus_,
            'weight': self.weight_
        }
    
    def from_yaml(self, yaml_data: str):
        self.name_ = yaml_data['name']
        self.description_ = yaml_data['description']
        self.article_ = yaml_data['article'] if 'article' in yaml_data else "a" if self.name_[0].lower() in "aeiou" else "an" if self.name_ else ""
        self.pronoun_subject_ = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
        self.pronoun_object_ = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
        self.pronoun_possessive_ = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
        self.weight_ = yaml_data['weight']
        self.value_ = yaml_data['value']
        if 'equip_locations' in yaml_data:
            for el in yaml_data['equip_locations']:
                self.equip_locations_.append(EquipLocation.string_to_enum(el))
        if 'attack_bonus' in yaml_data:
            self.attack_bonus_ = yaml_data['attack_bonus']
        if 'damage_type' in yaml_data:
            self.damage_type_ = DamageType[yaml_data['damage_type'].upper()] if 'damage_type' in yaml_data else None
            dmg_parts = get_dice_parts(yaml_data['damage'])
            self.damage_num_dice_ = dmg_parts[0]
            self.damage_dice_size_ = dmg_parts[1]
            self.damage_bonus_ = dmg_parts[2]
        self.dodge_penalty_ = yaml_data['dodge_penalty'] if 'dodge_penalty' in yaml_data else 0
        if 'damage_resistances' in yaml_data:
            for dt, mult in yaml_data['damage_resistances'].items():
                self.damage_resistances_.set(DamageType[dt.upper()], mult)
        if 'damage_reduction' in yaml_data:
            for dt, amount in yaml_data['damage_reduction'].items():
                self.damage_reduction_.set(DamageType[dt.upper()], amount)

        if 'triggers' in yaml_data:
            # print(f"triggers: {yaml_data['triggers']}")
            # raise NotImplementedError("Triggers not implemented yet.")
            # for trigger_type, trigger_info in yaml_data['triggers'].items():
            #     # logger.debug3(f"loading trigger_type: {trigger_type}")
            #     if not trigger_type in self.triggers_by_type_:
            #         self.triggers_by_type_[trigger_type] = []
            #     self.triggers_by_type_[trigger_type] += trigger_info
            for trig in yaml_data['triggers']:
                # logger.debug3(f"loading trigger_type: {trigger_type}")
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type_:
                    self.triggers_by_type_[new_trigger.trigger_type_] = []
                self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)
    
    def add_object(self, obj: 'Object', force=False):
        self.contents_.append(obj)
        obj.in_actor_ = self

    def remove_object(self, obj: 'Object'):
        self.contents_.remove(obj)
        obj.in_actor_ = None

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted:bool = False,
                   game_state=cls.game_state_, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Object.echo()> ")
        logger.critical("text before " + text)
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical("text after " + text)
        return await super().echo(text_type, text, vars, exceptions, game_state=game_state, skip_triggers=skip_triggers)
    
    @classmethod
    def create_from_definition(cls, obj_def: 'Object') -> 'Object':
        new_obj = copy.deepcopy(obj_def)
        if not new_obj.reference_number_ or new_obj.reference_number_ == obj_def.reference_number_:
            new_obj.create_reference()
        for trig_type, trig_data in new_obj.triggers_by_type_.items():
            for trig in trig_data:
                trig.actor_ = new_obj
                trig.enable()
        return new_obj
    
    @classmethod
    def collapse_name_multiples(cls, objects: List['Object'], separator: str, minimum_qty=1):
        if len(objects) == 0:
            return ""
        elif len(objects) == 1:
            return f"{objects[0].article_} {objects[0].name_}"

        multiples = {}
        for obj in objects:
            if obj.name_ in multiples:
                multiples[obj.name_]["count"] += 1 
            else:
                multiples[obj.name_] = {"count": 1, "article": obj.article_}
        
        msg_parts = []
        for name, info in multiples.items():
            if info["count"] >= minimum_qty:
                if info["count"] == 1:
                    msg_parts.append(f"{info['article']} {name}")
                else:
                    msg_parts.append(f"{info['count']} {name}s")
        return separator.join(msg_parts)

    def has_flags(self, flags: ObjectFlags) -> bool:
        return self.object_flags_.are_flags_set(flags)

    def set_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags_.add_flags(flags)
        return True
    
    def remove_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags_.remove_Flags(flags)
        return True
    
    @property
    def art_name(self):
        return article_plus_name(self.article_, self.name_)
    
    @property
    def art_name_cap(self):
        return article_plus_name(self.article_, self.name_, cap=True)


class Corpse(Object):

    def __init__(self, character: Character, room: Room):
        id = character.id_ + "_corpse"
        super().__init__(id, character.definition_zone_, name=f"{article_plus_name(character.article_, character.name_)}'s corpse", create_reference=True)
        self.article_ = ""
        self.description_ = f"The corpse of {character.name_} lies here. It makes you feel sad..."
        self.character_ = character
        self.object_flags_.add_flags(ObjectFlags.IS_CONTAINER)
        self.definition_zone_ = None
        self.location_room_ = room
        self.zone_ = room.zone_
        self.weight_ = 10

    def to_dict(self):
        return {
            'actor_type': self.actor_type_.name,
            'rid': self.rid,
            'name': self.name_,
            'character': self.character_.to_dict(),
            'contents': [obj.to_dict() for obj in self.contents_]
        }
    
    def transfer_inventory(self):
        for obj in self.character_.contents_[:]:
            self.character_.remove_object(obj)
            self.add_object(obj)
            obj.location_room_ = self.character.location_room_



