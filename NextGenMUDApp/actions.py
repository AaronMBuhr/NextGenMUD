from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .communication import CommTypes
from .nondb_models.actors import ActorType, Actor, Room, Character, FlagBitmap
from .operating_state import operating_state
from .nondb_models.triggers import TriggerType

def actor_vars(actor: Actor, name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}

async def arrive_room(actor: Actor, room: Room, room_from: Room = None):
    logger = CustomDetailLogger(__name__, prefix="arriveRoom()> ")
    logger.debug(f"actor: {actor}, room: {room}, room_from: {room_from}")
    if actor.actor_type_ != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to arrive in a room.")
    if actor.location_room_ is not None:
        raise Exception("Actor must not already be in a room to arrive in a room.")
    
    actor.location_room_ = room
    room.add_character(actor)
    # await room.send_text("dynamic", f"{actor.name_} arrives.", exceptions=[actor])
    room_msg = f"{actor.name_} arrives."
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_subject_,
        'R': actor.pronoun_object_,
        '*': room_msg }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(actor, "t")) }
    logger.debug(f"Sending room description to actor for: {room.name_}")
    # await actor.send_text(CommTypes.STATIC, room.description_)
    await actor.send_text(CommTypes.STATIC, room.name_ + "\n" + room.description_)
    await room.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=[actor])
    # # TODO:L: figure out what direction "from" based upon back-path
    # actor.location_room.send_text("dynamic", f"{actor.name_} arrives.", exceptions=[actor])



async def world_move(actor: Actor, direction: str):
    logger = CustomDetailLogger(__name__, prefix="worldMove()> ")
    logger.debug(f"actor: {actor}")

    if actor.actor_type_ != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to move.")
    
    if not direction in actor.location_room_.exits_:
        raise Exception(f"Location {actor.location_room_.id_} does not have an exit in direction {direction}")
    
    actor.location_room_.echo("dynamic", f"{actor.name_} leaves {direction}", exceptions=[actor])
    await actor.send_text("dynamic", f"You leave {direction}")
    old_room = actor.location_room_
    destination = actor.location_room_.exits_[direction]
    if "." in destination:
        zone_id, room_id = destination.split(".")
    else:
        zone_id = old_room.zone_.id_
        room_id = destination
    new_room = operating_state.zones_[zone_id].rooms_[room_id]
    actor.location_room_.remove_character(actor)
    actor.location_room_ = None
    await arrive_room(actor, new_room, old_room)


# async def do_echo(actor: Actor, comm_type: CommTypes, text: str):
#     logger = CustomDetailLogger(__name__, prefix="do_echo()> ")
#     logger.debug(f"actor: {actor}, text: {text}")
#     if actor.actor_type_ == ActorType.CHARACTER and actor.connection_ != None: 
#         await actor.send_text(comm_type, text)
#     # check triggers
#     for trigger_type in [ TriggerType.CATCH_ANY ]:
#         if trigger_type in actor.triggers_by_type_:
#             for trigger in actor.triggers_by_type_[trigger_type]:
#                 await trigger.run(actor, text, None)

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
