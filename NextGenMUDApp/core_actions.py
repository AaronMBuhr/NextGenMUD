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
from .nondb_models.character_interface import CharacterInterface, PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags, EquipLocation
from .nondb_models.rooms import Room
from .skills_core import Skills
from .nondb_models.triggers import TriggerType, TriggerFlags
from .constants import Constants
from .llm_npc_conversation import NPCConversationHandler
from .utility import set_vars, firstcap, article_plus_name, roll_dice, ticks_from_seconds


class CoreActions(CoreActionsInterface):
    config: Config = default_app_config
    game_state: GameStateInterface = GameStateInterface.get_instance()

    # Direction opposites for flee mechanic
    OPPOSITE_DIRECTIONS = {
        'north': 'south', 'south': 'north',
        'east': 'west', 'west': 'east',
        'up': 'down', 'down': 'up',
        'northeast': 'southwest', 'southwest': 'northeast',
        'northwest': 'southeast', 'southeast': 'northwest',
        'in': 'out', 'out': 'in',
        'n': 's', 's': 'n',
        'e': 'w', 'w': 'e',
        'u': 'd', 'd': 'u',
        'ne': 'sw', 'sw': 'ne',
        'nw': 'se', 'se': 'nw',
    }

    def get_opposite_direction(self, direction: str) -> str:
        """Return the opposite direction, or None if unknown."""
        return self.OPPOSITE_DIRECTIONS.get(direction.lower())

    def find_exit_to_room(self, from_room: 'Room', target_room: 'Room') -> str:
        """
        Find which exit in from_room leads to target_room.
        Returns the direction name, or None if no exit leads there.
        
        This is used for flee direction weighting - we want to know which
        direction leads back to where the player came from, regardless of
        the actual compass direction (handles diagonal hallways, etc.).
        """
        if not from_room or not target_room:
            return None
        
        # Build the target room's full ID for comparison
        target_full_id = f"{target_room.zone.id}.{target_room.id}"
        
        for direction, exit_obj in from_room.exits.items():
            destination = exit_obj.destination
            # Normalize to full zone.room format
            if "." in destination:
                dest_full = destination
            else:
                dest_full = f"{from_room.zone.id}.{destination}"
            
            if dest_full == target_full_id:
                return direction
        
        # No exit leads back (one-way passage, pit, teleport, etc.)
        return None

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
                # Append * to NPCs with LLM conversation for display (testing indicator)
                has_llm = character.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None
                llm_marker = "*" if has_llm else ""
                display_name = character.art_name_cap + llm_marker
                if character.fighting_whom:
                    fighting_has_llm = character.fighting_whom.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None
                    fighting_llm_marker = "*" if fighting_has_llm else ""
                    fighting_display_name = character.fighting_whom.art_name + fighting_llm_marker
                    if character.fighting_whom == actor:
                        msg_parts.append(display_name + " is here, fighting you!")
                    else:
                        msg_parts.append(display_name + " is here, fighting " + fighting_display_name + "!")
                else:
                    # print("character.article: " + character.article_)
                    # print("character.name: " + character.name)
                    msg_parts.append(display_name + " is here.")
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
        
        # Track which exit in the new room leads back to where we came from (for flee weighting)
        # This handles diagonal hallways, weird layouts, etc. - not just "opposite direction"
        actor.last_entered_from = None
        if room_from:
            actor.last_entered_from = self.find_exit_to_room(room, room_from)
        
        # logger.critical(f"arriving in {room.name} for {actor.rid}")
        actor.location_room = room
        room.add_character(actor)
        # await room.send_text("dynamic", f"{actor.name} arrives.", exceptions=[actor])
        room_msg = f"{actor.art_name_cap} arrives."
        vars = set_vars(actor, actor, actor, room_msg)
        await self.do_look_room(actor, actor.location_room)
        await room.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=[actor], game_state=self.game_state)
        
        # Send initial status update for PCs entering a room
        if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await actor.send_status_update()
        
        # Fire ON_ENTER triggers on the room itself
        if TriggerType.ON_ENTER in room.triggers_by_type:
            for trigger in room.triggers_by_type[TriggerType.ON_ENTER]:
                await trigger.run(actor, "", vars, self.game_state)
        
        # Fire ON_ENTER triggers on NPCs in the room when a player enters
        # This allows NPCs to react to players entering (e.g., greet them)
        # The NPC is the executor (commands go to NPC's queue), entering player is %s%/%S%
        if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            for npc in room.get_characters():
                if npc == actor:
                    continue
                if not npc.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    # Fire NPC's ON_ENTER triggers - NPC executes script, entering player in %s%/%S%
                    if TriggerType.ON_ENTER in npc.triggers_by_type:
                        npc_vars = set_vars(npc, actor, actor, room_msg)
                        for trigger in npc.triggers_by_type[TriggerType.ON_ENTER]:
                            await trigger.run(npc, "", npc_vars, self.game_state)
            
            # Fire ON_ENTER triggers on objects in the room
            # Objects execute immediately (no queue), entering player is %s%/%S%
            for obj in room.contents:
                if TriggerType.ON_ENTER in obj.triggers_by_type:
                    obj_vars = set_vars(obj, actor, actor, room_msg)
                    for trigger in obj.triggers_by_type[TriggerType.ON_ENTER]:
                        await trigger.run(obj, "", obj_vars, self.game_state)
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
        
        # # Check if existing characters in the room should aggro the arriving actor
        # logger.critical(f"checking for aggro in {room.name} - room has {len(room.get_characters())} characters")
        
        # # First: Check if the arriving character wants to aggro any existing room occupants
        # logger.critical(f"checking if {actor.rid} ({actor.art_name}) wants to aggro existing room occupants")
        incoming_aggroed = await self.do_aggro(actor)
        if incoming_aggroed:
            logger.debug3(f"{actor.rid} initiated aggro against room occupants")
            # Continue checking room occupants - they may still want to aggro on the incoming character
        
        # Second: Check if existing room occupants want to aggro the arriving character
        for c in room.get_characters():
            if c == actor:
                continue
            # logger.critical(f"checking if {c.rid} ({c.art_name}) should aggro {actor.rid} ({actor.art_name})")
            aggroed = await self.do_aggro(c)
            # if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            #     logger.critical(f"checked for aggro in {room.name} for {c.rid}: aggroed={aggroed}")
            # if aggroed:
            #     logger.critical(f"{c.rid} initiated aggro against {actor.rid}")
            #     # Continue checking other room occupants - don't break here
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
                    await self.start_fighting(actor, c.fighting_whom)
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
        
        # Stop meditating when moving
        if hasattr(actor, 'is_meditating') and actor.is_meditating:
            actor.is_meditating = False
            await actor.send_text(CommTypes.DYNAMIC, "You stop meditating.")

        old_room = actor.location_room
        exit_obj = old_room.exits[direction]
        
        # Check for closed/locked door
        if exit_obj.has_door:
            if exit_obj.is_closed:
                msg = f"{exit_obj.art_name_cap} is closed."
                vars = set_vars(actor, actor, actor, msg)
                await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                return
        
        destination = exit_obj.destination
        if "." in destination:
            zone_id, room_id = destination.split(".")
        else:
            zone_id = old_room.zone.id
            room_id = destination
        
        # Normalize destination to full zone.room format for guard check
        full_destination = f"{zone_id}.{room_id}"
        
        # Check if any guard blocks this destination
        blocking_guard = actor.get_guarded_destination(full_destination)
        if blocking_guard:
            msg = f"{blocking_guard.art_name_cap} blocks your path!"
            vars = set_vars(actor, actor, blocking_guard, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            return
        
        try:        
            new_room = self.game_state.get_zone_by_id(zone_id).rooms[room_id]
        except (KeyError, AttributeError):
            current_room_id = f"{old_room.zone.id}.{old_room.id}" if old_room.zone else f"unknown_zone.{old_room.id}"
            destination_id = f"{zone_id}.{room_id}"
            logger.warning(f"Invalid room reference: player in '{current_room_id}' tried to move {direction} to non-existent room '{destination_id}'")
            msg = f"There was a problem moving that direction."
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            return
        msg = f"{actor.art_name_cap} leaves {direction}."
        vars = set_vars(actor.location_room, actor, actor, msg, { 'direction': direction })
        await actor.location_room.echo("dynamic", msg, exceptions=[actor], game_state=self.game_state)
        await actor.send_text("dynamic", f"You leave {direction}.")
        
        # Fire ON_EXIT triggers before leaving the room
        await self._fire_exit_triggers(actor, old_room, direction)
        
        actor.location_room.remove_character(actor)
        actor.location_room = None
        await self.arrive_room(actor, new_room, old_room)


    async def _fire_exit_triggers(self, actor: Actor, room: Room, direction: str):
        """Fire ON_EXIT triggers when a character leaves a room."""
        from .nondb_models.character_interface import PermanentCharacterFlags
        
        exit_vars = set_vars(room, actor, actor, direction, {'direction': direction})
        
        # Fire room's ON_EXIT triggers (room executes script immediately)
        if TriggerType.ON_EXIT in room.triggers_by_type:
            for trigger in room.triggers_by_type[TriggerType.ON_EXIT]:
                await trigger.run(room, direction, exit_vars, self.game_state)
        
        # Fire NPC ON_EXIT triggers when a player leaves
        # NPCs execute script (commands queued), leaving player is %s%/%S%
        if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            for npc in room.get_characters():
                if npc == actor:
                    continue
                if not npc.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    if TriggerType.ON_EXIT in npc.triggers_by_type:
                        npc_vars = set_vars(npc, actor, actor, direction, {'direction': direction})
                        for trigger in npc.triggers_by_type[TriggerType.ON_EXIT]:
                            await trigger.run(npc, direction, npc_vars, self.game_state)
            
            # Fire object ON_EXIT triggers (objects execute immediately)
            for obj in room.contents:
                if TriggerType.ON_EXIT in obj.triggers_by_type:
                    obj_vars = set_vars(obj, actor, actor, direction, {'direction': direction})
                    for trigger in obj.triggers_by_type[TriggerType.ON_EXIT]:
                        await trigger.run(obj, direction, obj_vars, self.game_state)


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
        if target.is_unkillable:
            # can't fight unkillable NPCs (important NPCs without respawn)
            return
        subject.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        target.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN)
        # Stop meditation for both combatants
        if hasattr(subject, 'is_meditating'):
            subject.is_meditating = False
        if hasattr(target, 'is_meditating'):
            target.is_meditating = False
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
            self.game_state.add_character_fighting(subject)
            self.game_state.add_character_fighting(target)
        logger.debug3("checking for aggro or friends")
        
        # Player is initiating combat
        is_player_initiating = subject.has_perm_flags(PermanentCharacterFlags.IS_PC)
        # Combat is occurring in the room (any fighting)
        is_fighting_in_room = True
        
        for c in target.location_room.get_characters():
            logger.debug3(f"checking {c.rid}: attitude={c.attitude}, group={c.group_id}")
            
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
                logger.debug3(f"found {c.rid} joining in against {join_target.rid}")
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
                self.game_state.add_character_fighting(c)
        logger.debug3(f"looking room for {subject.rid}")
        await self.do_look_room(subject, subject.location_room)

    async def fight_next_opponent(self, actor: Actor):
        logger = StructuredLogger(__name__, prefix="fight_next_opponent()> ")
        logger.debug3(f"actor: {actor}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to fight next opponent.")
        if actor.fighting_whom != None:
            raise Exception("Actor must not be fighting anyone to fight next opponent.")
            # return
        for c in actor.location_room.get_characters():
            if c.fighting_whom == actor:
                logger.debug3(f"actor: {actor}, c: {c}")
                await self.start_fighting(actor, c)
                break
        logger.debug3(f"actor: {actor} no opponent found")

    async def do_die(self, dying_actor: Actor, killer: Actor = None, other_killer: str = None):
        from .nondb_models.objects import Corpse
        logger = StructuredLogger(__name__, prefix="do_die()> ")
        
        is_player = dying_actor.has_perm_flags(PermanentCharacterFlags.IS_PC)
        room = dying_actor.location_room
        
        # Death message to the dying actor
        msg = f"You die!"
        await dying_actor.echo(CommTypes.DYNAMIC, msg, set_vars(dying_actor, dying_actor, dying_actor, msg), game_state=self.game_state)

        # Death messages to killer and room
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
        
        # Remove from combat
        if dying_actor in self.game_state.get_characters_fighting():
            self.game_state.remove_character_fighting(dying_actor)
        dying_actor.fighting_whom = None
        
        # Distribute XP to those who killed an NPC
        those_fighting_dier = [c for c in room.get_characters() if c.fighting_whom == dying_actor]
        if not is_player:
            xp_amount = dying_actor.experience_points
            logger.debug3(f"those_fighting: {those_fighting_dier}")
            total_levels = sum([c.total_levels() for c in those_fighting_dier])
            logger.debug3(f"total_levels: {total_levels}")
            if total_levels > 0:
                for c in those_fighting_dier:
                    this_xp = math.ceil(xp_amount * c.total_levels() / total_levels)
                    c.experience_points += this_xp
                    msg = f"You gain {this_xp} experience points!"
                    await c.echo(CommTypes.DYNAMIC, msg, set_vars(c, c, dying_actor, msg), game_state=self.game_state)

        # Those fighting the dying actor switch to new targets
        for c in those_fighting_dier:
            c.fighting_whom = None
            if c in self.game_state.get_characters_fighting():
                self.game_state.remove_character_fighting(c)
            await self.fight_next_opponent(c)

        # Remove from room (temporarily for players)
        dying_actor.location_room.remove_character(dying_actor)
        dying_actor.location_room = None
        
        # Create corpse
        corpse = Corpse(dying_actor, room)
        
        if is_player:
            # PLAYER DEATH: Only drop inventory (not equipped gear)
            corpse.transfer_inventory_only()
            corpse.owner_id = dying_actor.id  # Track who owns this corpse
            
            # Schedule corpse decay (30 minutes)
            decay_ticks = ticks_from_seconds(30 * 60)
            self.game_state.add_scheduled_action(
                corpse, "corpse_decay", in_ticks=decay_ticks,
                vars={'corpse': corpse, 'room': room},
                func=lambda a, v: self._decay_corpse(v['corpse'], v['room'])
            )
            
            # Apply XP penalty (5% of current level's XP, can't de-level)
            await self._apply_death_xp_penalty(dying_actor)
            
            # Respawn player at start room with full HP
            await self._respawn_player(dying_actor)
        else:
            # NPC DEATH: Drop all inventory
            corpse.transfer_inventory()
            dying_actor.current_hit_points = 0
            dying_actor.is_deleted = True
            
            # Handle NPC respawn scheduling
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
        
        # Add corpse to room
        room.add_object(corpse)
        
        # Refresh room display for remaining players
        for c in room.characters:
            if c != dying_actor and c.has_perm_flags(PermanentCharacterFlags.IS_PC):
                logger.debug(f"{c.rid} is refreshing room")
                await self.do_look_room(c, room)

    async def _apply_death_xp_penalty(self, player: Actor):
        """Apply 5% XP penalty for death. Cannot de-level."""
        logger = StructuredLogger(__name__, prefix="_apply_death_xp_penalty()> ")
        
        total_level = player.total_levels()
        if total_level <= 1:
            # Level 1 players have no XP to lose
            return
        
        # Get XP thresholds
        xp_progression = Constants.XP_PROGRESSION
        current_level_threshold = xp_progression[total_level - 1] if total_level > 0 else 0
        
        # Calculate XP within current level
        xp_in_level = player.experience_points - current_level_threshold
        
        # 5% penalty
        xp_loss = int(xp_in_level * 0.05)
        
        if xp_loss > 0:
            player.experience_points -= xp_loss
            # Floor at current level threshold (can't de-level)
            player.experience_points = max(player.experience_points, current_level_threshold)
            
            msg = f"You lose {xp_loss} experience points."
            await player.echo(CommTypes.DYNAMIC, msg, set_vars(player, player, player, msg), game_state=self.game_state)
            logger.info(f"Player {player.name} lost {xp_loss} XP on death")

    async def _respawn_player(self, player: Actor):
        """Respawn player at start location with full HP."""
        logger = StructuredLogger(__name__, prefix="_respawn_player()> ")
        
        # Get start room from config
        start_location = Constants.DEFAULT_START_LOCATION
        if "." in start_location:
            zone_id, room_id = start_location.split(".")
        else:
            zone_id = start_location
            room_id = None
        
        start_zone = self.game_state.get_zone_by_id(zone_id)
        if not start_zone:
            logger.error(f"Start zone {zone_id} not found for player respawn!")
            return
        
        start_room = start_zone.rooms.get(room_id) if room_id else None
        if not start_room:
            # Use first room in zone
            start_room = start_zone.rooms[list(start_zone.rooms.keys())[0]]
        
        # Restore HP to full
        player.current_hit_points = player.max_hit_points
        
        # Clear any negative states
        player.remove_temp_flags(TemporaryCharacterFlags.IS_STUNNED | 
                                  TemporaryCharacterFlags.IS_FROZEN |
                                  TemporaryCharacterFlags.IS_SLEEPING |
                                  TemporaryCharacterFlags.IS_SITTING)
        
        # Arrive at respawn location
        logger.info(f"Player {player.name} respawning at {start_room.name}")
        await self.arrive_room(player, start_room)
        
        msg = "You awaken at a safe location."
        await player.echo(CommTypes.DYNAMIC, msg, set_vars(player, player, player, msg), game_state=self.game_state)

    def _decay_corpse(self, corpse: 'Object', room: 'Room'):
        """Remove a corpse after decay time, destroying any remaining contents."""
        logger = StructuredLogger(__name__, prefix="_decay_corpse()> ")
        
        if corpse in room.contents:
            # Destroy any remaining items in the corpse
            for obj in corpse.contents[:]:
                corpse.remove_object(obj)
                obj.is_deleted = True
            
            room.remove_object(corpse)
            corpse.is_deleted = True
            logger.info(f"Corpse {corpse.name} has decayed")


    async def do_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True, do_die=True) -> Tuple[int, int]:
        logger = StructuredLogger(__name__, prefix="do_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to do damage.")
        
        # Unkillable NPCs (important NPCs without respawn) cannot take damage
        if target.is_unkillable:
            logger.debug(f"Target {target.rid} is unkillable, ignoring damage")
            return 0, target.current_hit_points
        
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
        # Send status update to target if they're a PC
        if target.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await target.send_status_update()
        return damage, target.current_hit_points
                

    async def do_calculated_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True, do_die=True) -> Tuple[int, int]:
        logger = StructuredLogger(__name__, prefix="do_calculated_damage()> ")
        logger.debug(f"actor: {actor}, target: {target}, damage: {damage}, damage_type: {damage_type}")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to accept damage.")
        
        # Unkillable NPCs (important NPCs without respawn) cannot take damage
        if target.is_unkillable:
            logger.debug(f"Target {target.rid} is unkillable, ignoring damage")
            return 0, target.current_hit_points
        
        target_multiplier = (target.damage_multipliers.get(damage_type) / 100)
        if target_multiplier > 1:
            target_multiplier = 1
        damage = damage * (1 - target_multiplier) - target.damage_reduction.get(damage_type)
        if damage < 1:
            return 0
        damage, target_hp = await self.do_damage(actor, target, damage, damage_type, do_msg=do_msg, do_die=do_die)
        return damage, target_hp


    async def do_single_attack(self, actor: Actor, target: Actor, attack: AttackData) -> int:
        # TODO:M: figure out weapons
        # TODO:L: deal with nouns and verbs correctly
        logger = StructuredLogger(__name__, prefix="do_single_attack()> ")
        logger.debug3(f"actor: {actor.rid}, target: {target.rid}")
        logger.debug3(f"attackdata: {attack.to_dict()}")
        if actor.actor_type != ActorType.CHARACTER:
            raise Exception("Actor must be of type CHARACTER to attack.")
        if target.actor_type != ActorType.CHARACTER:
            raise Exception("Target must be of type CHARACTER to attack.")
        
        # Fire ON_ATTACKED triggers on the target when an attack is attempted
        if TriggerType.ON_ATTACKED in target.triggers_by_type:
            attack_vars = {
                'attack_noun': attack.attack_noun,
                'attack_verb': attack.attack_verb
            }
            for trigger in target.triggers_by_type[TriggerType.ON_ATTACKED]:
                await trigger.run(actor, "", attack_vars, self.game_state)
        
        hit_modifier = actor.hit_modifier + attack.attack_bonus
        logger.debug3(f"dodge_dice_number: {target.dodge_dice_number}, dodge_dice_size: {target.dodge_dice_size}, dodge_modifier: {target.dodge_modifier}")
        dodge_roll = roll_dice(target.dodge_dice_number, target.dodge_dice_size) + target.dodge_modifier
        hit_roll = random.randint(1, 100)
        if hit_roll + hit_modifier < dodge_roll:
            logger.debug3(f"MISS: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
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
        logger.debug3(f"{'CRIT' if critical else 'HIT'}: hit_roll: {hit_roll}, hit_modifier: {hit_modifier}, dodge_roll: {dodge_roll}")
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
            logger.debug3(f"did {damage} {dp.damage_type.word()} damage to {target.rid}")
        logger.debug3(f"total damage: {total_damage}")
        return total_damage
            

    # async def handle_combat_tick_event(self, actor: Actor, current_tick: int, game_state: 'ComprehensiveGameState',
    #                                    vars: Dict[str, Any]):
    async def handle_actor_combat_tick(self, actor: Actor):
        logger = StructuredLogger(__name__, prefix="handle_combat_tick_event()> ")
        # logger.debug3(f"handling combat tick for {actor.rid} against {vars['target'].rid}")
        if actor.fighting_whom == None:
            logger.warning(f"{actor.rid} is not fighting anyone")
            return
        target = actor.fighting_whom
        logger.debug3(f"handling combat tick for {actor.rid} against {target.rid}")
        
        # For NPCs, use combat AI to decide whether to use a skill
        # This queues a command rather than executing directly, so NPCs get
        # the same command handling (duration, queueing, etc.) as players
        if not actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            from .combat_ai import CombatAI
            skill_queued = CombatAI.queue_combat_action(actor, target)
            if skill_queued:
                # A skill command was queued, skip auto-attack this round
                # The skill will be executed when the command queue is processed
                # Still need to check if target should fight back
                if target.fighting_whom == None:
                    await self.start_fighting(target, actor)
                return
        
        # Standard auto-attack sequence
        total_dmg = 0
        if actor.equipped[EquipLocation.MAIN_HAND] != None \
        or actor.equipped[EquipLocation.BOTH_HANDS] != None:
            num_attacks = actor.num_main_hand_attacks
            if actor.equipped[EquipLocation.BOTH_HANDS] != None:
                hands = "both hands"
                weapon = actor.equipped[EquipLocation.BOTH_HANDS]
            else:
                hands = "main hand"
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
            logger.debug3(f"character: {actor.rid} attacking {num_attacks}x with {weapon.name} in {hands})")
            logger.debug3(f"weapon: +{weapon.attack_bonus} {weapon.damage_type}: {weapon.damage_num_dice}d{weapon.damage_dice_size} +{weapon.damage_bonus}")
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
                logger.debug3(f"attack_data: {attack_data.to_dict()}")
                total_dmg += await self.do_single_attack(actor, target, attack_data)
        if actor.equipped[EquipLocation.OFF_HAND] != None:
            num_attacks = actor.num_off_hand_attacks
            weapon = actor.equipped[EquipLocation.OFF_HAND]
            logger.debug3(f"character: {actor.rid} attacking, {num_attacks} with {weapon.name} in off hand)")
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
        if not actor.equipped[EquipLocation.MAIN_HAND] and not actor.equipped[EquipLocation.BOTH_HANDS] and not actor.equipped[EquipLocation.OFF_HAND]:        
            logger.debug3(f"character: {actor.rid} attacking, {len(actor.natural_attacks)} natural attacks)")
            for natural_attack in actor.natural_attacks:
                logger.debug3(f"natural_attack: {natural_attack.to_dict()}")
                if target:
                    total_dmg += await self.do_single_attack(actor, target, natural_attack)
        if total_dmg > 0 and target and not target.is_dead():
            status_desc = target.get_status_description()
            msg = f"{target.art_name_cap} is {status_desc}"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target, msg), game_state=self.game_state)
            msg = f"You are {status_desc}"
            await target.echo(CommTypes.DYNAMIC, msg, set_vars(target, actor, target, msg), game_state=self.game_state)
            msg = f"{target.art_name_cap} is {status_desc}"
            await target.location_room.echo(CommTypes.DYNAMIC, msg,
                                        set_vars(target.location_room, actor, target, msg),
                                        exceptions=[actor, target], game_state=self.game_state)
            
        if target.fighting_whom == None:
            await self.start_fighting(target, actor)
            
       
    async def process_fighting(self):
        logger = StructuredLogger(__name__, prefix="process_fighting()> ")
        
        characters_fighting = list(self.game_state.get_characters_fighting())
        for actor in characters_fighting:
            logger.debug3(f"process_fighting() actor: {actor}")
            if actor.is_deleted or actor.is_dead():
                if actor in self.game_state.get_characters_fighting():
                    self.game_state.remove_character_fighting(actor)
                continue
            if actor.actor_type != ActorType.CHARACTER:
                logger.debug3(f"{actor.rid} is not character: Actor must be of type CHARACTER to process fighting.")
                return
            await self.handle_actor_combat_tick(actor)
        
    
    async def do_aggro(self, actor: Actor) -> bool:
        logger = StructuredLogger(__name__, prefix="do_aggro()> ")
        # logger.critical(f"do_aggro() actor: {actor.rid}")
        if actor.actor_type != ActorType.CHARACTER:
            logger.debug3(f"{actor.rid} is not character")
            logger.error("Actor must be of type CHARACTER to aggro.")
            return False
        if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            logger.debug3(f"{actor.rid} is PC, skipping aggro")
            return False
        
        # Check if the actor is hostile (either by attitude or by aggressive flag)
        if not (actor.attitude == ActorAttitude.HOSTILE or actor.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE)):
            # logger.critical(f"{actor.rid} is not hostile or aggressive")
            # not hostile
            return False
        if actor.fighting_whom != None: # don't aggro if already fighting
            logger.debug3(f"{actor.rid} is fighting")
            return False
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            logger.debug3(f"{actor.rid} is sitting")
            msg = "You can't aggro while sitting!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return False
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            logger.debug3(f"{actor.rid} is sleeping")
            msg = "You can't aggro while sleeping!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return False
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            logger.debug3(f"{actor.rid} is stunned")
            msg = "You can't aggro while stunned!"
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, actor, msg), game_state=self.game_state)
            return False
        for c in actor.location_room.characters:
            # logger.critical(f"{actor.rid} examining character {c.rid} ({c.art_name})")
            # logger.critical(f"  - c != actor: {c != actor}")
            # logger.critical(f"  - c.actor_type == ActorType.CHARACTER: {c.actor_type == ActorType.CHARACTER}")
            # logger.critical(f"  - c.has_perm_flags(PermanentCharacterFlags.IS_PC): {c.has_perm_flags(PermanentCharacterFlags.IS_PC)}")
            # logger.critical(f"  - not c.has_game_flags(GamePermissionFlags.IS_ADMIN): {not c.has_game_flags(GamePermissionFlags.IS_ADMIN)}")
            
            if c != actor and c.actor_type == ActorType.CHARACTER \
                and c.has_perm_flags(PermanentCharacterFlags.IS_PC) \
                and not c.has_game_flags(GamePermissionFlags.IS_ADMIN):  # Don't aggro admins

                # logger.critical(f"{actor.rid} checking {c.rid}")

                if (c.has_perm_flags(PermanentCharacterFlags.IS_INVISIBLE) \
                or c.has_temp_flags(TemporaryCharacterFlags.IS_INVISIBLE)) \
                and not actor.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE) \
                and not actor.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE):
                    logger.debug3(f"{c.rid} is invisible to {actor.rid}, skipping")
                    continue

                if c.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
                    if Skills.stealthcheck(c, actor):
                        logger.debug3(f"{c.rid} is stealthed from {actor.rid}, skipping")
                        continue

                logger.debug3(f"{actor.rid} aggroing {c.rid}")
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
                
                # await self.do_look_room(actor, actor.location_room)
                # await self.do_look_room(c, c.location_room)
                return True
            # else:
            #     logger.critical(f"{c.rid} failed character check - skipping")

        # logger.critical(f"{actor.rid} did not aggro anyone")
        return False


    