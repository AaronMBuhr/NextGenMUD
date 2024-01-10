from .actions import arrive_room
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
import json
from .operating_state import operating_state
from yaml_dumper import YamlDumper

async def start_connection(consumer: 'MyWebsocketConsumer'):
    logger = CustomDetailLogger(__name__, prefix="startConnection()> ")
    logger.debug("init new connection")
    await consumer.send(text_data=json.dumps({ 
        'text_type': 'dynamic',
        'text': 'Connection accepted!'
    }))

    new_connection = Connection(consumer)
    # await new_connection.send("static", "Welcome to NextGenMUD!")
    operating_state.connections_.append(new_connection)
    await load_in_character(new_connection)
    return new_connection


async def load_in_character(connection: Connection):
    from .nondb_models.actors import Character
    from .operating_state import operating_state
    logger = CustomDetailLogger(__name__, prefix="loadInCharacter()> ")
    logger.debug("loading in character")
    chardef = operating_state.world_definition_.find_character_definition("test_player")
    new_player = Character.create_from_definition(chardef)
    new_player.connection_ = connection
    new_player.connection_.character = new_player
    new_player.name_ = "Test Player"
    new_player.description_ = "A test player."
    new_player.pronoun_subject_ = "he"
    new_player.pronoun_object_ = "him"
    operating_state.players_.append(new_player)
    # print(YamlDumper.to_yaml_compatible_str(operating_state.zones_))
    first_zone = operating_state.zones_[list(operating_state.zones_.keys())[0]]
    # print(YamlDumper.to_yaml_compatible_str(first_zone))
    logger.debug3(f"first_zone: {first_zone}")
    first_room = first_zone.rooms_[list(first_zone.rooms_.keys())[0]]
    logger.debug3(f"first_room: {first_room}")
    await arrive_room(new_player, first_room)


def remove_connection(consumer: 'MyWebsocketConsumer'):
    for c in operating_state.connections_:
        if c.consumer_ == consumer:
            remove_character(c)
            operating_state.connections_.remove(c)
            return
        

def remove_character(self, connection: Connection):
    operating_state.players_.remove(connection.character)
