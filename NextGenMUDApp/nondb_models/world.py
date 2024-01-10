from ..constants import Constants
from enum import Enum
import json
from .actors import Actor, Character, Room, Object

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

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def __str__(self):
        return self.__repr__()




class WorldDefinition:
    def __init__(self) -> None:
        self.zones_ = {}
        self.characters_ = {}
        self.objects_ = {}

def find_character_definition(self, character_id_or_name: str) -> Character:
    if character_id_or_name in self.characters_:
        return self.characters_[character_id_or_name]
    for character in operating_state.world_definition_.characters_:
        if character.name_.startswith(character_id_or_name):
            return character
    return None

