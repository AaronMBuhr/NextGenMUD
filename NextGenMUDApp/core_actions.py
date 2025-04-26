from .structured_logger import StructuredLogger
import math
import random
import time
from typing import Dict, List, Tuple, Any

from .config import Config, default_app_config
from .communication import CommTypes
from .core_actions_interface import CoreActionsInterface
from .comprehensive_game_state_interface import GameStateInterface, EventType
from .nondb_models.actor_interface import ActorType
from .nondb_models.actors import Actor
from .nondb_models.actor_attitudes import ActorAttitude
from .nondb_models.attacks_and_damage import AttackData, PotentialDamage, DamageType
from .nondb_models.character_interface import CharacterInterface, PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags
from .nondb_models.rooms import Room
from .skills_core import Skills
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
        if room_from is None or room_from.zone != room.zone:
            # Check if there are already PCs in the zone
            pc_in_zone = False
            for player in self.game_state.players:
                if player.location_room and player.location_room.zone == room.zone:
                    pc_in_zone = True
                    break
            # Only reset zone triggers if there are no PCs in the zone
            if not pc_in_zone:
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

        old_room = actor.location_room
        destination = old_room.exits[direction]
        if "." in destination:
            zone_id, room_id = destination.split(".")
        else:
            zone_id = old_room.zone.id
            room_id = destination
        try:        
            new_room = self.game_state.get_zone_by_id(zone_id).rooms[room_id]
        except KeyError:
            msg = f"There was a problem moving that direction."
            if actor.actor_type == ActorType.CHARACTER and actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
                msg += f"> Zone: {zone_id}, Room: {room_id}"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            return
        msg = f"{actor.art_name_cap} leaves {direction}."
        vars = set_vars(actor.location_room, actor, actor, msg, { 'direction': direction })
        await actor.location_room.echo("dynamic", msg, exceptions=[actor], game_state=self.game_state)
        await actor.send_text("dynamic", f"You leave {direction}.")
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
        if subject.actor_type != ActorType.CHARACTER:
            raise Exception("Subject must be of type CHARACTER to fight.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to fight.")
        if subject.fighting_whom != None:
            # already fighting someone
            # TODO: maybe switch command, or just allow bringing someone else into the fight
            return
        if target.is_dead():
            # can't fight dead actors
            return
        subject.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        target.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        subject.fighting_whom = target
        if subject.has_perm_flags(PermanentCharacterFlags.IS_PC) and target.fighting_whom != subject:
            msg = f"You attack {target.art_name}!"
            vars = set_vars(subject, subject, target, msg)
            await subject.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{subject.art_name_cap} attacks you!"
            vars = set_vars(subject, subject, target, msg)
            await target.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{subject.art_name_cap} attacks {target.art_name}!"
            vars = set_vars(subject, subject, target, msg)
            await subject.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(subject.location_room, subject, target, msg),
                                        exceptions=[subject, target], game_state=self.game_state)
        tick_vars = { 'target': target }
        self.game_state.add_scheduled_event(subject, EventType.COMBAT_TICK, "combat_tick", tick_vars, 
                                            lambda a, t, c, v: self.handle_combat_tick_event(a, t, c, v))
        self.game_state.add_character_fighting(subject)
        logger.critical("checking for aggro or friends")
        
        # Player is initiating combat
        is_player_initiating = subject.has_perm_flags(PermanentCharacterFlags.IS_PC)
        # Combat is occurring in the room (any fighting)
        is_fighting_in_room = True
        
        for c in target.location_room.get_characters():
            logger.critical(f"checking {c.rid}: attitude={c.attitude}, group={c.group_id}")
            
            # Skip if already fighting or if this is the subject or target
            if c.fighting_whom is not None or c == subject or c == target:
                continue
                
            will_join_fight = False
            will_help_player = False
            
            # HOSTILE - Attack players on sight (handled in do_aggro)
            
            # UNFRIENDLY - If any fighting starts, join against player
            if c.attitude == ActorAttitude.UNFRIENDLY and is_fighting_in_room:
                # Join against player if player is involved
                if subject.has_perm_flags(PermanentCharacterFlags.IS_PC) or target.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    will_join_fight = True
                    # Select the player as target
                    if subject.has_perm_flags(PermanentCharacterFlags.IS_PC):
                        join_target = subject
                    else:
                        join_target = target
            
            # NEUTRAL - Do nothing
            
            # FRIENDLY - Help player if player starts fighting
            elif c.attitude == ActorAttitude.FRIENDLY and is_player_initiating:
                will_join_fight = True
                will_help_player = True
                join_target = target  # Help player attack their target
            
            # CHARMED - Neutral plus won't join if their group is attacked
            # (no special logic needed - they just don't join)
            
            # DOMINATED - Like FRIENDLY until control mechanics implemented
            elif c.attitude == ActorAttitude.DOMINATED and is_player_initiating:
                will_join_fight = True
                will_help_player = True
                join_target = target  # Help player attack their target
            
            # Group loyalty - members of same group help each other
            # But CHARMED NPCs ignore group loyalty
            elif c.group_id is not None and c.attitude != ActorAttitude.CHARMED:
                # Help group member under attack
                if c.group_id == target.group_id:
                    will_join_fight = True
                    join_target = subject  # Attack whoever is attacking group member
                # Join group member who's attacking
                elif c.group_id == subject.group_id:
                    will_join_fight = True
                    join_target = target  # Help group member attack their target
            
            if will_join_fight:
                logger.critical(f"found {c.rid} joining in against {join_target.rid}")
                msg = f"You join the attack against {join_target.art_name}!"
                vars = set_vars(c, c, join_target, msg)
                await c.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{c.art_name_cap} joins the attack against you!"
                vars = set_vars(c, c, join_target, msg)
                await join_target.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{c.art_name_cap} joins the attack against {join_target.art_name}!"
                vars = set_vars(c, c, join_target, msg)
                await join_target.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[c, join_target], game_state=self.game_state)
                c.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
                c.fighting_whom = join_target
                tick_vars = { 'target': join_target }
                self.game_state.add_scheduled_event(c, EventType.COMBAT_TICK, "combat_tick", tick_vars, 
                                                    lambda a, t, c, v: self.handle_combat_tick_event(a, t, c, v))
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


    async def do_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True, do_die=True) -> Tuple[int, int]:
        logger = StructuredLogger(__name__, prefix="do_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
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
        if target.current_hit_points <= 0 and do_die:
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
        return damage, target.current_hit_points
                

    async def do_calculated_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True, do_die=True) -> Tuple[int, int]:
        logger = StructuredLogger(__name__, prefix="do_calculated_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to accept damage.")
        target_resistance = (target.damage_resistances.get(damage_type) / 100)
        if target_resistance > 1:
            target_resistance = 1
        damage = damage * (1 - target_resistance) - target.damage_reduction.get(damage_type)
        if damage < 1:
            return 0
        damage, target_hp = await self.do_damage(actor, target, damage, damage_type, do_msg=do_msg, do_die=do_die)
        return damage, target_hp


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
            

    async def handle_combat_tick_event(self, actor: Actor, current_tick: int, game_state: 'ComprehensiveGameState',
                                       vars: Dict[str, Any]):
        logger = StructuredLogger(__name__, prefix="handle_combat_tick_event()> ")
        logger.debug3(f"handling combat tick for {actor.rid} against {vars['target'].rid}")
        total_dmg = 0
        target = vars['target']
        if actor.equipped[EquipLocation.MAIN_HAND] != None \
        or actor.equipped[EquipLocation.BOTH_HANDS] != None:
            num_attacks = actor.num_main_hand_attacks
            if actor.equipped[EquipLocation.BOTH_HANDS] != None:
                hands = "both hands"
                weapon = actor.equipped[EquipLocation.BOTH_HANDS]
            else:
                hands = "main hand"
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
            logger.critical(f"character: {actor.rid} attacking {num_attacks}x with {weapon.name} in {hands})")
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
                total_dmg += await self.do_single_attack(actor, target, attack_data)
        if actor.equipped[EquipLocation.OFF_HAND] != None:
            num_attacks = actor.num_off_hand_attacks
            weapon = actor.equipped[EquipLocation.OFF_HAND]
            logger.critical(f"character: {actor.rid} attacking, {num_attacks} with {weapon.name} in off hand)")
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
                total_dmg += await self.do_single_attack(actor, target, attack_data)
        if not c.equipped[EquipLocation.MAIN_HAND] and not c.equipped[EquipLocation.BOTH_HANDS] and not c.equipped[EquipLocation.OFF_HAND]:        
            logger.critical(f"character: {actor.rid} attacking, {len(actor.natural_attacks)} natural attacks)")
            for natural_attack in actor.natural_attacks:
                logger.critical(f"natural_attack: {natural_attack.to_dict()}")
                if target:
                    total_dmg += await self.do_single_attack(actor, target, natural_attack)
        if total_dmg > 0 and actor.target != None:
            status_desc = actor.fighting_whom.get_status_description()
            msg = f"{actor.target.art_name_cap} is {status_desc}"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = f"You are {status_desc}"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, actor, target, msg), game_state=self.game_state)
            msg = f"{target.art_name_cap} is {status_desc}"
            await target.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(target.location_room, actor, target, msg),
                                        exceptions=[actor, target], game_state=self.game_state)
            
        # TODO: what is this for?
        # if target != None \
        #     and target.fighting_whom != None \
        #         and target.fighting_whom.fighting_whom == None \
        #             and target.fighting_whom.current_hit_points > 0:
        #     await self.start_fighting(target.fighting_whom, actor)
    
    async def do_aggro(self, actor: Actor):
        logger = StructuredLogger(__name__, prefix="do_aggro()> ")
        logger.debug3(f"do_aggro() actor: {actor}")
        if actor.actor_type != ActorType.CHARACTER:
            logger.critical(f"{actor.rid} is not character")
            logger.error("Actor must be of type CHARACTER to aggro.")
        
        # Check if the actor is hostile (either by attitude or by aggressive flag)
        if not (actor.attitude == ActorAttitude.HOSTILE or actor.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE)):
            logger.debug3(f"{actor.rid} is not hostile or aggressive")
            # not hostile
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
                and c.has_perm_flags(PermanentCharacterFlags.IS_PC) \
                and not c.has_game_flags(GamePermissionFlags.IS_ADMIN):  # Don't aggro admins

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


    