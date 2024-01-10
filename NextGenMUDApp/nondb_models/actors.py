from abc import abstractmethod
from ..communication import CommTypes
from ..core import FlagBitmap, replace_vars, get_dice_parts, roll_dice
from custom_detail_logger import CustomDetailLogger
from enum import Enum, auto
import json
from .triggers import TriggerType, Trigger
import random
from typing import Dict, List
import copy

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
        self.pronoun_subject_ = "it"
        self.pronoun_object_ = "it"
        self.location_room_ = None
        self.triggers_by_type_ = {}
        self.reference_number_ = None
        self.temp_variables_ = {}
        self.perm_variables_ = {}
        if create_reference:
            self.create_reference()

    def create_reference(self) -> str:
        logger = CustomDetailLogger(__name__, prefix="Actor.create_reference()> ")
        logger.critical(f"creating reference for {self.name_} ({self.id_})")
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

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Actor.echo()> ")
        logger.debug3("running")
        logger.debug3(f"text: {text}")
        logger.debug3(f"vars: {vars}")
        if vars:
            text = replace_vars(text, vars)
        logger.debug3(f"formatted text: {text}")
        # check room triggers
        if exceptions and self in exceptions:
            return False
        logger.debug3(f"triggers:\n{self.triggers_by_type_}")
        for trigger_type in [ TriggerType.CATCH_ANY ]:
            if trigger_type in self.triggers_by_type_:
                logger.debug3(f"checking trigger_type: {trigger_type}")
                for trigger in self.triggers_by_type_[trigger_type]:
                    logger.debug3(f"checking trigger: {trigger.to_dict()}")
                    await trigger.run(self, text, vars)
        return True


class Room(Actor):
    
    def __init__(self, id: str, zone=None, name: str = "", create_reference=True):
        super().__init__(ActorType.ROOM, id, name=name, create_reference=create_reference)
        self.exits_ = {}
        self.description_ = ""
        self.zone_ = None
        self.characters_ = []
        self.objects_ = []
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
            # 'objects': [o.to_dict() for o in self.objects_],
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


    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Room.echo()> ")
        logger.debug3("running super, text: " + text)
        await super().echo(text_type, text, vars, exceptions)
        if text == False:
            raise Exception("text False")
        logger.debug3("ran super, text: " + text)
        logger.debug3(f"checking characters: {self.characters_}")
        # if len(self.characters_) > 0:
        #     raise Exception("we found a character!")
        for c in self.characters_:
            logger.debug3(f"checking character {c.name_}")
            if exceptions is None or c not in exceptions:
                logger.debug3(f"sending '{text}' to {c.name_}")
                await c.echo(text_type, text, vars, exceptions)
        return True

    def remove_character(self, character: 'Character'):
        self.characters_.remove(character)

    def add_character(self, character: 'Character'):
        self.characters_.append(character)


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
    TAIL = 18

    def word(self):
        return self.name.lower().replace("_", " ")

class CharacterFlags(Enum):
    IS_PC = 2^0


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


class DamageResistances:
    def __init__(self, profile=None):
        if profile:
            self.profile_ = profile
        else:
            self.profile_ = {loc: 1 for loc in EquipLocation}

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

    def roll_damage(self, critical_chance: int = 0, critical_multiplier: int = 2):
        total_damage = 0
        for i in range(self.damage_dice_number_):
            total_damage += random.randint(1, self.damage_dice_type_)
        total_damage += self.damage_dice_bonus_
        if random.randint(1, 100) <= critical_chance:
            total_damage *= critical_multiplier
        return total_damage
    
    def calc_susceptability(self, damage_type: DamageType, damage_profile: List[DamageResistances]) -> float:
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

class CharacterClassType(Enum):
    WARRIOR = 1
    MAGE = 2
    CLERIC = 3
    ROGUE = 4

class CharacterClass:
    def __init__(self, character_class_type: CharacterClassType, level: int = 1):
        self.level_ = level


class AttackData():
    def __init__(self):
        self.potential_damage_: List[PotentialDamage()] = []
        self.attack_noun_ = "something"
        self.attack_verb_ = "hits"

class Character(Actor):
    
    def __init__(self, id: str, name: str = "", create_reference=True):
        super().__init__(ActorType.CHARACTER, id, name=name, create_reference=create_reference)
        self.description_ = ""
        self.attributes_ = {}
        self.classes_: Dict[CharacterClassType, CharacterClass] = {}
        self.inventory_: List[Object] = []
        self.character_flags_ = FlagBitmap()
        self.connection_: 'Connection' = None
        self.fighting_whom_: Character = None
        self.equipped_: Dict[EquipLocation, Object] = {loc: None for loc in EquipLocation}
        self.damage_resistances_ = DamageResistances()
        self.damage_reduction_: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.natural_attacks_: List[AttackData] = []
        self.hit_modifier_: int = 80
        self.dodge_dice_number_: int = 1
        self.dodge_dice_size_: int = 50
        self.dodge_modifier_: int = 0
        self.critical_chance_: int = 0
        self.critical_multiplier: int = 100
        self.hit_dice_ = 1
        self.hit_dice_size_ = 10
        self.hit_point_bonus_ = 0
        self.hit_points_ = 0


    def from_yaml(self, yaml_data: str):
        self.name_ = yaml_data['name']
        self.description_ = yaml_data['description']
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
        self.hit_points = roll_dice(self.hit_dice_, self.hit_dice_size_, self.hit_point_bonus_)
        self.hit_modifier_ = yaml_data['hit_modifier']
        dodge_parts = get_dice_parts(yaml_data['dodge_dice'])
        self.dodge_dice_number_, self.dodge_dice_size_, self.dodge_modifier_ = dodge_parts[0], dodge_parts[1], dodge_parts[2]
        self.critical_chance_ = yaml_data['critical_chance']
        self.critical_multiplier = yaml_data['critical_multiplier']
        if 'triggers' in yaml_data:
            for trig in yaml_data['triggers']:
                # logger.debug3(f"loading trigger_type: {trigger_type}")
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type_:
                    self.triggers_by_type_[new_trigger.trigger_type_] = []
                self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)

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

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Character.echo()> ")
        logger.debug3("running super")
        await super().echo(text_type, text, vars, exceptions)
        if exceptions and self in exceptions:
            return False
        logger.debug3("sending text")
        await self.send_text(text_type, text)
        return True

    @classmethod
    def create_from_definition(cls, char_def: 'Character') -> 'Character':
        new_char = Character(char_def.id_, char_def.name_)
        new_char = copy.deepcopy(char_def)
        if not new_char.reference_number_ or new_char.reference_number_ == char_def.reference_number_:
            new_char.create_reference()
        new_char.hit_points_ = roll_dice(new_char.hit_dice_, new_char.hit_dice_size_, new_char.hit_point_bonus_)
        new_char.inventory_ = []
        new_char.connection_ = None
        new_char.fighting_whom_ = None
        new_char.equipped_ = {loc: None for loc in EquipLocation}
        return new_char

class Object(Actor):

    def __init__(self, id: str, name: str = ""):
        super().__init__(ActorType.OBJECT, id, name)
        self.name_ = ""
        self.location_inventory_ = None
        self.location_container_ = None
        self.attributes_ = {}
        self.object_flags_ = FlagBitmap()
        self.damage_resistances_ = DamageResistances()
        self.damage_reduction_: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.equip_location_: EquipLocation = None
        # note that location of LEFT_FINGER also allows RIGHT_FINGER

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Object.echo()> ")
        text = await super().echo(text_type, text, vars, exceptions)
        return True


