from abc import abstractmethod
from ..communication import CommTypes
from ..core import FlagBitmap
from custom_detail_logger import CustomDetailLogger
from enum import Enum, auto
import json

class ActorType(Enum):
    CHARACTER = 1
    OBJECT = 2
    ROOM = 3


class Actor:

    def __init__(self, actor_type: ActorType, id: str):
        self.actor_type_ = actor_type
        self.id_ = id

    # def __str__(self):
    #     return self.id_

    # def __repr__(self):
    #     return self.id_

    def to_dict(self):
        return({'actor_type': self.actor_type_.name, 'id': self.id_})

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    @property
    def actor_type(self):
        return self.actor_type_
    
    @actor_type.setter
    def actor_type(self, value):
        self.actor_type_ = value

    @property
    def id(self):
        return self.id_

    @id.setter
    def id(self, value):
        self.id_ = value

    @abstractmethod
    async def sendText(self, text_type: CommTypes, text: str, exceptions=None):
        pass


class ExitDirectionsEnum(Enum):
    NORTH = 1
    SOUTH = 2
    EAST = 3
    WEST = 4
    UP = 5
    DOWN = 6
    NORTHEAST = 7
    NORTHWEST = 8
    SOUTHEAST = 9
    SOUTHWEST = 10
    IN = 11
    OUT = 12

class ExitDirections:
    def __init__(self, direction_list):
        self.direction_list = direction_list

    def __getattr__(self, name):
        if name in ExitDirectionsEnum.__members__:
            enum_member = ExitDirectionsEnum[name]
            return self.direction_list[enum_member.value - 1]
        raise AttributeError(f"'ExitDirections' object has no attribute '{name}'")


class Room(Actor):
    
    def __init__(self, id, zone=None):
        super().__init__(ActorType.ROOM, id)
        self.exits_ = {}
        self.description_ = ""
        self.zone_ = None
        self.characters_ = []
        self.objects_ = []

    def to_dict(self):
        return {
            'id': self.id_,
            'description': self.description_,
            'exits': self.exits_,
            # Convert complex objects to a serializable format, if necessary
            # 'zone': self.zone_.to_dict() if self.zone_ else None,
            # 'characters': [c.to_dict() for c in self.characters_],
            # 'objects': [o.to_dict() for o in self.objects_],
        }

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4)

    @property
    def exits(self):
        return self.exits_

    @exits.setter
    def exits(self, value):
        self.exits_ = value
    
    @property
    def description(self):
        return self.description_
    
    @description.setter
    def description(self, value):
        self.description_ = value

    async def sendText(self, text_type: CommTypes, text: str, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Room.sendText()> ")
        logger.debug(f"sendText: {text}")
        logger.debug(f"exceptions: {exceptions}")
        for c in self.characters_:
            logger.debug(f"checking character {c.name_}")
            if exceptions is None or c not in exceptions:
                logger.debug(f"sending text to {c.name_}")
                await c.sendText(text_type, text)

    def removeCharacter(self, character: 'Character'):
        self.characters_.remove(character)

    def addCharacter(self, character: 'Character'):
        self.characters_.append(character)


class CharacterFlags(Enum):
    IS_PC = 2^0

class Character(Actor):
    
    def __init__(self, id):
        super().__init__(ActorType.CHARACTER, id)
        self.name_ = ""
        self.location_room_ = None
        self.attributes_ = {}
        self.classes_ = {}
        self.inventory_ = {}
        self.character_flags_ = FlagBitmap()
        self.connection_ = None
    
    @property
    def location_room(self):
        return self.location_room_
    
    @location_room.setter
    def location_room(self, value):
        self.location_room_ = value

    async def sendText(self, text_type: CommTypes, text: str, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Character.sendText()> ")
        logger.debug(f"sendText: {text}")
        logger.debug(f"exceptions: {exceptions}")
        if self.connection_:
            logger.debug("connection exists")
            if exceptions is None or self not in exceptions:
                logger.debug(f"sending text to {self.name_}")
                await self.connection_.send(text_type, text)
                logger.debug("text sent")
        else:
            logger.debug("no connection")


class Zone:
    def __init__(self, id):
        self.id_ = id
        self.name_ = ""
        self.rooms_ = {}
        self.actors_ = {}
        self.description_ = ""

    def to_dict(self):
        return {
            'id': self.id_,
            'name': self.name_,
            'rooms': {room_id: room.to_dict() for room_id, room in self.rooms_.items()},
            'actors': self.actors_,  # Make sure this is also serializable
            'description': self.description_
        }

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4)

