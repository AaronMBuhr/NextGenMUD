from abc import abstractmethod
from enum import Enum
from ..basic_types import DescriptiveFlags

class PermanentCharacterFlags(DescriptiveFlags):
    IS_PC = 2**0
    IS_AGGRESSIVE = 2**1
    CAN_DUAL_WIELD = 2**2
    IS_INVISIBLE = 2**3
    SEE_INVISIBLE = 2**4
    DARKVISION = 2**5
    IS_UNDEAD = 2**6
    IS_SENTINEL = 2**7
    NO_WANDER = 2**8
    STATIONARY = 2**9
    EVASIVE = 2**10
    QUEST_GIVER = 2**11
    AGGRESSIVE_IF_ATTACKED = 2**12
    MINDLESS = 2**13
    COWARDLY = 2**14
    PROTECTED = 2**15

    @classmethod
    def field_name_unsafe(cls, idx):
        return ["is pc", "is aggressive", "can dual wield", "is invisible", "see invisible", 
                "darkvision", "is undead", "is sentinel", "no wander", "stationary",
                "evasive", "quest giver", "aggressive if attacked", "mindless", "cowardly", "protected"][idx]


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
    DARKVISION = 2**9
    IS_FROZEN = 2**10

    @classmethod
    def field_name_unsafe(cls, idx):
        return ["is dead", "is sitting", "is sleeping", "is stunned", "is disarmed", "is stealthed", "is hidden",
                "see invisible", "is invisible", "darkvision"][idx]


class GamePermissionFlags(DescriptiveFlags):
    IS_ADMIN = 1
    CAN_INSPECT = 2
    CAN_MODIFY = 4

    @classmethod
    def field_name(cls, idx):
        return ["is admin", "can inspect", "can modify"][idx]


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



class CharacterInterface:

    @abstractmethod
    async def arrive_room(self, room: 'Room'):
        raise NotImplementedError

    @abstractmethod
    def add_cooldown(self, cooldown: 'Cooldown'):
        raise NotImplementedError

    @abstractmethod
    def remove_cooldown(self, cooldown: 'Cooldown'):
        raise NotImplementedError

    @abstractmethod
    def current_cooldowns(self, cooldown_source=None, cooldown_name: str = None):
        raise NotImplementedError
    
    @abstractmethod
    def last_cooldown(self, cooldown_source=None, cooldown_name: str=None):
        raise NotImplementedError

    @abstractmethod
    def get_states(self):
        raise NotImplementedError
    
    @abstractmethod
    def has_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        raise NotImplementedError

    @abstractmethod
    def has_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def has_game_flags(self, flags: GamePermissionFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def add_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def add_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def add_game_flags(self, flags: GamePermissionFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def remove_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def remove_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    def remove_game_flags(self, flags: GamePermissionFlags) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_in_room(self, room: 'Room'):
        raise NotImplementedError
    
