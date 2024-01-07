from custom_detail_logger import CustomDetailLogger
from .communication import CommTypes
from .nondb_models.actors import ActorType, Actor, Room, Character, FlagBitmap
from .operating_state import operating_state

async def arriveRoom(actor: Actor, room: Room, room_from: Room = None):
    logger = CustomDetailLogger(__name__, prefix="arriveRoom()> ")
    logger.debug(f"actor: {actor}, room: {room}, room_from: {room_from}")
    if actor.actor_type != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to arrive in a room.")
    if actor.location_room is not None:
        raise Exception("Actor must not already be in a room to arrive in a room.")
    
    actor.location_room = room
    room.addCharacter(actor)
    await room.sendText("dynamic", f"{actor.name_} arrives.", exceptions=[actor])

    # # TODO:L: figure out what direction "from" based upon back-path
    # actor.location_room.sendText("dynamic", f"{actor.name_} arrives.", exceptions=[actor])

    logger.debug(f"Sending room description to actor: {room.description}")
    await actor.sendText(CommTypes.STATIC, room.description)


async def worldMove(actor: Actor, direction: str):
    logger = CustomDetailLogger(__name__, prefix="worldMove()> ")
    logger.debug(f"actor: {actor}")

    if actor.actor_type != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to move.")
    
    if not direction in actor.location_room.exits:
        raise Exception(f"Location {actor.location.id} does not have an exit in direction {direction}")
    
    actor.location_room.sendText("dynamic", f"{actor.name_} leaves {direction}", exceptions=[actor])
    await actor.sendText("dynamic", f"You leave {direction}")
    old_room = actor.location_room
    destination = actor.location_room.exits[direction]
    if "." in destination:
        zone_id, room_id = destination.split(".")
    else:
        zone_id = old_room.zone_.id_
        room_id = destination
    new_room = operating_state.zones_[zone_id].rooms_[room_id]
    actor.location_room.removeCharacter(actor)
    actor.location_room = None
    await arriveRoom(actor, new_room, old_room)

