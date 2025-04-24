from enum import Enum, IntFlag
from typing import TypeVar, Generic, Any, Dict, Union

T = TypeVar('T')  # This represents any type


class DescriptiveFlags(IntFlag):

    def __init__(self, value=0, *args, **kwargs):
        super().__init__(value)

    @classmethod
    def field_name(cls, index: int) -> str:
        try:
            return cls.field_name_unsafe(index)
        except IndexError:
            return "unknown_flag"

    @classmethod
    def field_name_unsafe(cls, index: int):
        raise NotImplementedError("This method should be overridden in a child class")

    def to_comma_separated(self):
        # Generate a comma-separated list of descriptions for all enabled flags
        return ', '.join(self.field_name(flag.value.bit_length() - 1) for flag in self.__class__ if flag in self)


    def add_flags(self, flags):
        # Add one or more flags
        if isinstance(flags, self.__class__):
            return self | flags
        elif isinstance(flags, int):
            return self.__class__(self.value | flags)
        else:
            raise ValueError("Invalid flag or flag combination")

    def remove_flags(self, flags):
        # Remove one or more flags
        if isinstance(flags, self.__class__):
            return self & ~flags
        elif isinstance(flags, int):
            return self.__class__(self.value & ~flags)
        else:
            raise ValueError("Invalid flag or flag combination")

    def add_flag_name(self, flag_name):
        # Add a flag by its name
        flag_name = flag_name.upper().replace(" ", "_")  # Convert to the expected enum name format
        if flag_name in self.__class__.__members__:
            flag = self.__class__.__members__[flag_name]
            return self.add_flags(flag)
        else:
            raise ValueError(f"Invalid flag name: {flag_name}")


    def are_flags_set(self, flags):
        # Check if each flag in a bitwise OR combination is set
        if isinstance(flags, self.__class__):
            for flag in self.__class__:
                if flags & flag and not self & flag:
                    return False
            return True
        else:
            raise ValueError("Invalid flag or flag combination")

    def are_flags_list_set(self, *flags):
        # Check if multiple specified flags are all set
        for flag in flags:
            if not isinstance(flag, self.__class__):
                raise ValueError(f"Invalid flag: {flag}")
            if not self & flag == flag:
                return False
        return True
    
    def get_flags_set(self):
        set_flags = []
        for flag in self.__class__:
            if self & flag == flag:
                set_flags.append(flag)
        return set_flags


class GenericEnumWithAttributes(Enum):
    """
    A generic enum that forwards attribute access to its values.
    Specially handles dictionary values to allow attribute-style access.
    """
    def __getattr__(self, name: str) -> Any:
        if isinstance(self.value, dict) and name in self.value:
            return self.value[name]
        return getattr(self.value, name)

    @classmethod
    def _missing_(cls, value):
        return None

    # # Example with Skills
    # class Skill:
    #     name: str
    #     base_class: 'CharacterClassRole'  # Forward reference
    #     cooldown_name: str
    #     cooldown_ticks: int
        
    #     def __init__(self, 
    #                 name: str, 
    #                 base_class: 'CharacterClassRole', 
    #                 cooldown_name: str, 
    #                 cooldown_ticks: int):
    #         self.name = name
    #         self.base_class = base_class
    #         self.cooldown_name = cooldown_name
    #         self.cooldown_ticks = cooldown_ticks

    # class FighterSkills(GenericEnumWithAttributes[Skill]):
    #     MIGHTY_KICK: Skill = Skill(
    #         name="shield bash",
    #         base_class=CharacterClassRole.FIGHTER,
    #         cooldown_name="shield_bash",
    #         cooldown_ticks=10
    #     )
    #     DEMORALIZING_SHOUT: Skill = Skill(
    #         name="demoralizing shout",
    #         base_class=CharacterClassRole.FIGHTER,
    #         cooldown_name="demoralizing_shout",
    #         cooldown_ticks=10
    #     )

    # # Example with a dictionary-based configuration
    # class Configuration(GenericEnumWithAttributes[Dict[str, Any]]):
    #     DATABASE: Dict[str, Any] = {
    #         "host": "localhost", 
    #         "port": 5432,
    #         "username": "admin"
    #     }
    #     API: Dict[str, Any] = {
    #         "url": "https://api.example.com", 
    #         "key": "abc123",
    #         "timeout": 30
    #     }