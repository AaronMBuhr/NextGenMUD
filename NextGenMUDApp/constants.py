from typing import Dict, List, Optional, ClassVar, Type, Any, Union, Set
# import yaml
from .structured_logger import StructuredLogger
from .basic_types import DescriptiveFlags


class CharacterClassRole(DescriptiveFlags):
    # Tell EnumMeta to ignore mapping variables
    _ignore_ = 'BASE_TO_SPECIALIZATIONS SPECIALIZATION_TO_BASE'
    # Base classes
    FIGHTER = 1 << 0
    ROGUE = 1 << 1
    MAGE = 1 << 2
    CLERIC = 1 << 3
    
    # Fighter specializations (level 20+)
    BERSERKER = 1 << 6   # Fighter specialization
    GUARDIAN = 1 << 7    # Fighter specialization
    REAVER = 1 << 8      # Fighter specialization
    
    # Rogue specializations (level 20+)
    DUELIST = 1 << 11    # Rogue specialization
    ASSASSIN = 1 << 12   # Rogue specialization
    INFILTRATOR = 1 << 13  # Rogue specialization
    
    # Mage specializations (level 20+)
    EVOKER = 1 << 16    # Mage specialization
    CONJURER = 1 << 17  # Mage specialization
    ENCHANTER = 1 << 18 # Mage specialization
    
    # Cleric specializations (level 20+)
    WARPRIEST = 1 << 21    # Cleric specialization
    RESTORER = 1 << 22    # Cleric specialization
    RITUALIST = 1 << 23   # Cleric specialization

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
    
    # Player save settings
    PLAYER_SAVES_DIR: ClassVar[str] = "player_saves"
    DEFAULT_START_LOCATION: ClassVar[str] = "debug_zone.starting_room"  # Format: zone.room
    DEFAULT_CHARACTER_TEMPLATE: ClassVar[str] = "debug_zone.test_player"
    
    # Disconnect/linkdead settings
    DISCONNECT_GRACE_PERIOD_SECONDS: ClassVar[int] = 60
    
    # Character save options
    SAVE_CHARACTER_STATES: ClassVar[bool] = True
    SAVE_CHARACTER_COOLDOWNS: ClassVar[bool] = True
    
    # Specialization level requirement
    SPECIALIZATION_LEVEL: ClassVar[int] = 20
    
    # Mana system
    MANA_BY_CHARACTER_CLASS: ClassVar[Dict[Union[CharacterClassRole, int], int]] = {}
    MANA_ATTRIBUTE_SCALING: ClassVar[int] = 2
    MANA_REGEN_COMBAT: ClassVar[float] = 0.1
    MANA_REGEN_WALKING: ClassVar[float] = 0.5
    MANA_REGEN_RESTING: ClassVar[float] = 2.0
    MANA_REGEN_MEDITATING: ClassVar[float] = 4.0
    
    # Stamina system
    STAMINA_BY_CHARACTER_CLASS: ClassVar[Dict[Union[CharacterClassRole, int], int]] = {}
    STAMINA_ATTRIBUTE_SCALING: ClassVar[int] = 2
    STAMINA_REGEN_COMBAT: ClassVar[float] = 0.5
    STAMINA_REGEN_WALKING: ClassVar[float] = 2.0
    STAMINA_REGEN_RESTING: ClassVar[float] = 4.0
    
    # HP regeneration
    HP_REGEN_COMBAT: ClassVar[float] = 0.0
    HP_REGEN_WALKING: ClassVar[float] = 0.1
    HP_REGEN_RESTING: ClassVar[float] = 0.5
    HP_REGEN_SLEEPING: ClassVar[float] = 1.0


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
            
        # Load player save settings
        if "PLAYER_SAVES_DIR" in constants_dict:
            Constants.PLAYER_SAVES_DIR = constants_dict["PLAYER_SAVES_DIR"]
        if "DEFAULT_START_LOCATION" in constants_dict:
            Constants.DEFAULT_START_LOCATION = constants_dict["DEFAULT_START_LOCATION"]
        if "DEFAULT_CHARACTER_TEMPLATE" in constants_dict:
            Constants.DEFAULT_CHARACTER_TEMPLATE = constants_dict["DEFAULT_CHARACTER_TEMPLATE"]
            
        # Load disconnect/linkdead settings
        if "DISCONNECT_GRACE_PERIOD_SECONDS" in constants_dict:
            Constants.DISCONNECT_GRACE_PERIOD_SECONDS = constants_dict["DISCONNECT_GRACE_PERIOD_SECONDS"]
            
        # Load character save options
        if "SAVE_CHARACTER_STATES" in constants_dict:
            Constants.SAVE_CHARACTER_STATES = constants_dict["SAVE_CHARACTER_STATES"]
        if "SAVE_CHARACTER_COOLDOWNS" in constants_dict:
            Constants.SAVE_CHARACTER_COOLDOWNS = constants_dict["SAVE_CHARACTER_COOLDOWNS"]
            
        # Load specialization level
        if "SPECIALIZATION_LEVEL" in constants_dict:
            Constants.SPECIALIZATION_LEVEL = constants_dict["SPECIALIZATION_LEVEL"]
        
        # Load mana by character class
        if "MANA_GAIN_BY_CLASS" in constants_dict:
            for class_name, mana in constants_dict["MANA_GAIN_BY_CLASS"].items():
                class_enum = CharacterClassRole.from_field_name(class_name)
                Constants.MANA_BY_CHARACTER_CLASS[class_enum] = mana
        
        # Load mana settings
        if "MANA_ATTRIBUTE_SCALING" in constants_dict:
            Constants.MANA_ATTRIBUTE_SCALING = constants_dict["MANA_ATTRIBUTE_SCALING"]
        if "MANA_REGEN_COMBAT" in constants_dict:
            Constants.MANA_REGEN_COMBAT = constants_dict["MANA_REGEN_COMBAT"]
        if "MANA_REGEN_WALKING" in constants_dict:
            Constants.MANA_REGEN_WALKING = constants_dict["MANA_REGEN_WALKING"]
        if "MANA_REGEN_RESTING" in constants_dict:
            Constants.MANA_REGEN_RESTING = constants_dict["MANA_REGEN_RESTING"]
        if "MANA_REGEN_MEDITATING" in constants_dict:
            Constants.MANA_REGEN_MEDITATING = constants_dict["MANA_REGEN_MEDITATING"]
        
        # Load stamina by character class
        if "STAMINA_GAIN_BY_CLASS" in constants_dict:
            for class_name, stamina in constants_dict["STAMINA_GAIN_BY_CLASS"].items():
                class_enum = CharacterClassRole.from_field_name(class_name)
                Constants.STAMINA_BY_CHARACTER_CLASS[class_enum] = stamina
        
        # Load stamina settings
        if "STAMINA_ATTRIBUTE_SCALING" in constants_dict:
            Constants.STAMINA_ATTRIBUTE_SCALING = constants_dict["STAMINA_ATTRIBUTE_SCALING"]
        if "STAMINA_REGEN_COMBAT" in constants_dict:
            Constants.STAMINA_REGEN_COMBAT = constants_dict["STAMINA_REGEN_COMBAT"]
        if "STAMINA_REGEN_WALKING" in constants_dict:
            Constants.STAMINA_REGEN_WALKING = constants_dict["STAMINA_REGEN_WALKING"]
        if "STAMINA_REGEN_RESTING" in constants_dict:
            Constants.STAMINA_REGEN_RESTING = constants_dict["STAMINA_REGEN_RESTING"]
        
        # Load HP regen settings
        if "HP_REGEN_COMBAT" in constants_dict:
            Constants.HP_REGEN_COMBAT = constants_dict["HP_REGEN_COMBAT"]
        if "HP_REGEN_WALKING" in constants_dict:
            Constants.HP_REGEN_WALKING = constants_dict["HP_REGEN_WALKING"]
        if "HP_REGEN_RESTING" in constants_dict:
            Constants.HP_REGEN_RESTING = constants_dict["HP_REGEN_RESTING"]
        if "HP_REGEN_SLEEPING" in constants_dict:
            Constants.HP_REGEN_SLEEPING = constants_dict["HP_REGEN_SLEEPING"]

