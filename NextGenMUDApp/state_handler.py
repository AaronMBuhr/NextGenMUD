from .nondb_models.actors import Character
from .actions import arrive_room
from .communication import Connection
from custom_detail_logger import CustomDetailLogger
import json
from .operating_state import operating_state
from yaml_dumper import YamlDumper

async def startConnection(consumer: 'MyWebsocketConsumer'):
    logger = CustomDetailLogger(__name__, prefix="startConnection()> ")
    logger.debug("init new connection")
    await consumer.send(text_data=json.dumps({ 
        'text_type': 'dynamic',
        'text': 'Connection accepted!'
    }))

    new_connection = Connection(consumer)
    # await new_connection.send("static", "Welcome to NextGenMUD!")
    operating_state.connections_.append(new_connection)
    await loadInCharacter(new_connection)
    return new_connection


async def loadInCharacter(connection: Connection):
    logger = CustomDetailLogger(__name__, prefix="loadInCharacter()> ")
    new_player = Character("test_player")
    new_player.connection_ = connection
    new_player.connection_.character = new_player
    new_player.name_ = "Test Player"
    new_player.description_ = "A test player."
    new_player.pronoun_ = "he"
    operating_state.players_.append(new_player)
    print(YamlDumper.to_yaml_compatible_str(operating_state.zones_))
    first_zone = operating_state.zones_[list(operating_state.zones_.keys())[0]]
    print(YamlDumper.to_yaml_compatible_str(first_zone))
    logger.debug(f"first_zone: {first_zone}")
    first_room = first_zone.rooms_[list(first_zone.rooms_.keys())[0]]
    logger.debug(f"first_room: {first_room}")
    await arrive_room(new_player, first_room)


def removeConnection(consumer: 'MyWebsocketConsumer'):
    for c in operating_state.connections_:
        if c.consumer_ == consumer:
            removeCharacter(c)
            operating_state.connections_.remove(c)
            return
        

def removeCharacter(self, connection: Connection):
    operating_state.players_.remove(connection.character)
