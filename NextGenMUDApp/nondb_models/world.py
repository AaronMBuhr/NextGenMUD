from . import Constants
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

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4)


def find_target_character(actor: Actor, target_name: str) -> Character:
    if target_name[0] == Constants.REFERENCE_SYMBOL:
        return Actor.getReference(target_name[1:])
            
    # Determine the starting point
    start_room = None
    if isinstance(actor, Character):
        start_room = actor.location_room_
    elif isinstance(actor, Room):
        start_room = actor
    elif isinstance(actor, Object) and actor.location_room_:
        start_room = actor.location_room_

    if not start_room:
        return None

    # Parse the target name and target number
    target_number = 1
    if '#' in target_name:
        parts = target_name.split('#')
        target_name = parts[0]
        target_number = int(parts[1])

    candidates = []

    # Helper function to add candidates from a room
    def add_candidates_from_room(room):
        for char in room.characters_:
            if char.name_.startswith(target_name) or char.id_.startswith(target_name):
                candidates.append(char)

    # Search in the current room
    add_candidates_from_room(start_room)

    # If not found in the current room, search in the current zone
    if len(candidates) < target_number and isinstance(start_room, Room) and start_room.zone_:
        for room in start_room.zone_.rooms_.values():
            add_candidates_from_room(room)

    # If still not found, search across all zones
    if len(candidates) < target_number:
        for zone in operating_state.zones_.values():
            for room in zone.rooms_.values():
                add_candidates_from_room(room)

    # Return the target character
    if 0 < target_number <= len(candidates):
        return candidates[target_number - 1]

    return None


def find_all_characters(actor: Actor, target_name: str) -> str:
    # Determine the starting point
    start_room = None
    if isinstance(actor, Character):
        start_room = actor.location_room_
    elif isinstance(actor, Room):
        start_room = actor
    elif isinstance(actor, Object) and actor.location_room_:
        start_room = actor.location_room_

    if not start_room:
        return ""

    matching_characters = []

    # Helper function to add matching characters from a room
    def add_matching_characters_from_room(room):
        for char in room.characters_:
            if char.name_.startswith(target_name) or char.id_.startswith(target_name):
                matching_characters.append(f"{char.name_} {room.name_}")

    # Search in the current room
    add_matching_characters_from_room(start_room)

    # Search in the current zone
    if isinstance(start_room, Room) and start_room.zone_:
        for room in start_room.zone_.rooms_.values():
            add_matching_characters_from_room(room)

    # Search across all zones
    for zone in operating_state.zones_.values():
        for room in zone.rooms_.values():
            add_matching_characters_from_room(room)

    # Format and return the results
    return "\n".join(matching_characters)
