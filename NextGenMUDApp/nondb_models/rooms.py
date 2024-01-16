from typing import Dict, List
from .actor_interface import ActorType, ActorSpawnData
from .actors import Actor
from ..communication import CommTypes
from custom_detail_logger import CustomDetailLogger
from .object_interface import ObjectInterface
from .room_interface import RoomInterface
from .triggers import Trigger
from ..utility import replace_vars

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
        self.location_room = self
        self.triggers_by_type = {}
        self.spawn_data = []

    def to_dict(self):
        return {
            'ref#': self.reference_number,
            'id': self.id,
            'name': self.name_,
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
        self.name_ = yaml_data['name']
        self.description = yaml_data['description']
        self.zone = zone

        for direction, exit_info in yaml_data['exits'].items():
            # logger.debug3(f"loading direction: {direction}")
            self.exits[direction] = exit_info['destination']

        if 'characters' in yaml_data:
            for character in yaml_data['characters']:
                if not "." in character['id']:
                    spawn_id = self.zone.id + "." + character['id']
                else:
                    spawn_id = character['id']
                print(repr(character))
                respawn = ActorSpawnData(ActorType.CHARACTER, spawn_id, character['quantity'],
                                            character['respawn time min'], character['respawn time max'])

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
                print(new_trigger.to_dict())
                if not new_trigger.trigger_type_ in self.triggers_by_type:
                    self.triggers_by_type[new_trigger.trigger_type_] = []
                self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)


    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] =None, already_substituted: bool = False,
                   game_state: 'GameStateInterface' = None, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Room.echo()> ")
        if text == False:
            raise Exception("text False")
        logger.critical("text before " + text)
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical("text after " + text)
        logger.debug3(f"checking characters: {self.characters}")
        # if len(self.characters_) > 0:
        #     raise Exception("we found a character!")
        for c in self.characters:
            logger.debug3(f"checking character {c.name_}")
            if exceptions is None or c not in exceptions:
                logger.debug3(f"sending '{text}' to {c.name_}")
                await c.echo(text_type, text, vars, exceptions, already_substituted=True,game_state=game_state, skip_triggers=skip_triggers)
        logger.debug3("running super, text: " + text)
        await super().echo(text_type, text, vars, exceptions, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        return True

    def remove_character(self, character: 'Character'):
        self.characters.remove(character)
        character.set_in_room(None)

    def add_character(self, character: 'Character'):
        self.characters.append(character)
        character.set_in_room(self)

    def remove_object(self, obj: ObjectInterface):
        self.contents.remove(obj)
        obj.set_in_room(None)

    def add_object(self, obj: ObjectInterface):
        self.contents.append(obj)
        obj.set_in_room(self)

    @property
    def art_name(self):
        return self.name
    
    @property
    def art_name_cap(self):
        return firstcap(self.name)
    
