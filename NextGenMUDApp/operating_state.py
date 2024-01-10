from custom_detail_logger import CustomDetailLogger
from django.conf import settings
import json
from .communication import Connection
import os
import sys
import yaml
from yaml_dumper import YamlDumper
from .nondb_models.actors import Character, Actor, Room, Object
from typing import List, Dict
import copy
from .nondb_models.world import WorldDefinition, Zone
from .constants import Constants

class OperatingState:

    def __init__(self):
        self.world_definition_: WorldDefinition = WorldDefinition()
        self.characters_: List[Character] = []
        self.players_ : List[Character] = []
        self.connections_ : List[Connection] = []
        self.characters_fighting_ : List[Character] = []
        self.zones_ = {}

    def Initialize(self):
        from .nondb_models.actors import Character, Room #, Zone
        from .nondb_models.world import Zone
        logger = CustomDetailLogger(__name__, prefix="Initialize()> ")

        # Zones
        logger.info("Loading zones...")
        zones_file_path = os.path.join(settings.BASE_DIR, 'NextGenMUDApp', 'world_data', 'zones.yaml')
        with open(zones_file_path, "r") as yf:
            yaml_data = yaml.safe_load(yf)

        # logger.debug(f"zone yaml_data: {yaml_data}")
        self.world_definition_.zones_ = {}
        for zone_id, zone_info in yaml_data['ZONES'].items():
            logger.info(f"Loading zone_id: {zone_id}")
            new_zone = Zone(zone_id)
            new_zone.name_ = zone_info['name']
            # logger.debug(f"new_zone.name_: {new_zone.name_}")
            new_zone.description_ = zone_info['description']

            logger.info(f"Loading rooms...")
            for room_id, room_info in zone_info['rooms'].items():
                logger.info(f"Loading room_id: {room_id}")
                new_room = Room(room_id)
                new_room.from_yaml(new_zone, room_info)
                new_zone.rooms_[room_id] = new_room
            logger.info("Rooms loaded")

            self.world_definition_.zones_[zone_id] = new_zone
        logger.info("Zones loaded")
        if self.world_definition_.zones_ == {}:
            raise Exception("No zones loaded.")
        if self.world_definition_.zones_ == None:
            raise Exception("Zones is NONE.")
        
        # Characters
        logger.info("Loading characters...")
        characters_file_path = os.path.join(settings.BASE_DIR, 'NextGenMUDApp', 'world_data', 'characters.yaml')
        with open(characters_file_path, "r") as yf:
            yaml_data = yaml.safe_load(yf)
        # print(yaml_data)
        # for charzone in yaml_data["ZONES"]:
        #     for chardef in yaml_data["ZONES"]["CHARACTERS"]:
        #         ch = Character(chardef["id"], charzone)
        #         ch.from_yaml(chardef)
        #         self.world_definition_.characters_[ch.id_] = ch
        for zonedef in yaml_data["CHARACTERS"]:
            for chardef in zonedef["characters"]:
                ch = Character(chardef["id"], zonedef["zone"])
                ch.from_yaml(chardef)
                self.world_definition_.characters_[ch.id_] = ch

        logger.info("Characters loaded")

        logger.info("Preparing world...")
        # copy to operating data
        self.zones_ = copy.deepcopy(self.world_definition_.zones_)
        # print("init zones")
        for zone, zone_data in self.zones_.items():
            for room, room_data in zone_data.rooms_.items():
                room_data.create_reference()
                # print(f"room_data: {room_data}")
                for trig_type in room_data.triggers_by_type_:
                    for trig in room_data.triggers_by_type_[trig_type]:
                        logger.debug3("enabling trigger")
                        trig.enable()

        logger.info("World prepared")
        

def find_target_character(actor: Actor, target_name: str) -> Character:
    if target_name[0] == Constants.REFERENCE_SYMBOL:
        return Actor.get_reference(target_name[1:])
            
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


def find_target_room(actor: Actor, target_name: str, start_zone: Zone) -> str:
    if target_name[0] == Constants.REFERENCE_SYMBOL:
        return Actor.get_reference(' '.join(target_name[1:]))
    for room in start_zone.rooms_.values():
        if room.name_.startswith(target_name) or room.id_.startswith(target_name):
            return room
    for zone in operating_state.zones_:
        for room in zone.rooms_.values():
            if room.name_.startswith(target_name) or room.id_.startswith(target_name):
                return room
    return None


operating_state = OperatingState()
