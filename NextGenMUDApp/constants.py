from typing import Dict
import yaml
from .structured_logger import StructuredLogger
from .basic_types import DescriptiveFlags



class CharacterClassRole(DescriptiveFlags):
    FIGHTER = 1
    ROGUE = 2
    MAGE = 4
    CLERIC = 8

    # Remove the _name_to_value dictionary

    @classmethod
    def field_name(cls, value):
        for member in cls:
            if member.value == value:
                return member.name.lower()
        raise ValueError(f"Unknown class value: {value}")

    @classmethod
    def from_field_name(cls, name):
        name = name.upper()
        if name in cls.__members__:
            return cls.__members__[name]
        raise ValueError(f"Unknown class name: {name}")


class Constants:
    REFERENCE_SYMBOL = '|'
    REFERENCE_SYMBOL_ESCAPE = '||'
    GAME_TICK_SEC = 0.5
    TICKS_PER_ROUND = 8
    XP_PROGRESSION = []
    HP_BY_CHARACTER_CLASS = {}
    MAIN_HAND_ATTACK_PROGRESSION = {}
    OFF_HAND_ATTACK_PROGRESSION = {}


    @classmethod
    def load_from_dict(cls, constants_dict: Dict):

        # Load XP progression
        Constants.XP_PROGRESSION = constants_dict["XP_PROGRESSION"]

        # Load HP by character class
        for class_name, hp in constants_dict["HIT_POINT_GAIN_BY_CLASS"].items():
            class_enum = CharacterClassRole.from_field_name(class_name)
            Constants.HP_BY_CHARACTER_CLASS[class_enum] = hp

        # Load main hand / off hand progression
        for role in CharacterClassRole:
            role_num = role.value
            Constants.MAIN_HAND_ATTACK_PROGRESSION[role_num] = [1 for _ in range(60)]
            Constants.OFF_HAND_ATTACK_PROGRESSION[role_num] = [1 for _ in range(60)]
        for class_name, an in constants_dict["MAIN_HAND_ATTACK_PROGRESSION"].items():
            class_enum = CharacterClassRole.from_field_name(class_name)
            Constants.MAIN_HAND_ATTACK_PROGRESSION[class_enum] = an
        for class_name, an in constants_dict["OFF_HAND_ATTACK_PROGRESSION"].items():
            class_enum = CharacterClassRole.from_field_name(class_name)
            Constants.OFF_HAND_ATTACK_PROGRESSION[class_enum] = an

