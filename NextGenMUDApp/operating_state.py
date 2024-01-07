from custom_detail_logger import CustomDetailLogger
from django.conf import settings
import json
from .communication import Connection
from .nondb_models.actors import Character, Room, Zone
# from .nondb_models.world import Zone
import os
import sys
import yaml
from yaml_dumper import YamlDumper

class OperatingState:

    def __init__(self):
        self.zones_ = {}
        self.characters_ = []
        self.players_ = []
        self.connections_ = []

    def Initialize(self):
        logger = CustomDetailLogger(__name__, prefix="Initialize()> ")
        zones_file_path = os.path.join(settings.BASE_DIR, 'NextGenMUDApp', 'world_data', 'zones.yaml')
        with open(zones_file_path, "r") as yf:
            yaml_data = yaml.safe_load(yf)

        logger.debug(f"zone yaml_data: {yaml_data}")
        for zone_id, zone_info in yaml_data['ZONES'].items():
            # logger.debug(f"loading zone_id: {zone_id}")
            new_zone = Zone(zone_id)
            new_zone.name_ = zone_info['name']
            # logger.debug(f"new_zone.name_: {new_zone.name_}")
            new_zone.description_ = zone_info['description']

            for room_id, room_info in zone_info['rooms'].items():
                # logger.debug(f"loading room_id: {room_id}")
                new_room = Room(room_id)
                new_room.description_ = room_info['description']
                new_room.zone_ = new_zone

                for direction, exit_info in room_info['exits'].items():
                    # logger.debug(f"loading direction: {direction}")
                    new_room.exits_[direction] = exit_info['destination']

                new_zone.rooms_[room_id] = new_room

            # logger.debug(repr(new_zone))
            # logger.debug(f"setting new_zone for zone id '{zone_id}': {new_zone}")
            # logger.debug(f"setting new_zone for zone id '{zone_id}': {YamlDumper.to_yaml_compatible_str(new_zone)}")
            logger.debug(f"setting new_zone for zone id '{zone_id}': {YamlDumper.to_yaml_compatible_str(new_zone)}")
            self.zones_[zone_id] = new_zone
        if self.zones_ == {}:
            raise Exception("No zones loaded.")
        if self.zones_ == None:
            raise Exception("Zones is NONE.")
        logger.debug(f"loaded zones: {YamlDumper.to_yaml_compatible_str(self.zones_)}")
        logger.debug(f"loaded zones: {self.zones_}")
        logger.debug(f"loaded zones: {YamlDumper.to_yaml_compatible_str(self.zones_)}")
        logger.debug(f"zone keys: {self.zones_.keys()}")
        logger.debug(f"loaded zones: {self.zones_['starting_zone']}")
        logger.debug(f"first zone: {self.zones_[list(self.zones_.keys())[0]]}")



operating_state = OperatingState()
