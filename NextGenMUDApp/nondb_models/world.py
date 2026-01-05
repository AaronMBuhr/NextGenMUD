from ..constants import Constants
from enum import Enum
import json

class Zone:
    def __init__(self, id):
        self.id = id
        self.name = ""       
        self.rooms = {}
        self.actors = {}
        self.description = ""
        self.common_knowledge = {}  # id -> knowledge content for LLM NPCs

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'rooms': {room_id: room.to_dict() for room_id, room in self.rooms.items()},
            'actors': self.actors,  # Make sure this is also serializable
            'description': self.description,
            'common_knowledge': self.common_knowledge,
        }

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def __str__(self):
        return self.__repr__()


class WorldDefinition:
    def __init__(self) -> None:
        self.zones = {}
        self.characters = {}
        self.objects = {}

    def find_character_definition(self, character_id_or_name: str) -> 'Character':
        if "." in character_id_or_name:
            zone_id, character_id = character_id_or_name.split(".")
            if zone_id in self.zones.keys():
                for c,cd in self.characters.items():
                    if cd.id == character_id and cd.definition_zone_id == zone_id:
                        return cd
        else:
            zone_id = None
            for c,cd in self.characters.items():
                if cd.id == character_id_or_name:
                    return cd
        for character, char_data in self.characters.items():
            if character.startswith(character_id_or_name) and (zone_id is None or char_data.zone == zone_id):
                return character
        return None

    def find_object_definition(self, object_id_or_name: str) -> 'Object':
        if object_id_or_name in self.objects:
            return self.objects[object_id_or_name]
        if "." not in object_id_or_name:
            for zone_id in self.zones.keys():
                if f"{zone_id}.{object_id_or_name}" in self.objects:
                    return self.objects[f"{zone_id}.{object_id_or_name}"]
            for object_id, object in self.objects.items():
                pieces = object_id.split(".")
                if pieces[1].startswith(object_id_or_name):
                    return object
                pieces = object.name.split()
                for piece in pieces:
                    if piece.startswith(object_id_or_name):
                        return object
        else:
            for object_id, object in self.objects.items():
                if object_id.startswith(object_id_or_name):
                    return object
                pieces = object.name.split()
                for piece in pieces:
                    if piece.startswith(object_id_or_name):
                        return object
        return None
    
