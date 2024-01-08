from custom_detail_logger import CustomDetailLogger
from .communication import CommTypes
from .nondb_models.actors import ActorType, Actor, Room, Character, FlagBitmap
from .operating_state import operating_state
from .nondb_models.triggers import TriggerType

async def arriveRoom(actor: Actor, room: Room, room_from: Room = None):
    logger = CustomDetailLogger(__name__, prefix="arriveRoom()> ")
    logger.debug(f"actor: {actor}, room: {room}, room_from: {room_from}")
    if actor.actor_type != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to arrive in a room.")
    if actor.location_room is not None:
        raise Exception("Actor must not already be in a room to arrive in a room.")
    
    actor.location_room = room
    room.addCharacter(actor)
    # await room.sendText("dynamic", f"{actor.name_} arrives.", exceptions=[actor])
    await do_echo(room, CommTypes.DYNAMIC, f"{actor.name_} arrives.")

    # # TODO:L: figure out what direction "from" based upon back-path
    # actor.location_room.sendText("dynamic", f"{actor.name_} arrives.", exceptions=[actor])

    logger.debug(f"Sending room description to actor for: {room.name_}")
    # await actor.sendText(CommTypes.STATIC, room.description_)
    await do_echo(actor, CommTypes.STATIC, room.name + "\n" + room.description_)


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


async def do_echo(actor: Actor, comm_type: CommTypes, text: str):
    logger = CustomDetailLogger(__name__, prefix="do_echo()> ")
    logger.debug(f"actor: {actor}, text: {text}")
    if actor.actor_type == ActorType.CHARACTER and actor.connection_ != None: 
        await actor.sendText(comm_type, text)
    # check triggers
    for trigger_type in [ TriggerType.CATCH_ANY ]:
        if trigger_type in actor.triggers_by_type_:
            for trigger in actor.triggers_by_type_[trigger_type]:
                await trigger.run(actor, text, None)

async def do_tell(actor: Actor, target: Actor, text: str):
    logger = CustomDetailLogger(__name__, prefix="do_tell()> ")
    logger.debug(f"actor: {actor}, target: {target}, text: {text}")
    do_echo(actor, CommTypes.DYNAMIC, f"You tell {target.name_}, \"{text}\"")
    do_echo(target, CommTypes.DYNAMIC, f"{actor.name_} tells you, \"{text}\"")
    var = { 'actor': actor, 'text': text }
    for trigger_type in [ TriggerType.CATCH_TELL ]:
        if trigger_type in target.triggers_by_type_:
            for trigger in target.triggers_by_type_[trigger_type]:
                await trigger.run(actor, text, var, None)
