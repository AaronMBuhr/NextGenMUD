from abc import abstractmethod
from ..communication import CommTypes
from ..core import FlagBitmap
from custom_detail_logger import CustomDetailLogger
from enum import Enum, auto
import json
from nondb_models.triggers import TriggerType


def replace_vars(script: str, vars: dict) -> str:
    for var, value in vars.items():
        script = script.replace(f"%{var}", value)
    return script

class ActorType(Enum):
    CHARACTER = 1
    OBJECT = 2
    ROOM = 3

class Actor:
    references_ = {}  # Class variable for storing references
    current_reference_num_ = 1  # Class variable for tracking the current reference number

    def __init__(self, actor_type: ActorType, id: str, name: str = ""):
        self.actor_type_ = actor_type
        self.id_ = id
        self.name_ = name
        self.location_room_ = None
        self.triggers_by_type_ = {}
        reference_prefix = self.actor_type_.name[0]  # First character of ActorType
        self.reference_number_ = reference_prefix + str(Actor.current_reference_num_)
        Actor.references_[self.reference_number_] = self
        Actor.current_reference_num_ += 1

    def to_dict(self):
        return {'actor_type': self.actor_type_.name, 'id': self.id_, 'name': self.name_, 'reference_number': self.reference_number_}

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    @classmethod
    def getReference(cls, reference_number):
        try:
            return cls.references_[reference_number]
        except KeyError:
            return None
    
    @classmethod
    def dereference(cls, reference_number):
        if reference_number in cls.references_:
            del cls.references_[reference_number]

    def dereference(self):
        Actor.dereference_(self.reference_number_)

    async def sendText(self, text_type: CommTypes, text: str):
        pass

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Actor.echo()> ")
        logger.debug(f"text: {text}")
        logger.debug(f"vars: {vars}")
        if vars:
            text = replace_vars(text, vars)
        logger.debug(f"formatted text: {text}")
        # check room triggers
        if exceptions and self in exceptions:
            return
        for trigger_type in [ TriggerType.CATCH_ANY ]:
            if trigger_type in self.triggers_by_type_:
                for trigger in self.triggers_by_type_[trigger_type]:
                    await trigger.run(self, text, vars)


class Room(Actor):
    
    def __init__(self, id: str, zone=None, name: str = ""):
        super().__init__(ActorType.ROOM, id, name)
        self.exits_ = {}
        self.description_ = ""
        self.zone_ = None
        self.characters_ = []
        self.objects_ = []
        self.location_room_ = self

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

    def from_yaml(self, zone, yaml_data: str):
        self.name_ = yaml_data['name']
        self.description_ = yaml_data['description']
        self.zone_ = zone

        for direction, exit_info in yaml_data['exits'].items():
            # logger.debug(f"loading direction: {direction}")
            self.exits_[direction] = exit_info['destination']

        for trigger_type, trigger_info in yaml_data['triggers'].items():
            # logger.debug(f"loading trigger_type: {trigger_type}")
            if not trigger_type in self.triggers_by_type_:
                self.triggers_by_type_[trigger_type] = []
            self.triggers_by_type_[trigger_type] += trigger_info


    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Room.echo()> ")
        super().echo(self, text_type, text, vars, exceptions)
        for c in self.characters_:
            logger.debug(f"checking character {c.name_}")
            if exceptions is None or c not in exceptions:
                logger.debug(f"sending text to {c.name_}")
                await c.echo(text_type, text, vars, exceptions)

    def removeCharacter(self, character: 'Character'):
        self.characters_.remove(character)

    def addCharacter(self, character: 'Character'):
        self.characters_.append(character)


class CharacterFlags(Enum):
    IS_PC = 2^0

class Character(Actor):
    
    def __init__(self, id: str, name: str = ""):
        super().__init__(ActorType.CHARACTER, id, name)
        self.attributes_ = {}
        self.classes_ = {}
        self.inventory_ = {}
        self.character_flags_ = FlagBitmap()
        self.connection_ = None
    
    async def sendText(self, text_type: CommTypes, text: str):
        logger = CustomDetailLogger(__name__, prefix="Character.sendText()> ")
        logger.debug(f"sendText: {text}")
        logger.debug(f"exceptions: {exceptions}")
        if self.connection_:
            logger.debug(f"connection exists, sending text to {self.name_}")
            await self.connection_.send(text_type, text)
            logger.debug("text sent")
        else:
            logger.debug("no connection")

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Character.echo()> ")
        super().echo(self, text_type, text, vars, exceptions)
        if exceptions and self in exceptions:
            return
        await self.sendText(text_type, text, exceptions)

class Object(Actor):

    def __init__(self, id: str, name: str = ""):
        super().__init__(ActorType.OBJECT, id, name)
        self.name_ = ""
        self.location_inventory_ = None
        self.location_container_ = None
        self.attributes_ = {}
        self.object_flags_ = FlagBitmap()

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, exceptions=None):
        logger = CustomDetailLogger(__name__, prefix="Object.echo()> ")
        super().echo(self, text_type, text, vars, exceptions)

# class Zone:
#     def __init__(self, id):
#         self.id_ = id
#         self.name_ = ""
#         self.rooms_ = {}
#         self.actors_ = {}
#         self.description_ = ""

#     def to_dict(self):
#         return {
#             'id': self.id_,
#             'name': self.name_,
#             'rooms': {room_id: room.to_dict() for room_id, room in self.rooms_.items()},
#             'actors': self.actors_,  # Make sure this is also serializable
#             'description': self.description_
#         }

#     def __str__(self):
#         return json.dumps(self.to_dict(), indent=4)

