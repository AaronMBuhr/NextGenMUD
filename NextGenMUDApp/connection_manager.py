import json
from structured_logger import StructuredLogger

from .comprehensive_game_state import ComprehensiveGameState
from .communication import Connection
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actors import Actor
from .nondb_models.characters import Character


class ConnectionManager:

    def __init__(self, live_game_state: ComprehensiveGameState):
        self.live_game_state_ = live_game_state

    async def start_connection(self, consumer: 'MyWebsocketConsumer'):
        logger = StructuredLogger(__name__, prefix="startConnection()> ")
        logger.debug("init new connection")
        await consumer.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Connection accepted!'
        }))

        new_connection = Connection(consumer)
        await new_connection.send("static", "Welcome to NextGenMUD!")
        self.live_game_state_.connections.append(new_connection)
        await self.load_in_character(new_connection)
        return new_connection


    async def load_in_character(self, connection: Connection):
        logger = StructuredLogger(__name__, prefix="loadInCharacter()> ")
        logger.debug("loading in character")
        chardef = self.live_game_state_.world_definition_.find_character_definition("test_player")
        new_player = Character.create_from_definition(chardef)
        new_player.connection = connection
        new_player.connection.character = new_player
        new_player.name_ = "Test Player"
        new_player.description_ = "A test player."
        new_player.pronoun_subject_ = "he"
        new_player.pronoun_object_ = "him"
        self.live_game_state_.players.append(new_player)
        first_zone = self.live_game_state_.zones_[list(self.live_game_state_.zones_.keys())[0]]
        logger.debug3(f"first_zone: {first_zone}")
        first_room = first_zone.rooms_[list(first_zone.rooms_.keys())[0]]
        logger.debug3(f"first_room: {first_room}")
        await CoreActionsInterface.get_instance().actions.arrive_room(new_player, first_room)


    def remove_connection(self, consumer: 'MyWebsocketConsumer'):
        logger = StructuredLogger(__name__, prefix="remove_connection()> ")
        for c in self.live_game_state_.connections:
            if c.consumer_ == consumer:
                logger.debug(f"Found connection to remove")
                self.remove_character(c)
                self.live_game_state_.connections.remove(c)
                return
        logger.warning(f"Could not find connection to remove for consumer: {consumer}")


    def remove_character(self, connection: Connection):
        if connection.character:
            # Remove from combat if fighting
            if connection.character.fighting_whom is not None:
                CoreActionsInterface.get_instance().stop_fighting(connection.character)
            
            # Remove from players list
            if connection.character in self.live_game_state_.players:
                self.live_game_state_.players.remove(connection.character)
            
            # Clear the connection reference in the character
            connection.character.connection = None
            connection.character = None
