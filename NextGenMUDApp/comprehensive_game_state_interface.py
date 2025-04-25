from abc import abstractmethod
from typing import Any, Dict, List, Callable

class EventType:
    COMBAT_TICK = "combat_tick"
    COOLDOWN_OVER = "cooldown_over"
    STATE_PULSE = "state_pulse"
    CAST_FINISHED = "cast_finished"
    STATE_END = "state_end"

class ScheduledEvent:
    def __init__(self, on_tick: int, event_type: EventType, subject: Any, name: str, vars: Dict[str, Any], 
                 func: Callable[[Any, int, 'GameStateInterface', Dict[str, Any]], Any] = None):
        self.event_type: EventType = event_type
        self.subject: Any = subject
        self.vars: Dict[str, Any] = vars
        self.name = name
        self.func = func
        self.on_tick: int = 0

    async def run(self, current_tick: int, game_state: 'GameStateInterface'):
        if self.func:
            await self.func(self.subject, current_tick, game_state, self.vars)

class GameStateInterface:

    _instance: 'GameStateInterface' = None

    @classmethod
    def set_instance(cls, instance: 'GameStateInterface'):
        cls._instance = instance

    @classmethod
    def get_instance(cls) -> 'GameStateInterface':
        if not cls._instance:
            from .comprehensive_game_state import GameState
            cls._instance = GameState()
        return cls._instance

    @abstractmethod
    def find_target_character(self, actor: 'Actor', target_name: str, search_zone=False, search_world=False, exclude_initiator=True) -> 'Character':
        raise NotImplementedError

    @abstractmethod
    def find_all_characters(self, actor: 'Actor', target_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def find_target_room(self, actor: 'Actor', target_name: str, start_zone: 'Zone') -> 'Room':
        raise NotImplementedError

    @abstractmethod
    def find_target_object(self, target_name: str, actor: 'Actor' = None, equipped: Dict['EquipLocation', 'Object'] = None, 
                           start_room: 'Room' = None, start_zone: 'Zone' = None, search_world=False) -> 'Object':
        raise NotImplementedError

    @abstractmethod
    def add_scheduled_event(self, type: EventType, subject: Any, name: str, scheduled_tick: int = None, 
                            in_ticks: int = None, vars: Dict[str, Any] = None, 
                            func: Callable[[Any, int, 'GameStateInterface', Dict[str, Any]], Any] = None) -> 'ScheduledEvent':
        raise NotImplementedError

    @abstractmethod
    def remove_scheduled_event(self, event_type: EventType, subject: Any, tick: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_scheduled_event(self, scheduled_event: 'ScheduledEvent') -> None:
        raise NotImplementedError

    @abstractmethod
    def get_zone_by_id(self, zone_id: str) -> 'Zone':
        raise NotImplementedError

    @abstractmethod
    def add_character_fighting(self, character: 'Character'):
        raise NotImplementedError
    
    @abstractmethod
    def get_characters_fighting(self) -> List['Character']:
        raise NotImplementedError
    
    @abstractmethod
    def remove_character_fighting(self, character: 'Character'):
        raise NotImplementedError
    
    @abstractmethod
    def get_world_definition() -> 'WorldDefinition':
        raise NotImplementedError
    
    @abstractmethod
    def respawn_character(self, owner: 'Actor', vars: dict):
        raise NotImplementedError
    
    @abstractmethod
    def remove_character(self, character: 'Character'):
        raise NotImplementedError

    @abstractmethod
    def get_temp_var(cls, source_actor_ptr: str, var_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_perm_var(cls, source_actor_ptr: str, var_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_world_definition(self) -> 'WorldDefinition':
        raise NotImplementedError
    
    @abstractmethod
    def can_see(char: 'Character', target: 'Character') -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_current_tick(self) -> int:
        raise NotImplementedError
