from abc import abstractmethod
from enum import Enum

class TriggerType(Enum):
    CATCH_ANY = 1
    CATCH_SAY = 2
    CATCH_TELL = 3
    TIMER_TICK = 4
    CATCH_LOOK = 5

    def __str__(self):
        return "TriggerType." + self.name

class TriggerInterface:

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'GameStateInterface'=None) -> bool:
        raise Exception("Trigger.run() must be overridden.")
