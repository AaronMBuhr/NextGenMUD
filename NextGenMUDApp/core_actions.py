from custom_detail_logger import CustomDetailLogger
import random
from .config import Config, default_app_config
from .constants import Constants
from .communication import CommTypes
from .core_actions_interface     import CoreActionsInterface
from .comprehensive_game_state_interface import GameStateInterface
from .nondb_models.actors import ActorType, Actor
from .nondb_models.character_interface import CharacterInterface, PermanentCharacterFlags, TemporaryCharacterFlags
from .nondb_models.attacks_and_damage import AttackData, DamageType
from .nondb_models.object_interface import ObjectInterface, ObjectFlags
from .nondb_models.rooms import Room
from .nondb_models.triggers import TriggerType
from .utility import set_vars, firstcap, article_plus_name, roll_dice, ticks_from_seconds


class CoreActions(CoreActionsInterface):
    config: Config = default_app_config
    game_state: GameStateInterface = GameStateInterface.get_instance()

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
                        msg_parts.append(character.art_name_cap + " is here, fighting you!")
                    else:
                        msg_parts.append(character.art_name_cap + " is here, fighting " + character.fighting_whom_.art_name + "!")
                else:
                    # print("character.article: " + character.article_)
                    # print("character.name: " + character.name_)
                    msg_parts.append(character.art_name_cap + " is here.")
        logger.debug("objects")
        for object in room.contents_: 
            msg_parts.append(object.art_name_cap + " is here.")
        logger.debug(f"Sending room description to actor for: {room.name_}")
        await actor.send_text(CommTypes.CLEARSTATIC, "")
        await actor.echo(CommTypes.STATIC, "\n".join(msg_parts), set_vars(actor, actor, room, msg_parts), game_state=cls.game_state)

        
    async def do_look_character(cls, actor: Actor, target: 'Character'):
        logger = CustomDetailLogger(__name__, prefix="do_look_character()> ")
        msg = firstcap(target.description_) + "\n" + f"{firstcap(target.pronoun_subject_)} is {target.get_status_description()}"
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)


    async def do_look_object(cls, actor: Actor, target: 'Object'):
        logger = CustomDetailLogger(__name__, prefix="do_look_object()> ")
        msg_parts = [ target.description_ ]
        if target.has_flags(ObjectFlags.IS_CONTAINER) and not target.has_flags(ObjectFlags.IS_CONTAINER_LOCKED):
            if len(target.contents_) == 0:
                msg_parts.append(firstcap(target.pronoun_subject_) + " is empty.")
            else:
                msg_parts.append(firstcap(target.pronoun_subject_) + " contains:\n" + Object.collapse_name_multiples(target.contents_, "\n"))
        msg = '\n'.join(msg_parts)
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)


    async def arrive_room(cls, actor: Actor, room: Room, room_from: Room = None):
        logger = CustomDetailLogger(__name__, prefix="arriveRoom()> ")
        logger.debug(f"actor: {actor}, room: {room}, room_from: {room_from}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to arrive in a room.")
        if actor.location_room is not None:
            raise Exception("Actor must not already be in a room to arrive in a room.")
        
        actor.location_room = room
        room.add_character(actor)
        # await room.send_text("dynamic", f"{actor.name_} arrives.", exceptions=[actor])
        room_msg = f"{actor.name} arrives."
        vars = set_vars(actor, actor, actor, room_msg)
        await cls.do_look_room(actor, actor.location_room)
        await room.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=[actor], game_state=cls.game_state)
        cls.do_aggro(actor)
        # # TODO:L: figure out what direction "from" based upon back-path
        # actor.location_room.send_text("dynamic", f"{actor.name_} arrives.", exceptions=[actor])


    async def world_move(cls, actor: Actor, direction: str):
        logger = CustomDetailLogger(__name__, prefix="worldMove()> ")
        logger.debug(f"actor: {actor}")

        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to move.")
        
        if not direction in actor.location_room.exits_:
            raise Exception(f"Location {actor.location_room.id} does not have an exit in direction {direction}")
        
        actor.location_room.echo("dynamic", f"{firstcap(actor.name)} leaves {direction}", exceptions=[actor], game_state=cls.game_state)
        await actor.send_text("dynamic", f"You leave {direction}")
        old_room = actor.location_room
        destination = actor.location_room.exits_[direction]
        if "." in destination:
            zone_id, room_id = destination.split(".")
        else:
            zone_id = old_room.zone_.id
            room_id = destination
        new_room = cls.game_state.get_zone_by_id(zone_id).rooms[room_id]
        actor.location_room.remove_character(actor)
        actor.location_room = None
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


    async def start_fighting(cls, subject: Actor, target: Actor):
        logger = CustomDetailLogger(__name__, prefix="start_fighting()> ")
        logger.debug(f"subject: {subject}, target: {target}")
        if subject.actor_type != ActorType.CHARACTER:
            raise Exception("Subject must be of type CHARACTER to start fighting.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to start fighting.")
        subject.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        target.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        subject.fighting_whom_ = target
        msg = f"You start fighting {target.art_name}!"
        await subject.echo(CommTypes.DYNAMIC, msg, set_vars(subject, subject, target, msg), game_state=cls.game_state)
        msg = f"{subject.art_name_cap} starts fighting you!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, subject, target, msg), game_state=cls.game_state)
        msg = f"{subject.art_name_cap} starts fighting {target.art_name}!"
        await subject.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(subject.location_room, subject, target, msg),
                                        exceptions=[subject, target], game_state=cls.game_state)
        cls.game_state.add_character_fighting(subject)
        for c in target.location_room.characters_:
            if c.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE) \
                 and c != subject and c.fighting_whom_ == None:
                msg = f"You join the attack against {target.art_name}!"
                set_vars(c, c, target, msg)
                c.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                msg = f"{c.art_name_cap} joins the attack against you!"
                set_vars(c, c, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                msg = f"{c.art_name_cap} joins the attack against {target.art_name}!"
                set_vars(c, c, target, msg)
                target.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[c], game_state=cls.game_state)
                c.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
                c.fighting_whom_ = target
                

    async def do_die(cls, dying_actor: Actor, killer: Actor = None, other_killer: str = None):
        # TODO:L: maybe do "x kills you"
        logger = CustomDetailLogger(__name__, prefix="do_die()> ")
        msg = f"You die!"
        await dying_actor.echo(CommTypes.DYNAMIC, msg, set_vars(dying_actor, dying_actor, dying_actor, msg), game_state=cls.game_state)

        if killer:
            msg = f"You kill {dying_actor.art_name}!"
            await killer.echo(CommTypes.DYNAMIC, msg, set_vars(killer, killer, dying_actor, msg), game_state=cls.game_state)
            msg = f"{killer.art_name_cap} kills {dying_actor.art_name}!"
            await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(dying_actor, killer, dying_actor, msg), exceptions=[killer, dying_actor], 
                                            game_state=cls.game_state)
        if other_killer != None:
            if other_killer == "":
                msg = f"{dying_actor.art_name_cap} dies!"
                await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg), exceptions=[dying_actor], game_state=cls.game_state)
            else:
                msg = f"{other_killer} kills {dying_actor.art_name}!"
                await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg),
                                                exceptions=[dying_actor], game_state=cls.game_state)
        if dying_actor in cls.game_state.get_characters_fighting():
            cls.game_state.remove_character_fighting(dying_actor)
        if killer:
            killer.fighting_whom_ = None
            cls.game_state.remove_character_fighting(killer)
        for c in cls.game_state.get_characters_fighting():
            if killer and c.fighting_whom_ == killer:
                cls.start_fighting(killer, c)
            if c.fighting_whom_ == dying_actor:
                c.fighting_whom_ = None

        dying_actor.fighting_whom_ = None
        dying_actor.current_hit_points_ = 0
        room = dying_actor.location_room
        dying_actor.location_room.remove_character(dying_actor)
        corpse = Corpse(dying_actor, room)
        corpse.transfer_inventory()
        room.add_object(corpse)
        for c in room.characters_:
            logger.debug(f"{c.rid} is refreshing room")
            await cls.do_look_room(c, room)
        if not dying_actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            xp_amount = dying_actor.experience_points
            those_fighting = [c for c in dying_actor.location_room.characters_ if c.fighting_whom_ == dying_actor]
            total_levels = sum([c.total_levels() for c in those_fighting])
            for c in those_fighting:
                this_xp = xp_amount * c.total_levels() / total_levels
                c.experience_points += this_xp
                msg = f"You gain {this_xp} experience points!"
                await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, dying_actor, msg), game_state=cls.game_state)
            dying_actor.is_deleted = True
            if dying_actor.spawned_from:
                dying_actor.spawned_from.spawned.remove(dying_actor)
                if dying_actor.spawned_from.current_quantity < dying_actor.spawned_from.desired_quantity:
                    character_def = cls.game_state.get_world_definition().find_character_definition(dying_actor.id)
                    if character_def:
                        in_ticks = ticks_from_seconds(dying_actor.spawned_from.respawn_time_min 
                                                      + random.randint(0, dying_actor.spawned_from.respawn_time_max 
                                                                       - dying_actor.spawned_from.respawn_time_min))
                        vars = { 'spawn_data': dying_actor.spawned_from }
                        cls.game_state.add_scheduled_action(dying_actor.spawned_from.owner, "respawn", in_ticks=in_ticks,
                                                            vars=vars, func=lambda a,v: cls.game_state.respawn_character(a,v))
            cls.game_state.remove_character(dying_actor)


    async def do_damage(cls, actor: Actor, target: Actor, damage: int, damage_type: DamageType):
        logger = CustomDetailLogger(__name__, prefix="do_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to do damage.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to do damage.")
        target.current_hit_points_ -= damage
        msg = f"You do {damage} {damage_type.word()} damage to {target.art_name}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
        msg = f"{actor.art_name_cap} does {damage} {damage_type.word()} damage to you!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
        msg = (f"{actor.art_name_cap} does "
            f"{damage} {damage_type.word()} damage to {target.art_name}!")
        await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room, actor, target, msg),
                                        exceptions=[actor, target], game_state=cls.game_state)
        if target.current_hit_points_ <= 0:
            await cls.do_die(target, actor)


    async def do_single_attack(cls, actor: Actor, target: Actor, attack: AttackData) -> int:
        # TODO:M: figure out weapons
        # TODO:L: deal with nouns and verbs correctly
        logger = CustomDetailLogger(__name__, prefix="do_single_attack()> ")
        logger.critical(f"actor: {actor.rid}, target: {target.rid}")
        logger.critical(f"attackdata: {attack.to_dict()}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to attack.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to attack.")
        hit_modifier = actor.hit_modifier_ + attack.attack_bonus
        logger.critical(f"dodge_dice_number_: {target.dodge_dice_number_}, dodge_dice_size_: {target.dodge_dice_size_}, dodge_modifier_: {target.dodge_modifier_}")
        dodge_roll = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_) + target.dodge_modifier_
        hit_roll = random.randint(1, 100)
        if hit_roll + hit_modifier < dodge_roll:
            logger.critical(f"MISS: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
            msg = f"You miss {target.art_name} with {attack.attack_noun_}!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
            msg = f"{actor.art_name_cap} misses you with {attack.attack_noun_}!"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
            msg = f"{actor.art_name_cap} misses {target.name} with {attack.attack_noun_}!"
            await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(actor.location_room, actor, target, msg),
                                            exceptions=[actor, target], game_state=cls.game_state)
            return -1 # a miss
        # is it a critical?
        critical = random.randint(1,100) < actor.critical_chance_
        logger.critical(f"{'CRIT' if critical else 'HIT'}: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
        # it hit, figure out damage
        msg = f"You {"critically" if critical else ""} {attack.attack_verb_} {target.art_name} with {attack.attack_noun_}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
        msg = f"{actor.art_name_cap} {"critically" if critical else ""} {attack.attack_verb_}s you with {attack.attack_noun_}!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=cls.game_state)
        msg = f"{actor.art_name_cap} {"critically" if critical else ""} {attack.attack_verb_}s {target.name} with {attack.attack_noun_}!"
        await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room, actor, target, msg),
                                        exceptions=[actor, target], game_state=cls.game_state)
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
            

    async def process_fighting(cls):
        logger = CustomDetailLogger(__name__, prefix="process_fighting()> ")
        logger.debug3("beginning")
        logger.debug3(f"num characters_fighting_: {len(cls.game_state.get_characters_fighting())}")
        for c in cls.game_state.get_characters_fighting():
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
                msg = f"{c.fighting_whom_.art_name_cap} is {status_desc}"
                await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, c.fighting_whom_, msg), game_state=cls.game_state)
                msg = f"You are {status_desc}"
                await c.fighting_whom_.echo(CommTypes.DYNAMIC, msg, set_vars(c.fighting_whom_, c, c.fighting_whom_, msg), game_state=cls.game_state)
                msg = f"{c.fighting_whom_.art_name_cap} is {status_desc}"
                await c.location_room_.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(c.location_room_, c, c.fighting_whom_, msg),
                                            exceptions=[c, c.fighting_whom_], game_state=cls.game_state)

    
    async def do_aggro(cls, actor: Actor):
        from NextGenMUDApp.character_classes import Skills
        logger = CustomDetailLogger(__name__, prefix="do_aggro()> ")
        logger.debug(f"actor: {actor}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to aggro.")
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            msg = "You can't aggro while sitting!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=cls.game_state)
            return
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            msg = "You can't aggro while sleeping!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=cls.game_state)
            return
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            msg = "You can't aggro while stunned!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=cls.game_state)
            return
        for c in actor.location_room.characters_:
            if c != actor and c.actor_type_ == ActorType.CHARACTER:

                if (c.has_perm_flags(PermanentCharacterFlags.IS_INVISIBLE) \
                or c.has_temp_flags(TemporaryCharacterFlags.IS_INVISIBLE)) \
                and not actor.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE) \
                and not actor.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE):
                    continue

                if c.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
                    if Skills.stealthcheck(c, actor):
                        continue
                    
                msg = f"You attack {c.art_name}!"
                set_vars(actor, actor, c, msg)
                actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                msg = f"{actor.art_name_cap} attacks you!"
                set_vars(actor, actor, c, msg)
                c.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                msg = f"{actor.art_name_cap} attacks {c.art_name}!"
                set_vars(actor, actor, c, msg)
                actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c], game_state=cls.game_state)
                await cls.start_fighting(c, actor)
                await cls.start_fighting(actor, c)
                return


    