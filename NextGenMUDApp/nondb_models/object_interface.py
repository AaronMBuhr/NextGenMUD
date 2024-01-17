from abc import abstractmethod
from .actor_interface import ActorInterface
from ..basic_types import DescriptiveFlags
from .character_interface import EquipLocation


class ObjectFlags(DescriptiveFlags):
    IS_ARMOR = 2**0
    IS_WEAPON = 2**1
    IS_CONTAINER = 2**2
    IS_CONTAINER_LOCKED = 2**3

    @classmethod
    def field_name(cls, idx):
        return ["armor", "weapon", "container", "container-locked"][idx]

class ObjectInterface(ActorInterface):

    @abstractmethod
    def set_in_actor(self, actor: ActorInterface):
        raise NotImplementedError
    
    @abstractmethod
    def set_equip_location(self, loc: EquipLocation):
        raise NotImplementedError

