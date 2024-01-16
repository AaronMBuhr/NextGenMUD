from abc import abstractmethod
from typing import Dict 
from .nondb_models.actors import Actor, Character, Room, Object, EquipLocation
from .world import Zone


    

class ScheduledAction:
    def __init__(self, actor: Actor, name: str, vars: Dict[str, str], func: callable = None):
        self.actor_: Actor = actor
        self.vars_: Dict[str, str] = vars
        self.name_ = name
        self.func_ = func

    async def run(self):
        await self.func_(self.actor_, self.vars_)

class GameStateInterface:

    @abstractmethod
    def find_target_character(self, actor: Actor, target_name: str, search_zone=False, search_world=False) -> Character:
        pass

    @abstractmethod
    def find_all_characters(self, actor: Actor, target_name: str) -> str:
        pass

    @abstractmethod
    def find_target_room(self, actor: Actor, target_name: str, start_zone: Zone) -> Room:
        pass

    @abstractmethod
    def find_target_object(self, target_name: str, actor: Actor = None, equipped: Dict[EquipLocation, Object] = None, 
                           start_room: Room = None, start_zone: Zone = None, search_world=False) -> Object:
        pass

    @abstractmethod
    def add_scheduled_action(self, actor: Actor, name: str, vars: Dict[str, str], func: callable = None):
        pass


