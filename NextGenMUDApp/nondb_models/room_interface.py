from abc import abstractmethod
from typing import List
from .actor_interface import ActorInterface
from ..basic_types import DescriptiveFlags


class RoomFlags(DescriptiveFlags):
    DARK = 2**0
    NO_MOB = 2**1
    INDOORS = 2**2
    NO_MAGIC = 2**3
    NO_SUMMON = 2**4
    FLIGHT_NEEDED = 2**5
    UNDERWATER = 2**6


class RoomInterface:

    @abstractmethod
    def remove_character(self, character: 'Character'):
        raise NotImplementedError
        
    @abstractmethod
    def add_character(self, character: 'Character'):
        raise NotImplementedError

    @abstractmethod
    def remove_object(self, obj: 'Object'):
        raise NotImplementedError

    @abstractmethod
    def add_object(self, obj: 'Object'):
        raise NotImplementedError
    
    @abstractmethod
    def get_characters(self) -> List['Character']:
        raise NotImplementedError
    
