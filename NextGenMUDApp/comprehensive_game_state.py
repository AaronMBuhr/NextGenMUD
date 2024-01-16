import copy
import fnmatch
from custom_detail_logger import CustomDetailLogger
from django.conf import settings
import json
import os
from typing import List, Dict
import yaml
from yaml_dumper import YamlDumper
from .nondb_models.actors import Character, Actor, Room, Object, EquipLocation, GamePermissionFlags, \
    TemporaryCharacterFlags, PermanentCharacterFlags, CharacterStateStealthed
from .nondb_models.world import WorldDefinition, Zone
from .constants import Constants
from .communication import Connection
from .config import Config, default_app_config
from .utility import article_plus_name
# from .consumers import MyWebsocketConsumerStateHandlerInterface
from .game_state_interface import GameStateInterface, ScheduledAction
from .nondb_models.world import Zone


class LiveGameStateContextManager:
    def __init__(self, **live_game_states):
        self.original_live_game_states = {}
        self.new_live_game_states = live_game_states

    def __enter__(self):
        # Store the original configurations and apply new ones
        for class_name, new_state in self.new_live_game_states.items():
            self.original_live_game_states[class_name] = class_name.live_game_state
            class_name.live_game_state = new_state

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the original configurations
        for class_name, original_live_game_state in self.original_live_game_states.items():
            class_name.live_game_state = original_live_game_state


def find_yaml_files(directory):
    # print(f"------------------ {directory}")
    for root, dirs, files in os.walk(directory):
        # print("***************")
        # print(root,dirs,files)
        for file in files:
            # print(file)
            if fnmatch.fnmatch(file, '*.yaml') or fnmatch.fnmatch(file, '*.yml'):
                yield os.path.join(root, file)


