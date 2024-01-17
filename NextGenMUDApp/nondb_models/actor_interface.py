from abc import abstractmethod, ABC
from enum import Enum
from typing import List 
from ..communication import CommTypes


class ActorType(Enum):
    CHARACTER = 1
    OBJECT = 2
    ROOM = 3


class ActorSpawnData:
    def __init__(self, owner: 'Actor', actor_type: ActorType, id: str, quantity: int = 1, respawn_time_min: int = None,
                 respawn_time_max: int = None):
        self.owner = owner
        self.actor_type: ActorType = actor_type
        self.id: str = id
        # self.name: str = name
        self.desired_quantity: int = quantity
        self.respawn_time_min: int = respawn_time_min
        self.respawn_time_max: int = respawn_time_max
        self.spawned : List['Actor'] = []

    def to_dict(self):
        return {
            'actor_type': self.actor_type.name,
            'id': self.id,
            #'name': self.name,
            'quantity': self.quantity,
            'respawn_time_min': self.respawn_time_min,
            'respawn_time_max': self.respawn_time_max,
        }

    @property
    def current_quantity(self):
        return len(self.spawned)    
    
    def do_spawn(self):
        for i in range(self.quantity):
            new_actor = self.owner.spawn_actor(self.actor_type, self.id, self.name)
            self.spawned.append(new_actor)
            new_actor.spawned_by_ = self
            self.owner.zone_.add_actor(new_actor)
            self.owner.zone_.add_actor_to_room(new_actor, self.owner)
            new_actor.zone_ = self.owner.zone_
            new_actor.location_room_ = self.owner
            new_actor.spawn_data = self
            new_actor.on_spawn()




class ActorInterface(ABC):

    @abstractmethod
    def to_dict(self) -> dict:
        raise NotImplementedError
        
    @property
    @abstractmethod
    def art_name(self) -> str:
        raise NotImplementedError
    
    @property
    @abstractmethod
    def art_name_cap(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def from_yaml(self, zone: 'Zone', yaml_data: str) -> 'Actor':
        raise NotImplementedError

    @abstractmethod    
    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: 'GameStateInterface' = None, skip_triggers: bool = False) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def rid(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_vars(self, name: str) -> dict:    
        raise NotImplementedError
    
    @property
    @abstractmethod
    def location_room(self) -> 'Room':
        raise NotImplementedError

    @location_room.setter
    @abstractmethod
    def location_room(self, room: 'Room'):
        raise NotImplementedError    

    @abstractmethod
    def get_temp_var(self, varname, default):
        raise NotImplementedError
    
    @abstractmethod
    def get_perm_var(self, varname, default):
        raise NotImplementedError
    
