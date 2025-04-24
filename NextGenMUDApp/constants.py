from typing import Dict, List, Optional, ClassVar, Type, Any, Union, Set
import yaml
from .structured_logger import StructuredLogger
from .basic_types import DescriptiveFlags


class CharacterClassRole(DescriptiveFlags):
    # Tell EnumMeta to ignore mapping variables
    _ignore_ = 'BASE_TO_SPECIALIZATIONS SPECIALIZATION_TO_BASE'
    # Base classes
    FIGHTER = 1
    ROGUE = 2
    MAGE = 4
    CLERIC = 8
    
    # Fighter specializations (level 20+)
    BERSERKER = 16   # Fighter specialization
    GUARDIAN = 32    # Fighter specialization
    REAVER = 64      # Fighter specialization
    
    # Rogue specializations (level 20+)
    DUELIST = 128    # Rogue specialization
    ASSASSIN = 256   # Rogue specialization
    INFILTRATOR = 512  # Rogue specialization
    
    # Mage specializations (level 20+)
    EVOKER = 1024    # Mage specialization
    CONJURER = 2048  # Mage specialization
    ENCHANTER = 4096 # Mage specialization
    
    # Cleric specializations (level 20+)
    WARPRIEST = 8192    # Cleric specialization
    RESTORER = 16384    # Cleric specialization
    RITUALIST = 32768   # Cleric specialization

    # Base class to specialization mapping
    BASE_TO_SPECIALIZATIONS: ClassVar[Dict[int, List[int]]] = {
        FIGHTER: [BERSERKER, GUARDIAN, REAVER],
        ROGUE: [DUELIST, ASSASSIN, INFILTRATOR],
        MAGE: [EVOKER, CONJURER, ENCHANTER],
        CLERIC: [WARPRIEST, RESTORER, RITUALIST]
    }
    
    # Specialization to base class mapping
    SPECIALIZATION_TO_BASE: ClassVar[Dict[int, int]] = {
        BERSERKER: FIGHTER,
        GUARDIAN: FIGHTER,
        REAVER: FIGHTER,
        DUELIST: ROGUE,
        ASSASSIN: ROGUE,
        INFILTRATOR: ROGUE,
        EVOKER: MAGE,
        CONJURER: MAGE,
        ENCHANTER: MAGE,
        WARPRIEST: CLERIC,
        RESTORER: CLERIC,
        RITUALIST: CLERIC
    }
    
    @classmethod
    def get_base_classes(cls) -> List[int]:
        """Returns a list of all base classes"""
        return [cls.FIGHTER, cls.ROGUE, cls.MAGE, cls.CLERIC]
    
    @classmethod
    def get_specializations(cls, base_class: int) -> List[int]:
        """Returns a list of specializations for a given base class"""
        return cls.BASE_TO_SPECIALIZATIONS.get(base_class, [])
    
    @classmethod
    def get_base_class(cls, specialization: int) -> Optional[int]:
        """Returns the base class for a given specialization"""
        return cls.SPECIALIZATION_TO_BASE.get(specialization)
    
    @classmethod
    def is_specialization(cls, role: int) -> bool:
        """Returns True if the role is a specialization"""
        return role in cls.SPECIALIZATION_TO_BASE
    
    @classmethod
    def is_base_class(cls, role: int) -> bool:
        """Returns True if the role is a base class"""
        return role in cls.BASE_TO_SPECIALIZATIONS

    @classmethod
    def field_name(cls, value: int) -> str:
        for member in cls:
            if member.value == value:
                return member.name.lower()
        raise ValueError(f"Unknown class value: {value}")

    @classmethod
    def from_field_name(cls, name: str) -> 'CharacterClassRole':
        name = name.upper()
        if name in cls.__members__:
            return cls.__members__[name]
        raise ValueError(f"Unknown class name: {name}")


class Constants:
    REFERENCE_SYMBOL: ClassVar[str] = '|'
    REFERENCE_SYMBOL_ESCAPE: ClassVar[str] = '||'
    GAME_TICK_SEC: ClassVar[float] = 0.5
    TICKS_PER_ROUND: ClassVar[int] = 8
    XP_PROGRESSION: ClassVar[List[int]] = []
    HP_BY_CHARACTER_CLASS: ClassVar[Dict[Union[CharacterClassRole, int], int]] = {}
    MAIN_HAND_ATTACK_PROGRESSION: ClassVar[Dict[Union[CharacterClassRole, int], List[int]]] = {}
    OFF_HAND_ATTACK_PROGRESSION: ClassVar[Dict[Union[CharacterClassRole, int], List[int]]] = {}
    RECOVERY_TICKS: ClassVar[int] = 4


    @classmethod
    def load_from_dict(cls, constants_dict: Dict[str, Any]) -> None:

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

