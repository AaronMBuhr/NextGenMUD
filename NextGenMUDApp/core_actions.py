from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .communication import CommTypes
from .utility import set_vars, firstcap, article_plus_name, roll_dice
from .nondb_models.actors import ActorType, Actor, Room, Character, \
     AttackData, DamageType, Corpse, Object, ObjectFlags, EquipLocation
from .nondb_models.triggers import TriggerType
import random
from .config import Config, default_app_config
from .comprehensive_game_state import ComprehensiveGameState, live_game_state

class CoreActions:
    config: Config = default_app_config
    game_state: ComprehensiveGameState = live_game_state

    @classmethod
    async def do_look_room(cls, actor: Actor, room: Room):
        logger = CustomDetailLogger(__name__, prefix="do_look_room()> ")
        logger.debug("starting")
        # await actor.send_text(CommTypes.STATIC, room.description_)
        logger.debug("room parts")
        msg_parts = [ room.name_ , room.description_ ]
        # TODO:M: handle batching multiples
        logger.debug("characters")
        for character in room.characters_:
            if character != actor:
                logger.debug(f"character: {character.rid}")
                if character.fighting_whom_:
                    if character.fighting_whom_ == actor:
                        msg_parts.append(firstcap(article_plus_name(character.article_, character.name_)) + " is here, fighting you!")
                    else:
                        msg_parts.append(firstcap(article_plus_name(character.article_,character.name_)) + " is here, fighting " + character.fighting_whom_.name_ + "!")
                else:
                    # print("character.article: " + character.article_)
                    # print("character.name: " + character.name_)
                    msg_parts.append(firstcap(article_plus_name(character.article_, character.name_)) + " is here.")
        logger.debug("objects")
        for object in room.contents_: 
            msg_parts.append(firstcap(article_plus_name(object.article_, object.name_)) + " is here.")
        logger.debug(f"Sending room description to actor for: {room.name_}")
        await actor.send_text(CommTypes.CLEARSTATIC, "")
        await actor.echo(CommTypes.STATIC, "\n".join(msg_parts), set_vars(actor, actor, room, msg_parts))

        
    @classmethod
    async def do_look_character(cls, actor: Actor, target: Character):
        logger = CustomDetailLogger(__name__, prefix="do_look_character()> ")
        msg = firstcap(target.description_) + "\n" + f"{firstcap(target.pronoun_subject_)} is {target.get_status_description()}"
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg))


    @classmethod
    async def do_look_object(cls, actor: Actor, target: Object):
        logger = CustomDetailLogger(__name__, prefix="do_look_object()> ")
        msg_parts = [ target.description_ ]
        if target.object_flags_.are_flags_set(ObjectFlags.IS_CONTAINER) and not target.object_flags_.are_flags_set(ObjectFlags.IS_CONTAINER_LOCKED):
            if len(target.contents_) == 0:
                msg_parts.append(firstcap(target.pronoun_subject_) + " is empty.")
            else:
                msg_parts.append(firstcap(target.pronoun_subject_) + " contains:\n" + Object.collapse_name_multiples(target.contents_, "\n"))
        msg = '\n'.join(msg_parts)
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg))


    @classmethod
    async def arrive_room(cls, actor: Actor, room: Room, room_from: Room = None):
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
        await cls.do_look_room(actor, actor.location_room_)
        await room.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=[actor])
        # # TODO:L: figure out what direction "from" based upon back-path
        # actor.location_room.send_text("dynamic", f"{actor.name_} arrives.", exceptions=[actor])



    @classmethod
    async def world_move(cls, actor: Actor, direction: str):
        logger = CustomDetailLogger(__name__, prefix="worldMove()> ")
        logger.debug(f"actor: {actor}")

        if actor.actor_type_ != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to move.")
        
        if not direction in actor.location_room_.exits_:
            raise Exception(f"Location {actor.location_room_.id_} does not have an exit in direction {direction}")
        
        actor.location_room_.echo("dynamic", f"{firstcap(actor.name_)} leaves {direction}", exceptions=[actor])
        await actor.send_text("dynamic", f"You leave {direction}")
        old_room = actor.location_room_
        destination = actor.location_room_.exits_[direction]
        if "." in destination:
            zone_id, room_id = destination.split(".")
        else:
            zone_id = old_room.zone_.id_
            room_id = destination
        new_room = cls.game_state.zones_[zone_id].rooms_[room_id]
        actor.location_room_.remove_character(actor)
        actor.location_room_ = None
        await cls.arrive_room(actor, new_room, old_room)


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

    # @classmethod
    # async def do_tell(cls, actor: Actor, target: Actor, text: str):
    #     logger = CustomDetailLogger(__name__, prefix="do_tell()> ")
    #     logger.debug(f"actor: {actor}, target: {target}, text: {text}")
    #     do_echo(actor, CommTypes.DYNAMIC, f"You tell {target.name_}, \"{text}\"")
    #     do_echo(target, CommTypes.DYNAMIC, f"{actor.name_} tells you, \"{text}\"")
    #     var = { 'actor': actor, 'text': text }
    #     for trigger_type in [ TriggerType.CATCH_TELL ]:
    #         if trigger_type in target.triggers_by_type_:
    #             for trigger in target.triggers_by_type_[trigger_type]:
    #                 await trigger.run(actor, text, var, None)


    @classmethod
    async def start_fighting(cls, subject: Actor, target: Actor):
        logger = CustomDetailLogger(__name__, prefix="start_fighting()> ")
        logger.debug(f"subject: {subject}, target: {target}")
        if subject.actor_type_ != ActorType.CHARACTER:
            raise Exception("Subject must be of type CHARACTER to start fighting.")
        if target.actor_type_ != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to start fighting.")
        subject.fighting_whom_ = target
        msg = f"You start fighting {article_plus_name(target.article_, target.name_)}!"
        await subject.echo(CommTypes.DYNAMIC, msg, set_vars(subject, subject, target, msg))
        msg = f"{article_plus_name(subject.article_, subject.name_, cap=True)} starts fighting you!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, subject, target, msg))
        msg = f"{article_plus_name(subject.article_, subject.name_, cap=True)} starts fighting {target.name_}!"
        await subject.location_room_.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(subject.location_room_, subject, target, msg),
                                        exceptions=[subject, target])
        cls.game_state.characters_fighting_.append(subject)





    @classmethod
    async def do_die(cls, dying_actor: Actor, killer: Actor = None, other_killer: str = None):
        # TODO:L: maybe do "x kills you"
        logger = CustomDetailLogger(__name__, prefix="do_die()> ")
        msg = f"You die!"
        await dying_actor.echo(CommTypes.DYNAMIC, msg, set_vars(dying_actor, dying_actor, dying_actor, msg))

        if killer:
            msg = f"You kill {article_plus_name(dying_actor.article_, dying_actor.name_)}!"
            await killer.echo(CommTypes.DYNAMIC, msg, set_vars(killer, killer, dying_actor, msg))
            msg = f"{killer.name_} kills {article_plus_name(dying_actor.article_, dying_actor.name_)}!"
            await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(dying_actor, killer, dying_actor, msg), exceptions=[killer, dying_actor])
        if other_killer != None:
            if other_killer == "":
                msg = f"{article_plus_name(dying_actor.article_, dying_actor.name_, cap=True)} dies!"
                await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg), exceptions=[dying_actor])
            else:
                msg = f"{other_killer} kills {article_plus_name(dying_actor.article_, dying_actor.name_)}!"
                await dying_actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg),
                                                exceptions=[dying_actor])
        if dying_actor in cls.game_state.characters_fighting_:
            cls.game_state.characters_fighting_.remove(dying_actor)
        if killer:
            killer.fighting_whom_ = None
            cls.game_state.characters_fighting_.remove(killer)
        for c in cls.game_state.characters_fighting_:
            if killer and c.fighting_whom_ == killer:
                cls.start_fighting(killer, c)
            if c.fighting_whom_ == dying_actor:
                c.fighting_whom_ = None

        dying_actor.fighting_whom_ = None
        dying_actor.current_hit_points_ = 0
        room = dying_actor.location_room_
        dying_actor.location_room_.remove_character(dying_actor)
        corpse = Corpse(dying_actor, room)
        corpse.transfer_inventory()
        room.add_object(corpse)
        for c in room.characters_:
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            logger.debug(f"{c.rid} is refreshing room")
            await cls.do_look_room(c, room)


    @classmethod
    async def do_damage(cls, actor: Actor, target: Actor, damage: int, damage_type: DamageType):
        logger = CustomDetailLogger(__name__, prefix="do_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if actor.actor_type_ != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to do damage.")
        if target.actor_type_ != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to do damage.")
        target.current_hit_points_ -= damage
        msg = f"You do {damage} {damage_type.word()} damage to {article_plus_name(target.article_, target.name_)}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = f"{article_plus_name(actor.article_, actor.name_, cap=True)} does {damage} {damage_type.word()} damage to you!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = (f"{article_plus_name(actor.article_, actor.name_, cap=True)} does "
            f"{damage} {damage_type.word()} damage to {article_plus_name(target.article_, target.name_)}!")
        await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room_, actor, target, msg),
                                        exceptions=[actor, target])
        if target.current_hit_points_ <= 0:
            await cls.do_die(target, actor)


    @classmethod
    async def do_single_attack(cls, actor: Actor, target: Actor, attack: AttackData) -> int:
        # TODO:M: figure out weapons
        # TODO:L: deal with nouns and verbs correctly
        logger = CustomDetailLogger(__name__, prefix="do_single_attack()> ")
        logger.critical(f"actor: {actor.rid}, target: {target.rid}")
        logger.critical(f"attackdata: {attack.to_dict()}")
        if actor.actor_type_ != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to attack.")
        if target.actor_type_ != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to attack.")
        hit_modifier = actor.hit_modifier_ + attack.attack_bonus
        logger.critical(f"dodge_dice_number_: {target.dodge_dice_number_}, dodge_dice_size_: {target.dodge_dice_size_}, dodge_modifier_: {target.dodge_modifier_}")
        dodge_roll = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_) + target.dodge_modifier_
        hit_roll = random.randint(1, 100)
        if hit_roll + hit_modifier < dodge_roll:
            logger.critical(f"MISS: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
            msg = f"You miss {article_plus_name(target.article_, target.name_)} with {attack.attack_noun_}!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
            msg = f"{article_plus_name(actor.article_, actor.name_, cap=True)} misses you with {attack.attack_noun_}!"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
            msg = f"{article_plus_name(actor.article_, actor.name_, cap=True)} misses {target.name_} with {attack.attack_noun_}!"
            await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(actor.location_room_, actor, target, msg),
                                            exceptions=[actor, target])
            return -1 # a miss
        # is it a critical?
        critical = random.randint(1,100) < actor.critical_chance_
        logger.critical(f"{'CRIT' if critical else 'HIT'}: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
        # it hit, figure out damage
        msg = f"You {"critically" if critical else ""} {attack.attack_verb_} {article_plus_name(target.article_, target.name_)} with {attack.attack_noun_}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = f"{article_plus_name(actor.article_, actor.name_, cap=True)} {"critically" if critical else ""} {attack.attack_verb_}s you with {attack.attack_noun_}!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg))
        msg = f"{article_plus_name(actor.article_, actor.name_, cap=True)} {"critically" if critical else ""} {attack.attack_verb_}s {target.name_} with {attack.attack_noun_}!"
        await actor.location_room_.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room_, actor, target, msg),
                                        exceptions=[actor, target])
        total_damage = 0
        if len(attack.potential_damage_) == 0:
            logger.warning(f"no damage types in attack by {actor.rid}: {attack.to_dict()}")
        for dp in attack.potential_damage_:
            damage = dp.roll_damage()
            if critical:
                damage *= (100 + actor.critical_damage_bonus_) / 100
            dmg_mult = target.damage_resistances_.get(dp.damage_type_)
            damage = damage * dmg_mult - target.damage_reduction_.get(dp.damage_type_)
            await cls.do_damage(actor, target, damage, dp.damage_type_)
            total_damage += damage
            logger.critical(f"did {damage} {dp.damage_type_.word()} damage to {target.rid}")
        logger.critical(f"total damage: {total_damage}")
        return total_damage
            


    @classmethod
    async def process_fighting(cls):
        logger = CustomDetailLogger(__name__, prefix="process_fighting()> ")
        logger.debug3("beginning")
        logger.debug3(f"num characters_fighting_: {len(cls.game_state.characters_fighting_)}")
        for c in cls.game_state.characters_fighting_:
            total_dmg = 0
            if c.equipped_[EquipLocation.MAIN_HAND] != None \
            or c.equipped_[EquipLocation.BOTH_HANDS] != None:
                num_attacks = c.num_main_hand_attacks_
                if c.equipped_[EquipLocation.BOTH_HANDS] != None:
                    hands = "both hands"
                    weapon = c.equipped_[EquipLocation.BOTH_HANDS]
                else:
                    hands = "main hand"
                    weapon = c.equipped_[EquipLocation.MAIN_HAND]
                logger.critical(f"character: {c.rid} attacking {num_attacks}x with {weapon.name_} in {hands})")
                logger.critical(f"weapon: +{weapon.attack_bonus_} {weapon.damage_type_}: {weapon.damage_num_dice_}d{weapon.damage_dice_size_} +{weapon.damage_bonus_}")
                for n in range(num_attacks):
                    attack_data = AttackData(
                        damage_type=weapon.damage_type_, 
                        damage_num_dice=weapon.damage_num_dice_, 
                        damage_dice_size=weapon.damage_dice_size_, 
                        damage_bonus=weapon.damage_bonus_, 
                        attack_verb=weapon.damage_type_.verb(), 
                        attack_noun=weapon.damage_type_.noun(),
                        attack_bonus=weapon.attack_bonus_
                        )
                    logger.critical(f"attack_data: {attack_data.to_dict()}")
                    total_dmg += await cls.do_single_attack(c, c.fighting_whom_, attack_data)
            if c.equipped_[EquipLocation.OFF_HAND] != None:
                num_attacks = c.num_off_hand_attacks_
                weapon = c.equipped[EquipLocation.OFF_HAND]
                logger.critical(f"character: {c.rid} attacking, {num_attacks} with {weapon.name_} in off hand)")
                for n in range(num_attacks):
                    attack_data = AttackData(
                        damage_type=weapon.damage_type_, 
                        damage_num_dice=weapon.damage_num_dice_, 
                        damage_dice_size=weapon.damage_dice_size_,
                        damage_bonus=weapon.damage_modifier_, 
                        attack_verb=weapon.DamageType.verb(weapon.damage_type), 
                        attack_noun=DamageType.noun(weapon.damage_type),
                        attack_bonus=weapon.attack_bonus_
                        )
                    total_dmg += await cls.do_single_attack(c, c.fighting_whom_, attack_data)
            if not c.equipped_[EquipLocation.MAIN_HAND] and not c.equipped_[EquipLocation.BOTH_HANDS] and not c.equipped_[EquipLocation.OFF_HAND]:        
                logger.critical(f"character: {c.rid} attacking, {len(c.natural_attacks_)} natural attacks)")
                for natural_attack in c.natural_attacks_:
                    logger.critical(f"natural_attack: {natural_attack.to_dict()}")
                    if c.fighting_whom_:
                        total_dmg += await cls.do_single_attack(c, c.fighting_whom_, natural_attack)
            if total_dmg > 0 and c.fighting_whom_ != None:
                status_desc = c.fighting_whom_.get_status_description()
                msg = f"{article_plus_name(c.fighting_whom_.article_, c.fighting_whom_.name_, cap=True)} is {status_desc}"
                await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, c.fighting_whom_, msg))
                msg = f"You are {status_desc}"
                await c.fighting_whom_.echo(CommTypes.DYNAMIC, msg, set_vars(c.fighting_whom_, c, c.fighting_whom_, msg))
                msg = f"{article_plus_name(c.article_, c.name_, cap=True)} is {status_desc}"
                await c.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(c.location_room_, c, c.fighting_whom_, msg),
                                            exceptions=[c, c.fighting_whom_])
