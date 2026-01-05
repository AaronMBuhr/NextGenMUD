from abc import abstractmethod
from .actor_interface import ActorInterface
from ..basic_types import DescriptiveFlags
from .character_interface import EquipLocation


class ObjectFlags(DescriptiveFlags):
    IS_ARMOR = 2**0
    IS_WEAPON = 2**1
    IS_CONTAINER = 2**2
    IS_CONTAINER_LOCKED = 2**3  # Legacy - use IS_LOCKED instead
    NO_TAKE = 2**4              # Cannot be picked up
    IS_STATIC = 2**5            # Part of the room, cannot be moved
    IS_OPENABLE = 2**6          # Can be opened/closed (doors, chests)
    IS_CLOSED = 2**7            # Currently closed
    IS_LOCKABLE = 2**8          # Can be locked/unlocked
    IS_LOCKED = 2**9            # Currently locked
    IS_HIDDEN = 2**10           # Hidden until searched/revealed
    IS_DOOR = 2**11             # Is a door between rooms
    IS_CONSUMABLE = 2**12       # Can be consumed (eaten, drunk, used up)
    IS_POTION = 2**13           # Is a potion (quaff command)
    IS_BANDAGE = 2**14          # Is a bandage (apply command)
    IS_FOOD = 2**15             # Is food (eat command)

    @classmethod
    def field_name(cls, idx):
        return ["armor", "weapon", "container", "container-locked", "no-take", "static",
                "openable", "closed", "lockable", "locked", "hidden", "door",
                "consumable", "potion", "bandage", "food"][idx]

class ObjectInterface(ActorInterface):

    @abstractmethod
    def set_in_actor(self, actor: ActorInterface):
        raise NotImplementedError
    
    @abstractmethod
    def set_equip_location(self, loc: EquipLocation):
        raise NotImplementedError