class ComprehensiveGameState:

    def __init__(self, app_config: Config = default_app_config):
        self.app_config: Config = app_config
        self.world_definition_: WorldDefinition = WorldDefinition()
        self.characters_: List[Character] = []
        self.players_ : List[Character] = []
        self.connections_ : List[Connection] = []
        self.characters_fighting_ : List[Character] = []
        self.zones_ = {}
        self.world_clock_tick_ = 0
        self.scheduled_actions_ = {}
        self.xp_progression_ = []
        # MyWebsocketConsumerStateHandlerInterface.game_state_handler = self


    def Initialize(self):
        from .nondb_models.actors import Character, Room #, Zone
        from .nondb_models.world import Zone
        logger = CustomDetailLogger(__name__, prefix="Initialize()> ")

        self.world_definition_.zones_ = {}

        self.xp_progression_ = self.app_config.XP_PROGRESSION

        file_found = False
        logger.info(f"Loading world files (*.yaml) from [{self.app_config.WORLD_DATA_DIR}]...")
        for yaml_file in find_yaml_files(self.app_config.WORLD_DATA_DIR):
            logger.info(f"Loading world file {yaml_file}")
            with open(yaml_file, "r") as yf:
                yaml_data = yaml.safe_load(yf)
                file_found = True
            if yaml_data == None:
                logger.warning(f"YAML file {yaml_file} is empty.")
                continue
            # try:
            if 'ZONES' in yaml_data:
                logger.debug("Loading zones...")
                for zone_id, zone_info in yaml_data['ZONES'].items():
                    logger.info(f"Loading zone_id: {zone_id}")
                    new_zone = Zone(zone_id)
                    new_zone.name_ = zone_info['name']
                    # logger.debug(f"new_zone.name_: {new_zone.name_}")
                    new_zone.description_ = zone_info['description']
                    self.world_definition_.zones_[zone_id] = new_zone
                    logger.debug(f"Loading rooms...")
                    for room_id, room_info in zone_info['rooms'].items():
                        logger.debug2(f"Loading room_id: {room_id}")
                        new_room = Room(room_id, self.world_definition_.zones_[zone_id])
                        new_room.from_yaml(new_zone, room_info)
                        new_zone.rooms_[room_id] = new_room
                    logger.debug("Rooms loaded")
                logger.debug("Zones loaded")

            if "CHARACTERS" in yaml_data:
                logger.debug("Loading characters...")
                # print(yaml_data)
                # for charzone in yaml_data["ZONES"]:
                #     for chardef in yaml_data["ZONES"]["CHARACTERS"]:
                #         ch = Character(chardef["id"], charzone)
                #         ch.from_yaml(chardef)
                #         self.world_definition_.characters_[ch.id_] = ch
                for zonedef in yaml_data["CHARACTERS"]:
                    for chardef in zonedef["characters"]:
                        ch = Character(chardef["id"], self.world_definition_.zones_[zonedef["zone"]], create_reference=False)
                        ch.from_yaml(chardef)
                        ch.game_permission_flags_ = ch.game_permission_flags_.add_flags(GamePermissionFlags.IS_ADMIN)
                        logger.debug(f"loaded character: {ch.id_}")
                        self.world_definition_.characters_[ch.id_] = ch

                logger.debug("Characters loaded")

            if "OBJECTS" in yaml_data:
                # Objects
                logger.debug("Loading objects...")
                # print(yaml_data)
                # for charzone in yaml_data["ZONES"]:
                #     for chardef in yaml_data["ZONES"]["CHARACTERS"]:
                #         ch = Character(chardef["id"], charzone)
                #         ch.from_yaml(chardef)
                #         self.world_definition_.characters_[ch.id_] = ch
                for zonedef in yaml_data["OBJECTS"]:
                    for objdef in zonedef["objects"]:
                        obj = Object(objdef["id"], self.world_definition_.zones_[zonedef["zone"]], create_reference=False)
                        obj.from_yaml(objdef)
                        self.world_definition_.objects_[obj.id_] = obj
                logger.debug("Objects loaded")
            # except Exception as e:
            #     logger.error(f"Error loading yaml file {yaml_file}: {e}")

        if not file_found:
            raise Exception(f"No world files found in {self.app_config.WORLD_DATA_DIR}.")
        if self.world_definition_.zones_ == {}:
            raise Exception("No zones loaded.")
        if self.world_definition_.zones_ == None:
            raise Exception("Zones is NONE.")
        logger.info(f"World files finished loading, from [{self.app_config.WORLD_DATA_DIR}].")

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
    

    def find_target_character(self, actor: Actor, target_name: str, search_zone=False, search_world=False) -> Character:
        logger = CustomDetailLogger(__name__, prefix="find_target_character()> ")
        # search_world automatically turns on search_zone
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name[0].lower() == 'me':
            return actor
                
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
            try:
                target_number = int(parts[1])
            except:
                return None

        candidates = []

        def can_see(char: Character, target: Character) -> bool:
            if char == target:
                return True
            if target.has_temp_flags(TemporaryCharacterFlags.INVISIBLE) \
            or target.has_perm_flags(PermanentCharacterFlags.INVISIBLE):
                if not char.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE) \
                and not char.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE):
                    return False
            if target.has_temp_flag(TemporaryCharacterFlags.IS_STEALTHED):
                stealth_states = [s for s in target.get_states() if isinstance(s) == CharacterStateStealthed]
                if len(stealth_states) == 0:
                    # TODO:L: this probably should log an error message
                    return False
                if not char in stealth_states[0].vars_['seen_by']:
                    return False
            return True

        # Helper function to add candidates from a room
        def add_candidates_from_room(actor, room):
            for char in room.characters_:
                if char.id_.startswith(target_name) and can_see(char, actor):
                    candidates.append(char)
                else:
                    name_pieces = char.name_.split(' ')
                    for piece in name_pieces:
                        if piece.startswith(target_name) and can_see(char, actor):
                            candidates.append(char)

        # Search in the current room
        add_candidates_from_room(start_room)

        if search_zone or search_world:
            # If not found in the current room, search in the current zone
            if len(candidates) < target_number and isinstance(start_room, Room) and start_room.zone_:
                for room in start_room.zone_.rooms_.values():
                    add_candidates_from_room(room)

        if search_world:
            # If still not found, search across all zones
            if len(candidates) < target_number:
                for zone in self.zones_.values():
                    for room in zone.rooms_.values():
                        add_candidates_from_room(room)

        # Return the target character
        logger.critical(f"candidates: {candidates}")
        if 0 < target_number <= len(candidates):
            return candidates[target_number - 1]

        return None


    def find_all_characters(self, actor: Actor, target_name: str) -> str:
        # TODO:L: should we limit these to can-see?
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
                if char.id_.startswith(target_name):
                    matching_characters.append(f"{article_plus_name(char.article_, char.name_, cap=True)} in {room.name_}")
                else:
                    name_pieces = char.name_.split(' ')
                    for piece in name_pieces:
                        if piece.startswith(target_name):
                            matching_characters.append(f"{article_plus_name(char.article_, char.name_, cap=True)} in {room.name_}")
                            break

        # Search in the current room
        add_matching_characters_from_room(start_room)

        # Search in the current zone
        if isinstance(start_room, Room) and start_room.zone_:
            for room in start_room.zone_.rooms_.values():
                add_matching_characters_from_room(room)

        # Search across all zones
        for zone in self.zones_.values():
            for room in zone.rooms_.values():
                add_matching_characters_from_room(room)

        # Format and return the results
        return "\n".join(matching_characters)


    def find_target_room(self, actor: Actor, target_name: str, start_zone: Zone) -> Room:
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name[0].lower() == 'me':
            return actor
        for room in start_zone.rooms_.values():
            if room.name_.startswith(target_name) or room.id_.startswith(target_name):
                return room
        for zone in self.zones_:
            for room in zone.rooms_.values():
                if room.id_.startswith(target_name):
                    return room
                for pieces in room.name_.split(' '):
                    if pieces.startswith(target_name):
                        return room
        return None
    

    def find_target_object(self, target_name: str, actor: Actor = None, equipped: Dict[EquipLocation, Object] = None, 
                           start_room: Room = None, start_zone: Zone = None, search_world=False) -> Object:
        logger = CustomDetailLogger(__name__, prefix="find_target_object()> ")

        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name[0].lower() == 'me':
            return actor

        def check_object(obj) -> bool:
            logger = CustomDetailLogger(__name__, prefix="find_target_object.check_object()> ")
            if obj.id_.startswith(target_name):
                return True
            for pieces in obj.name_.split(' '):
                logger.debug3(f"pieces: {pieces} ? {target_name}")
                if pieces.startswith(target_name):
                    return True
            return False

        target_number = 1
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                target_number = int(parts[1])
            except:
                return None

        candidates: List[Object] = []

        if equipped:
            for obj in equipped.values():
                print(obj)
                if check_object(obj):
                    candidates.append(obj)
        if actor:
            for obj in actor.contents_:
                if check_object(obj):
                    candidates.append(obj)
        if start_room:
            for obj in start_room.contents_:
                if check_object(obj):
                    candidates.append(obj)
        if start_zone:
            for room in start_zone.rooms_.values():
                for obj in room.contents_:
                    if check_object(obj):
                        candidates.append(obj)
        if search_world:
            for zone in self.zones_.values():
                for room in zone.rooms_.values():
                    for obj in room.contents_:
                        if check_object(obj):
                            candidates.append(obj)
        
        # Return the target object
        logger.critical(f"candidates: {candidates}")
        if 0 < target_number <= len(candidates):
            return candidates[target_number - 1]
        return None
    

    
    async def start_connection(self, consumer: 'MyWebsocketConsumer'):
        logger = CustomDetailLogger(__name__, prefix="startConnection()> ")
        logger.debug("init new connection")
        await consumer.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Connection accepted!'
        }))

        new_connection = Connection(consumer)
        # await new_connection.send("static", "Welcome to NextGenMUD!")
        self.connections_.append(new_connection)
        await self.load_in_character(new_connection)
        return new_connection


    async def load_in_character(self, connection: Connection):
        from .core_actions import CoreActions
        logger = CustomDetailLogger(__name__, prefix="loadInCharacter()> ")
        logger.debug("loading in character")
        chardef = self.world_definition_.find_character_definition("test_player")
        if not chardef:
            raise Exception("Character definition for 'test_player' not found.")
        new_player = Character.create_from_definition(chardef)
        new_player.connection_ = connection
        new_player.connection_.character = new_player
        new_player.name_ = "Test Player"
        new_player.description_ = "A test player."
        new_player.pronoun_subject_ = "he"
        new_player.pronoun_object_ = "him"
        self.players_.append(new_player)
        # print(YamlDumper.to_yaml_compatible_str(operating_state.zones_))
        first_zone = self.zones_[list(self.zones_.keys())[0]]
        # print(YamlDumper.to_yaml_compatible_str(first_zone))
        logger.debug3(f"first_zone: {first_zone}")
        first_room = first_zone.rooms_[list(first_zone.rooms_.keys())[0]]
        logger.debug3(f"first_room: {first_room}")
        logger.info(f"New player arriving: {new_player.name_}")
        await CoreActions.arrive_room(new_player, first_room)


    def remove_connection(self, consumer: 'MyWebsocketConsumer'):
        for c in self.connections_:
            if c.consumer_ == consumer:
                self.remove_character(c)
                self.connections_.remove(c)
                return
            

    def remove_character(self, connection: Connection):
        self.players_.remove(connection.character)


    def add_scheduled_action(self, scheduled_tick: int, actor: Actor, name: str, vars: Dict[str, str], func: callable = None):
        logger = CustomDetailLogger(__name__, prefix="add_scheduled_task()> ")
        action = ScheduledAction(actor, name, vars, func)
        if not scheduled_tick in self.scheduled_actions_:
            self.scheduled_actions_[scheduled_tick] = []
        self.scheduled_actions_[scheduled_tick].append(action)

    def perform_scheduled_actions(self, tick: int):
        logger = CustomDetailLogger(__name__, prefix="perform_scheduled_actions()> ")
        if tick in self.scheduled_actions_:
            for action in self.scheduled_actions_[tick]:
                if action.actor_ and Actor.is_deleted_(action.actor_):
                    action.actor_ = None
                    continue
                logger.debug(f"performing scheduled action {action.name_}")
                action.run()
            del self.scheduled_actions_[tick]

live_game_state = ComprehensiveGameState()
