from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .communication import CommTypes
from .core import set_vars
from .nondb_models.actors import ActorType, Actor, Room, Character, FlagBitmap, AttackData, DamageType
from .operating_state import operating_state
from .nondb_models.triggers import TriggerType
import random


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
    vars = set_vars(actor, actor, actor, room_msg)
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


async def start_fighting(subject: Actor, target: Actor):
    logger = CustomDetailLogger(__name__, prefix="start_fighting()> ")
    logger.debug(f"subject: {subject}, target: {target}")
    if subject.actor_type_ != ActorType.CHARACTER:
        raise Exception("Subject must be of type CHARACTER to start fighting.")
    if target.actor_type_ != ActorType.CHARACTER:
        raise Exception("Target must be of type CHARACTER to start fighting.")
    subject.fighting_whom_ = target
    msg = f"You start fighting {target.name_}!"
    await subject.echo(CommTypes.DYNAMIC, msg, set_vars(subject, subject, target, msg))
    msg = f"{subject.name_} starts fighting you!"
    await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, subject, target, msg))
    msg = f"{subject.name_} starts fighting {target.name_}!"
    await subject.location_room_.echo(CommTypes.DYNAMIC, msg,
                                      set_vars(subject.location_room_, subject, target, msg),
                                      exceptions=[subject, target])
    operating_state.characters_fighting_.append(subject)




async def do_die(dying_actor: Actor, killer: Actor = None, other_killer = None):
    msg = f"You die!"
    await dying_actor.echo(CommTypes.DYNAMIC, msg, set_vars(dying_actor, dying_actor, dying_actor, msg))

    if killer:
        msg = f"You kill {dying_actor.name_}!"
        await killer.echo(CommTypes.DYNAMIC, msg, set_vars(killer, killer, dying_actor, msg))
        msg = f"{killer.name_} kills {dying_actor.name_}!"
        await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(dying_actor, killer, dying_actor, msg))
    if other_killer != None:
        if other_killer == "":
            msg = f"{dying_actor.name_} dies!"
            await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(dying_actor, None, dying_actor, msg))
        else:
            msg = f"{other_killer} kills {dying_actor.name_}!"
            await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(dying_actor, None, dying_actor, msg),
                                            exceptions=[dying_actor])
    # TODO:M: handle corpses!
    if operating_state.characters_fighting_.contains(dying_actor):
        operating_state.characters_fighting_.remove(dying_actor)
    dying_actor.fighting_whom_ = None
    dying_actor.location_room_.remove_character(dying_actor)
    dying_actor.hit_points_ = 0
    for c in operating_state.characters_fighting_:
        if c.fighting_whom_ == dying_actor:
            c.fighting_whom_ = None


async def do_damage(actor: Actor, target: Actor, damage: int, damage_type: DamageType):
    logger = CustomDetailLogger(__name__, prefix="do_damage()> ")
    logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
    if actor.actor_type_ != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to do damage.")
    if target.actor_type_ != ActorType.CHARACTER:
        raise Exception("Target must be of type CHARACTER to do damage.")
    target.current_hit_points_ -= damage
    msg = f"You do {damage} {damage_type.word()} damage to {target.name_}!"
    await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
    msg = f"{actor.name_} does {damage} {damage_type.word()} damage to you!"
    await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
    msg = f"{actor.name_} does {damage} {damage_type.word()} damage to {target.name_}!"
    await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                    set_vars(actor.location_room_, actor, target, msg),
                                    exceptions=[actor, target])
    if target.current_hit_points_ <= 0:
        await do_die(target, actor)


async def do_single_attack(actor: Actor, target: Actor, attack: AttackData) -> int:
    # TODO:M: figure out weapons
    logger = CustomDetailLogger(__name__, prefix="do_single_attack()> ")
    logger.debug(f"actor: {actor.rid}, target: {target.rid}")
    if actor.actor_type_ != ActorType.CHARACTER:
        raise Exception("Actor must be of type CHARACTER to attack.")
    if target.actor_type_ != ActorType.CHARACTER:
        raise Exception("Target must be of type CHARACTER to attack.")
    hit_modifier = actor.hit_chance_
    dodge_roll = target.dodge_dice_number_ * target.dodge_dice_size_ + target.dodge_modifier_
    hit_roll = random.randint(1, 100)
    if hit_roll + hit_modifier < dodge_roll:
        msg = f"You miss {target.name_} with {attack.attack_noun_}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = f"{actor.name_} {"critically" if critical else ""} misses you with {attack.attack_noun_}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = f"{actor.name_} {"critically" if critical else ""} misses {target.name_} with {attack.attack_noun_}!"
        await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room_, actor, target, msg),
                                        exceptions=[actor, target])
        return -1 # a miss
    # is it a critical?
    critical = random.random(1,100) < actor.critical_chance_
    # it hit, figure out damage
    msg = f"You {"critically" if critical else ""} {attack.attack_verb_} {target.name_} with {attack.attack_noun_}!"
    await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
    msg = f"{actor.name_} {"critically" if critical else ""} {attack.attack_verb_}s you with {attack.attack_noun_}!"
    await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
    msg = f"{actor.name_} {"critically" if critical else ""} {attack.attack_verb_}s {target.name_} with {attack.attack_noun_}!"
    await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                    set_vars(actor.location_room_, actor, target, msg),
                                    exceptions=[actor, target])
    total_damage = 0
    for dp in attack.potential_damage_:
        damage = dp.roll_damage()
        if critical:
            damage *= (100 + actor.critical_damage_bonus_) / 100
        dmg_mult = dp.calc_susceptability(dp.damage_type_, [ target.damage_resistances_])
        damage = damage * dmg_mult - target.damage_reduction_[dp.damage_type_]
        do_damage(actor, target, damage, dp.damage_type_)
        total_damage += damage
    return total_damage
        


    


async def process_fighting():
    for c in operating_state.characters_fighting_:
        for natural_attack in c.natural_attacks_:
            await do_single_attack(c, c.fighting_whom_, natural_attack)
