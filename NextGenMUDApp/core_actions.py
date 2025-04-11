from .structured_logger import StructuredLogger
import math
import random
from .config import Config, default_app_config
from .constants import Constants
from .communication import CommTypes
from .core_actions_interface import CoreActionsInterface
from .comprehensive_game_state_interface import GameStateInterface
from .nondb_models.character_interface import EquipLocation
from .nondb_models.actors import ActorType, Actor
from .nondb_models.character_interface import CharacterInterface, PermanentCharacterFlags, TemporaryCharacterFlags
from .nondb_models.attacks_and_damage import AttackData, DamageType
from .nondb_models.object_interface import ObjectInterface, ObjectFlags
from .nondb_models.objects import Object
from .nondb_models.rooms import Room
from .nondb_models.triggers import TriggerType, TriggerFlags
from .utility import set_vars, firstcap, article_plus_name, roll_dice, ticks_from_seconds


class CoreActions(CoreActionsInterface):
    config: Config = default_app_config
    game_state: GameStateInterface = GameStateInterface.get_instance()

    async def do_look_room(self, actor: Actor, room: Room):
        logger = StructuredLogger(__name__, prefix="do_look_room()> ")
        logger.debug3("starting")
        # await actor.send_text(CommTypes.STATIC, room.description)
        logger.debug3("room parts")
        msg_parts = [ room.name , room.description ]
        # TODO:M: handle batching multiples
        logger.debug3("characters")
        for character in room.characters:
            if character != actor:
                logger.debug3(f"character: {character.rid}")
                if character.fighting_whom:
                    if character.fighting_whom == actor:
                        msg_parts.append(character.art_name_cap + " is here, fighting you!")
                    else:
                        msg_parts.append(character.art_name_cap + " is here, fighting " + character.fighting_whom.art_name + "!")
                else:
                    # print("character.article: " + character.article_)
                    # print("character.name: " + character.name)
                    msg_parts.append(character.art_name_cap + " is here.")
        logger.debug3("objects")
        for object in room.contents: 
            msg_parts.append(object.art_name_cap + " is here.")
        logger.debug3(f"Sending room description to actor for: {room.name}")
        await actor.send_text(CommTypes.CLEARSTATIC, "")
        await actor.echo(CommTypes.STATIC, "\n".join(msg_parts), set_vars(actor, actor, room, msg_parts), game_state=self.game_state)

        
    async def do_look_character(self, actor: Actor, target: 'Character'):
        logger = StructuredLogger(__name__, prefix="do_look_character()> ")
        msg = firstcap(target.description) + "\n" + f"{firstcap(target.pronoun_subject)} is {target.get_status_description()}"
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)


    async def do_look_object(self, actor: Actor, target: 'Object'):
        logger = StructuredLogger(__name__, prefix="do_look_object()> ")
        msg_parts = [ target.description ]
        if target.has_flags(ObjectFlags.IS_CONTAINER) and not target.has_flags(ObjectFlags.IS_CONTAINER_LOCKED):
            if len(target.contents) == 0:
                msg_parts.append(firstcap(target.pronoun_subject) + " is empty.")
            else:
                msg_parts.append(firstcap(target.pronoun_subject) + " contains:\n" + Object.collapse_name_multiples(target.contents, "\n"))
        msg = '\n'.join(msg_parts)
        await actor.echo(CommTypes.STATIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)


    async def arrive_room(self, actor: Actor, room: Room, room_from: Room = None):
        logger = StructuredLogger(__name__, prefix="arriveRoom()> ")
        logger.debug3(f"actor: {actor}, room: {room}, room_from: {room_from}")

        def reset_triggers_by_room(room: Room):
            for trigger in room.triggers_by_type.get(TriggerType.TIMER_TICK, []):
                if trigger.are_flags_set(TriggerFlags.ONLY_WHEN_PC_ROOM):
                    trigger.reset_timer()
            for ch in room.get_characters():
                for trigger in ch.triggers_by_type.get(TriggerType.TIMER_TICK, []):
                    if trigger.are_flags_set(TriggerFlags.ONLY_WHEN_PC_ROOM):
                        trigger.reset_timer()

        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to arrive in a room.")
        if actor.location_room is not None:
            raise Exception("Actor must not already be in a room to arrive in a room.")
        
        old_room = actor.location_room
        actor.location_room = room
        room.add_character(actor)
        # await room.send_text("dynamic", f"{actor.name} arrives.", exceptions=[actor])
        room_msg = f"{actor.art_name_cap} arrives."
        vars = set_vars(actor, actor, actor, room_msg)
        await self.do_look_room(actor, actor.location_room)
        await room.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=[actor], game_state=self.game_state)
        # reset trigger timers
        reset_triggers_by_room(room)
        # was this a zone change?
        if old_room == None or old_room.zone != room.zone:
            # go through every room in new zone
            for r in room.zone.rooms.values():
                # reset trigger timers
                reset_triggers_by_room(r)                   
        await self.do_aggro(actor)
        if actor.fighting_whom == None and actor.group_id is not None \
            and not actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            for c in room.get_characters():
                if c != actor and c.group_id == actor.group_id and c.fighting_whom != None \
                    and not c.has_perm_flags(PermanentCharacterFlags.IS_PC) \
                        and c.fighting_whom != actor:
                    msg = f"You join the attack against {c.fighting_whom.art_name}!"
                    vars = set_vars(actor, actor, c.fighting_whom, msg)
                    await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                    msg = f"{actor.art_name_cap} joins the attack against {c.fighting_whom.art_name}!"
                    vars = set_vars(actor, actor, c.fighting_whom, msg)
                    await room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c.fighting_whom], game_state=self.game_state)
                    msg = f"{actor.art_name_cap} joins the attack against you!"
                    vars = set_vars(actor, actor, c.fighting_whom, msg)
                    await c.fighting_whom.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                    self.start_fighting(actor, c.fighting_whom)
        # # TODO:L: figure out what direction "from" based upon back-path
        # actor.location_room.send_text("dynamic", f"{actor.name} arrives.", exceptions=[actor])


    async def world_move(self, actor: Actor, direction: str):
        logger = StructuredLogger(__name__, prefix="worldMove()> ")
        logger.debug3(f"actor: {actor}")

        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to move.")
        
        if not direction in actor.location_room.exits:
            msg = "You can't go that direction from here."
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            return
        
        if actor.fighting_whom != None:
            msg = "You can't move while fighting!"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            return
        
        msg = f"{actor.art_name_cap} leaves {direction}."
        vars = set_vars(actor.location_room, actor, actor, msg, { 'direction': direction })
        await actor.location_room.echo("dynamic", msg, exceptions=[actor], game_state=self.game_state)
        await actor.send_text("dynamic", f"You leave {direction}.")
        old_room = actor.location_room
        destination = actor.location_room.exits[direction]
        if "." in destination:
            zone_id, room_id = destination.split(".")
        else:
            zone_id = old_room.zone.id
            room_id = destination
        new_room = self.game_state.get_zone_by_id(zone_id).rooms[room_id]
        actor.location_room.remove_character(actor)
        actor.location_room = None
        await self.arrive_room(actor, new_room, old_room)


    # async def do_echo(actor: Actor, comm_type: CommTypes, text: str):
    #     logger = StructuredLogger(__name__, prefix="do_echo()> ")
    #     logger.debug(f"actor: {actor}, text: {text}")
    #     if actor.actor_type == ActorType.CHARACTER and actor.connection_ != None: 
    #         await actor.send_text(comm_type, text)
    #     # check triggers
    #     for trigger_type in [ TriggerType.CATCH_ANY ]:
    #         if trigger_type in actor.triggers_by_type:
    #             for trigger in actor.triggers_by_type[trigger_type]:
    #                 await trigger.run(actor, text, None)

    # @classmethod
    # async def do_tell(self, actor: Actor, target: Actor, text: str):
    #     logger = StructuredLogger(__name__, prefix="do_tell()> ")
    #     logger.debug(f"actor: {actor}, target: {target}, text: {text}")
    #     do_echo(actor, CommTypes.DYNAMIC, f"You tell {target.name}, \"{text}\"")
    #     do_echo(target, CommTypes.DYNAMIC, f"{actor.name} tells you, \"{text}\"")
    #     var = { 'actor': actor, 'text': text }
    #     for trigger_type in [ TriggerType.CATCH_TELL ]:
    #         if trigger_type in target.triggers_by_type:
    #             for trigger in target.triggers_by_type[trigger_type]:
    #                 await trigger.run(actor, text, var, None)


    async def start_fighting(self, subject: Actor, target: Actor):
        logger = StructuredLogger(__name__, prefix="start_fighting()> ")
        logger.debug(f"subject: {subject}, target: {target}")
        if subject.actor_type != ActorType.CHARACTER:
            raise Exception("Subject must be of type CHARACTER to start fighting.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to start fighting.")
        subject.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        target.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        subject.fighting_whom = target
        msg = f"You start fighting {target.art_name}!"
        await subject.echo(CommTypes.DYNAMIC, msg, set_vars(subject, subject, target, msg), game_state=self.game_state)
        msg = f"{subject.art_name_cap} starts fighting you!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, subject, target, msg), game_state=self.game_state)
        msg = f"{subject.art_name_cap} starts fighting {target.art_name}!"
        await subject.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(subject.location_room, subject, target, msg),
                                        exceptions=[subject, target], game_state=self.game_state)
        self.game_state.add_character_fighting(subject)
        logger.critical("checking for aggro or friends")
        for c in target.location_room.get_characters():
            logger.critical(f"checking {c.rid}: {c.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE)} / {c.group_id} / {subject.group_id}")
            if (c.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE) \
                or (c.group_id == subject.group_id and c.group_id != None)) \
                 and c != subject and c.fighting_whom == None:
                logger.critical(f"found {c.rid} joining in")
                msg = f"You join the attack against {target.art_name}!"
                vars = set_vars(c, c, target, msg)
                await c.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{c.art_name_cap} joins the attack against you!"
                vars = set_vars(c, c, target, msg)
                await target.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{c.art_name_cap} joins the attack against {target.art_name}!"
                vars = set_vars(c, c, target, msg)
                await target.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[c, target], game_state=self.game_state)
                c.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
                c.fighting_whom = target
                self.game_state.add_character_fighting(c)
                

    def fight_next_opponent(self, actor: Actor):
        logger = StructuredLogger(__name__, prefix="fight_next_opponent()> ")
        logger.debug(f"actor: {actor}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to fight next opponent.")
        if actor.fighting_whom != None:
            # raise Exception("Actor must not be fighting anyone to fight next opponent.")
            return
        for c in actor.location_room.get_characters():
            if c.fighting_whom == actor:
                self.start_fighting(actor, c)
                break

    async def do_die(self, dying_actor: Actor, killer: Actor = None, other_killer: str = None):
        # TODO:L: maybe do "x kills you"
        from .nondb_models.objects import Corpse
        logger = StructuredLogger(__name__, prefix="do_die()> ")
        msg = f"You die!"
        await dying_actor.echo(CommTypes.DYNAMIC, msg, set_vars(dying_actor, dying_actor, dying_actor, msg), game_state=self.game_state)

        if killer:
            msg = f"You kill {dying_actor.art_name}!"
            await killer.echo(CommTypes.DYNAMIC, msg, set_vars(killer, killer, dying_actor, msg), game_state=self.game_state)
            msg = f"{killer.art_name_cap} kills {dying_actor.art_name}!"
            await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(dying_actor, killer, dying_actor, msg), exceptions=[killer, dying_actor], 
                                            game_state=self.game_state)
        if other_killer != None:
            if other_killer == "":
                msg = f"{dying_actor.art_name_cap} dies!"
                await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg), exceptions=[dying_actor], game_state=self.game_state)
            else:
                msg = f"{other_killer} kills {dying_actor.art_name}!"
                await dying_actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(dying_actor, None, dying_actor, msg),
                                                exceptions=[dying_actor], game_state=self.game_state)
        if dying_actor in self.game_state.get_characters_fighting():
            self.game_state.remove_character_fighting(dying_actor)
        dying_actor.fighting_whom = None
        dying_actor.current_hit_points = 0
        room = dying_actor.location_room

        those_fighting = [c for c in room.get_characters() if c.fighting_whom == dying_actor]
        if not dying_actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            xp_amount = dying_actor.experience_points
            logger.critical(f"those_fighting: {those_fighting}")
            total_levels = sum([c.total_levels() for c in those_fighting])
            logger.critical(f"total_levels: {total_levels}")
            for c in those_fighting:
                this_xp = math.ceil(xp_amount * c.total_levels() / total_levels)
                c.experience_points += this_xp
                msg = f"You gain {this_xp} experience points!"
                await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, dying_actor, msg), game_state=self.game_state)

        for c in those_fighting:
            c.fighting_whom = None
            if c in self.game_state.get_characters_fighting():
                self.game_state.remove_character_fighting(c)
            self.fight_next_opponent(c)

        dying_actor.location_room.remove_character(dying_actor)
        corpse = Corpse(dying_actor, room)
        corpse.transfer_inventory()
        room.add_object(corpse)
        for c in room.characters:
            if c != dying_actor and c.has_perm_flags(PermanentCharacterFlags.IS_PC):
                logger.debug(f"{c.rid} is refreshing room")
                await self.do_look_room(c, room)
        if dying_actor.spawned_from:
            dying_actor.spawned_from.spawned.remove(dying_actor)
            if dying_actor.spawned_from.current_quantity < dying_actor.spawned_from.desired_quantity:
                character_def = self.game_state.get_world_definition().find_character_definition(dying_actor.id)
                if character_def:
                    in_ticks = ticks_from_seconds(dying_actor.spawned_from.respawn_time_min 
                                                    + random.randint(0, dying_actor.spawned_from.respawn_time_max 
                                                                    - dying_actor.spawned_from.respawn_time_min))
                    vars = { 'spawn_data': dying_actor.spawned_from }
                    self.game_state.add_scheduled_action(dying_actor.spawned_from.owner, "respawn", in_ticks=in_ticks,
                                                        vars=vars, func=lambda a,v: self.game_state.respawn_character(a,v))
        self.game_state.remove_character(dying_actor)
        dying_actor.is_deleted = True


    async def do_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True):
        logger = StructuredLogger(__name__, prefix="do_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to do damage.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to do damage.")
        
        if damage < 1 and damage > 0.5:
            damage = 1
        elif damage < 1:
            damage = 0
        else:
            damage = int(damage)
        target.current_hit_points -= damage
        if do_msg:
            msg = f"You do {damage} {damage_type.word()} damage to {target.art_name}!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = f"{actor.art_name_cap} does {damage} {damage_type.word()} damage to you!"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = (f"{actor.art_name_cap} does "
                f"{damage} {damage_type.word()} damage to {target.art_name}!")
            await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(actor.location_room, actor, target, msg),
                                            exceptions=[actor, target], game_state=self.game_state)
        if target.current_hit_points <= 0:
            await self.do_die(target, actor)
        else:
            if target.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
                target.remove_states_by_flag(TemporaryCharacterFlags.IS_SLEEPING)
                target.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)
                msg = f"{target.art_name_cap} wakes up!"
                await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, target, target, msg), game_state=self.game_state)
                msg = f"You wake up!"
                await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, target, target, msg), game_state=self.game_state)
                msg = f"{target.art_name_cap} wakes up!"
                await target.location_room.echo(CommTypes.DYNAMIC, msg,
                                                set_vars(target.location_room, target, target, msg),
                                                exceptions=[target], game_state=self.game_state)
                

    async def do_calculated_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True) -> int:
        logger = StructuredLogger(__name__, prefix="do_calculated_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to do damage.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to do damage.")
        damage = damage * target.damage_resistances.get(damage_type) - target.damage_reduction.get(damage_type)
        await self.do_damage(actor, target, damage, damage_type, do_msg)
        return damage


    async def do_single_attack(self, actor: Actor, target: Actor, attack: AttackData) -> int:
        # TODO:M: figure out weapons
        # TODO:L: deal with nouns and verbs correctly
        logger = StructuredLogger(__name__, prefix="do_single_attack()> ")
        logger.critical(f"actor: {actor.rid}, target: {target.rid}")
        logger.critical(f"attackdata: {attack.to_dict()}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to attack.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to attack.")
        hit_modifier = actor.hit_modifier + attack.attack_bonus
        logger.critical(f"dodge_dice_number: {target.dodge_dice_number}, dodge_dice_size: {target.dodge_dice_size}, dodge_modifier: {target.dodge_modifier}")
        dodge_roll = roll_dice(target.dodge_dice_number, target.dodge_dice_size) + target.dodge_modifier
        hit_roll = random.randint(1, 100)
        if hit_roll + hit_modifier < dodge_roll:
            logger.critical(f"MISS: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
            msg = f"You miss {target.art_name} with {attack.attack_noun}!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = f"{actor.art_name_cap} misses you with {attack.attack_noun}!"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = f"{actor.art_name_cap} misses {target.name} with {attack.attack_noun}!"
            await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(actor.location_room, actor, target, msg),
                                            exceptions=[actor, target], game_state=self.game_state)
            return -1 # a miss
        # is it a critical?
        critical = random.randint(1,100) < actor.critical_chance
        logger.critical(f"{'CRIT' if critical else 'HIT'}: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
        # it hit, figure out damage
        msg = f"You {"critically " if critical else ""}{attack.attack_verb} {target.art_name} with {attack.attack_noun}!"
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
        msg = f"{actor.art_name_cap} {"critically " if critical else ""}{attack.attack_verb} you with {attack.attack_noun}!"
        await target.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
        msg = f"{actor.art_name_cap} {"critically " if critical else ""}{attack.attack_verb} {target.name} with {attack.attack_noun}!"
        await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(actor.location_room, actor, target, msg),
                                        exceptions=[actor, target], game_state=self.game_state)
        total_damage = 0
        if len(attack.potential_damage_) == 0:
            logger.warning(f"no damage types in attack by {actor.rid}: {attack.to_dict()}")
        for dp in attack.potential_damage_:
            damage = dp.roll_damage()
            if critical:
                damage *= (100 + actor.critical_damage_bonus) / 100
            await self.do_calculated_damage(actor, target, damage, dp.damage_type)
            total_damage += damage
            logger.critical(f"did {damage} {dp.damage_type.word()} damage to {target.rid}")
        logger.critical(f"total damage: {total_damage}")
        return total_damage
            

    async def process_fighting(self):
        logger = StructuredLogger(__name__, prefix="process_fighting()> ")
        logger.debug3("beginning")
        logger.critical(f"num characters_fighting_: {len(self.game_state.get_characters_fighting())}")
        for c in self.game_state.get_characters_fighting():
            total_dmg = 0
            if c.equipped[EquipLocation.MAIN_HAND] != None \
            or c.equipped[EquipLocation.BOTH_HANDS] != None:
                num_attacks = c.num_main_hand_attacks
                if c.equipped[EquipLocation.BOTH_HANDS] != None:
                    hands = "both hands"
                    weapon = c.equipped[EquipLocation.BOTH_HANDS]
                else:
                    hands = "main hand"
                    weapon = c.equipped[EquipLocation.MAIN_HAND]
                logger.critical(f"character: {c.rid} attacking {num_attacks}x with {weapon.name} in {hands})")
                logger.critical(f"weapon: +{weapon.attack_bonus} {weapon.damage_type}: {weapon.damage_num_dice}d{weapon.damage_dice_size} +{weapon.damage_bonus}")
                for n in range(num_attacks):
                    attack_data = AttackData(
                        damage_type=weapon.damage_type, 
                        damage_num_dice=weapon.damage_num_dice, 
                        damage_dice_size=weapon.damage_dice_size, 
                        damage_bonus=weapon.damage_bonus, 
                        attack_verb=weapon.damage_type.verb(), 
                        attack_noun=weapon.damage_type.noun(),
                        attack_bonus=weapon.attack_bonus
                        )
                    logger.critical(f"attack_data: {attack_data.to_dict()}")
                    total_dmg += await self.do_single_attack(c, c.fighting_whom, attack_data)
            if c.equipped[EquipLocation.OFF_HAND] != None:
                num_attacks = c.num_off_hand_attacks
                weapon = c.equipped[EquipLocation.OFF_HAND]
                logger.critical(f"character: {c.rid} attacking, {num_attacks} with {weapon.name} in off hand)")
                for n in range(num_attacks):
                    attack_data = AttackData(
                        damage_type=weapon.damage_type, 
                        damage_num_dice=weapon.damage_num_dice, 
                        damage_dice_size=weapon.damage_dice_size,
                        damage_bonus=weapon.damage_modifier, 
                        attack_verb=weapon.DamageType.verb(weapon.damage_type), 
                        attack_noun=DamageType.noun(weapon.damage_type),
                        attack_bonus=weapon.attack_bonus
                        )
                    total_dmg += await self.do_single_attack(c, c.fighting_whom, attack_data)
            if not c.equipped[EquipLocation.MAIN_HAND] and not c.equipped[EquipLocation.BOTH_HANDS] and not c.equipped[EquipLocation.OFF_HAND]:        
                logger.critical(f"character: {c.rid} attacking, {len(c.natural_attacks)} natural attacks)")
                for natural_attack in c.natural_attacks:
                    logger.critical(f"natural_attack: {natural_attack.to_dict()}")
                    if c.fighting_whom:
                        total_dmg += await self.do_single_attack(c, c.fighting_whom, natural_attack)
            if total_dmg > 0 and c.fighting_whom != None:
                status_desc = c.fighting_whom.get_status_description()
                msg = f"{c.fighting_whom.art_name_cap} is {status_desc}"
                await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, c.fighting_whom, msg), game_state=self.game_state)
                msg = f"You are {status_desc}"
                await c.fighting_whom.echo(CommTypes.DYNAMIC, msg, set_vars(c.fighting_whom, c, c.fighting_whom, msg), game_state=self.game_state)
                msg = f"{c.fighting_whom.art_name_cap} is {status_desc}"
                await c.location_room.echo(CommTypes.DYNAMIC, msg,
                                            set_vars(c.location_room, c, c.fighting_whom, msg),
                                            exceptions=[c, c.fighting_whom], game_state=self.game_state)
            if c.fighting_whom != None and c.fighting_whom.fighting_whom == None and c.fighting_whom.current_hit_points > 0:
                await self.start_fighting(c.fighting_whom, c)
    
    async def do_aggro(self, actor: Actor):
        from NextGenMUDApp.skills import Skills
        logger = StructuredLogger(__name__, prefix="do_aggro()> ")
        logger.critical(f"actor: {actor}")
        if actor.actor_type != ActorType.CHARACTER:
            logger.critical(f"{actor.rid} is not character")
            raise Exception("Actor must be of type CHARACTER to aggro.")
        if not actor.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE):
            logger.critical(f"{actor.rid} is not aggressive")
            # not aggressive
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            logger.critical(f"{actor.rid} is sitting")
            msg = "You can't aggro while sitting!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            logger.critical(f"{actor.rid} is sleeping")
            msg = "You can't aggro while sleeping!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            logger.critical(f"{actor.rid} is stunned")
            msg = "You can't aggro while stunned!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return
        elif actor.fighting_whom != None:
            # looks like this could be spammy so no msg
            logger.critical(f"{actor.rid} is fighting")
            return
        for c in actor.location_room.characters:
            if c != actor and c.actor_type == ActorType.CHARACTER \
                and c.has_perm_flags(PermanentCharacterFlags.IS_PC):

                logger.critical(f"{actor.rid} checking {c.rid}")

                if (c.has_perm_flags(PermanentCharacterFlags.IS_INVISIBLE) \
                or c.has_temp_flags(TemporaryCharacterFlags.IS_INVISIBLE)) \
                and not actor.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE) \
                and not actor.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE):
                    continue

                if c.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
                    if Skills.stealthcheck(c, actor):
                        continue

                logger.critical(f"{actor.rid} aggroing {c.rid}")
                msg = f"You attack {c.art_name}!"
                vars = set_vars(actor, actor, c, msg)
                await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{actor.art_name_cap} attacks you!"
                vars = set_vars(actor, actor, c, msg)
                await c.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{actor.art_name_cap} attacks {c.art_name}!"
                vars = set_vars(actor, actor, c, msg)
                await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c], game_state=self.game_state)
                await self.start_fighting(actor, c)
                await self.start_fighting(c, actor)
                return


    