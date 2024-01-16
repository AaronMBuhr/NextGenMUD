from abc import abstractmethod
from typing import Dict, List

class ScheduledAction:
    def __init__(self, on_tick: int, actor: 'Actor', name: str, vars: Dict[str, str], func: callable = None):
        self.actor: 'Actor' = actor
        self.vars: Dict[str, str] = vars
        self.name = name
        self.func = func
        self.on_tick: int = 0

    async def run(self):
        await self.func(self.actor, self.vars)

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
    def find_target_character(self, actor: 'Actor', target_name: str, search_zone=False, search_world=False) -> 'Character':
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
    def add_scheduled_action(self, actor: 'Actor', name: str, vars: Dict[str, str], func: callable = None):
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

