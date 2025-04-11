from typing import Dict, List
from .actor_interface import ActorType, ActorSpawnData
from .actors import Actor
from ..communication import CommTypes
from ..structured_logger import StructuredLogger
from .object_interface import ObjectInterface
from .room_interface import RoomInterface
from .triggers import Trigger
from ..utility import replace_vars, firstcap, evaluate_functions_in_line

class Room(Actor, RoomInterface):
    from .world import Zone
    
    def __init__(self, id: str, zone: Zone, name: str = "", create_reference=False):
        super().__init__(ActorType.ROOM, id, name=name, create_reference=create_reference)
        self.definition_zone = zone
        self.exits = {}
        self.description = ""
        self.zone = None
        self.characters = []
        self.contents = []
        self._location_room = self
        self.triggers_by_type = {}
        self.spawn_data = []

    def to_dict(self):
        return {
            'ref#': self.reference_number,
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'zone': self.zone.id if self.zone else None,
            'exits': self.exits,
            'triggers': self.triggers_by_type,
            # Convert complex objects to a serializable format, if necessary
            # 'zone': self.zone_.to_dict() if self.zone_ else None,
            # 'characters': [c.to_dict() for c in self.characters_],
            # 'objects': [o.to_dict() for o in self.contents_],
        }
    
    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def __str__(self):
        return self.__repr__()

    def from_yaml(self, zone, yaml_data: str):
        logger = StructuredLogger(__name__, prefix="Room.from_yaml()> ")
        try:
            self.name = yaml_data['name']
            self.description = yaml_data['description']
            self.zone = zone

            for direction, exit_info in yaml_data['exits'].items():
                # logger.debug3(f"loading direction: {direction}")
                self.exits[direction] = exit_info['destination']

            if 'characters' in yaml_data:
                logger.debug3("characters found")
                for character in yaml_data['characters']:
                    logger.debug3(f"character: {character}")
                    if not "." in character['id']:
                        spawn_id = self.zone.id + "." + character['id']
                    else:
                        spawn_id = character['id']
                    logger.debug(f"spawn_id: {spawn_id}")
                    # print(repr(character))
                    respawn = ActorSpawnData(self, ActorType.CHARACTER, spawn_id, character['quantity'],
                                                character['respawn time min'], character['respawn time max'])
                    self.spawn_data.append(respawn)

            if 'triggers' in yaml_data:
                # print(f"triggers: {yaml_data['triggers']}")
                # raise NotImplementedError("Triggers not implemented yet.")
                # for trigger_type, trigger_info in yaml_data['triggers'].items():
                #     # logger.debug3(f"loading trigger_type: {trigger_type}")
                #     if not trigger_type in self.triggers_by_type_:
                #         self.triggers_by_type_[trigger_type] = []
                #     self.triggers_by_type_[trigger_type] += trigger_info
                for trig in yaml_data['triggers']:
                    # logger.debug3(f"loading trigger_type: {trigger_type}")
                    new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                    # print(new_trigger.to_dict())
                    if not new_trigger.trigger_type_ in self.triggers_by_type:
                        self.triggers_by_type[new_trigger.trigger_type_] = []
                    self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
        except:
            logger.error("Exception in Room.from_yaml()")
            logger.error("yaml_data: " + str(yaml_data))
            raise

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] =None, already_substituted: bool = False,
                   game_state: 'GameStateInterface' = None, skip_triggers: bool = False) -> bool:
        logger = StructuredLogger(__name__, prefix="Room.echo()> ")
        if text == False:
            raise Exception("text False")
        logger.debug3(f"text before: {text if text is not None else 'None'}")
        if not already_substituted and text is not None:
            text = evaluate_functions_in_line(replace_vars(text, vars), vars, game_state)
        logger.debug3(f"text after: {text if text is not None else 'None'}")
        logger.debug3(f"checking characters: {self.characters}")
        # if len(self.characters_) > 0:
        #     raise Exception("we found a character!")
        for c in self.characters:
            logger.debug3(f"checking character {c.name}")
            if exceptions is None or c not in exceptions:
                logger.debug3(f"sending '{text}' to {c.name}")
                await c.echo(text_type, text, vars, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        logger.debug3(f"running super, text: {text if text is not None else 'None'}")
        # Run Actor.echo to send the message to the room itself if it has a connection
        return await super().echo(text_type, text, vars, exceptions, already_substituted, game_state, skip_triggers)

    def remove_character(self, character: 'Character'):
        self.characters.remove(character)
        character.location_room = None

    def add_character(self, character: 'Character'):
        self.characters.append(character)
        character.location_room = self

    def remove_object(self, obj: ObjectInterface):
        self.contents.remove(obj)
        obj.location_room = None

    def add_object(self, obj: ObjectInterface):
        self.contents.append(obj)
        obj.location_room = self

    @property
    def art_name(self):
        return self.name
    
    @property
    def art_name_cap(self):
        return firstcap(self.name)
    
    def get_characters(self) -> List['Character']:
        return self.characters

    @property
    def location_room(self) -> 'Room':
        return self

    @location_room.setter
    def location_room(self, room: 'Room'):
        raise Exception("can't set location_room for a room")
        

