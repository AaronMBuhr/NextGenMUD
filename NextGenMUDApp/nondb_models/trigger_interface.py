from abc import abstractmethod
from enum import Enum
from ..basic_types import DescriptiveFlags

class TriggerType(Enum):
    CATCH_ANY = 1
    CATCH_SAY = 2
    CATCH_TELL = 3
    TIMER_TICK = 4
    CATCH_LOOK = 5

    def __str__(self):
        return "TriggerType." + self.name

class TriggerFlags(DescriptiveFlags):
    ONLY_WHEN_PC_ROOM = 2**0
    ONLY_WHEN_PC_ZONE = 2**1

    @classmethod
    def field_name_unsafe(cls, idx):
        return ["only when pc is in room", "only when pc is in zone"][idx]
    
    @classmethod
    def from_names(cls, name) -> 'TriggerFlags':
        flags = TriggerFlags(0)
        flag_names = name.split(",")
        for flag_name in flag_names:
            enum_name = flag_name.upper().replace(" ", "_")
            flag_value = getattr(TriggerFlags, enum_name, None)
            if flag_value is not None:
                flags |= flag_value
        return flags
    
class TriggerInterface:

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'GameStateInterface'=None) -> bool:
        raise Exception("Trigger.run() must be overridden.")

    @abstractmethod
    def reset_timer(self):
        pass # most triggers this does nothing

    @abstractmethod
    def are_flags_set(self, flags: TriggerFlags) -> bool:
        raise Exception("Trigger.are_flags_set() must be overridden.")
    