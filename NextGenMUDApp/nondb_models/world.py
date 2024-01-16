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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'rooms': {room_id: room.to_dict() for room_id, room in self.rooms.items()},
            'actors': self.actors,  # Make sure this is also serializable
            'description': self.description
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
        self.characters_ = {}
        self.objects_ = {}

    def find_character_definition(self, character_id_or_name: str) -> 'Character':
        if character_id_or_name in self.characters_:
            return self.characters_[character_id_or_name]
        print("YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY")
        print(type(self.characters_))
        for character in self.characters_:
            print(type(character))
            if character.name_.startswith(character_id_or_name):
                return character
        return None

    def find_object_definition(self, object_id_or_name: str) -> 'Object':
        if object_id_or_name in self.objects_:
            return self.objects_[object_id_or_name]
        for object_id, object in self.objects_.items():
            if object.id_.startswith(object_id_or_name):
                return object
            pieces = object.name_.split()
            for piece in pieces:
                if piece.startswith(object_id_or_name):
                    return object
        return None
    
