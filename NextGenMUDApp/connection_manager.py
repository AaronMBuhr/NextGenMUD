from custom_detail_logger import CustomDetailLogger

from .comprehensive_game_state import ComprehensiveGameState
from .communication import Connection
from .core_actions_interface import CoreActionsInterface


class ConnectionManager:

    def __init__(self, live_game_state: ComprehensiveGameState):
        self.live_game_state_ = live_game_state

    async def start_connection(self, consumer: 'MyWebsocketConsumer'):
        logger = CustomDetailLogger(__name__, prefix="startConnection()> ")
        logger.debug("init new connection")
        await consumer.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Connection accepted!'
        }))

        new_connection = Connection(consumer)
        # await new_connection.send("static", "Welcome to NextGenMUD!")
        self.live_game_state.connections.append(new_connection)
        await self.load_in_character(new_connection)
        return new_connection


    async def load_in_character(self, connection: Connection):
        from .nondb_models.actors import Character
        logger = CustomDetailLogger(__name__, prefix="loadInCharacter()> ")
        logger.debug("loading in character")
        chardef = self.live_game_state.world_definition_.find_character_definition("test_player")
        new_player = Character.create_from_definition(chardef)
        new_player.connection = connection
        new_player.connection.character = new_player
        new_player.name_ = "Test Player"
        new_player.description_ = "A test player."
        new_player.pronoun_subject_ = "he"
        new_player.pronoun_object_ = "him"
        self.live_game_state.players_.append(new_player)
        # print(YamlDumper.to_yaml_compatible_str(operating_state.zones_))
        first_zone = self.live_game_state.zones_[list(self.live_game_state.zones_.keys())[0]]
        # print(YamlDumper.to_yaml_compatible_str(first_zone))
        logger.debug3(f"first_zone: {first_zone}")
        first_room = first_zone.rooms_[list(first_zone.rooms_.keys())[0]]
        logger.debug3(f"first_room: {first_room}")
        await CoreActionsInterface.get_instance().actions.arrive_room(new_player, first_room)


    def remove_connection(self, consumer: 'MyWebsocketConsumer'):
        for c in self.live_game_state.connections:
            if c.consumer_ == consumer:
                self.remove_character(c)
                self.live_game_state.connections.remove(c)
                return
            

    def remove_character(self, connection: Connection):
        self.live_game_state.players_.remove(connection.character)
