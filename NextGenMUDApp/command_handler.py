import asyncio
from .structured_logger import StructuredLogger
import itertools
import logging
from num2words import num2words
import random
import re
from typing import Any, Callable, List
from .command_handler_interface import CommandHandlerInterface
from .communication import CommTypes
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
from .constants import Constants
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actor_states import CharacterStateForcedSleeping, CharacterStateForcedSitting
from .nondb_models.actors import Actor, ActorType
from .nondb_models.characters import Character
from .nondb_models.character_interface import CharacterInterface, \
    EquipLocation, PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags
from .nondb_models.object_interface import ObjectInterface, ObjectFlags
from .nondb_models.objects import Object
from .nondb_models.room_interface import RoomInterface
from .nondb_models.triggers import TriggerType, Trigger
from .nondb_models import world
from .utility import replace_vars, firstcap, set_vars, split_preserving_quotes, article_plus_name
from .nondb_models.rooms import Room
from .nondb_models.world import WorldDefinition, Zone
from .communication import Connection
from .comprehensive_game_state_interface import GameStateInterface, ScheduledEvent, EventType
from .config import Config, default_app_config
from .skills_interface import SkillsRegistryInterface
from .nondb_models.actor_states import Cooldown
from .nondb_models.attacks_and_damage import DamageType
from .skills_core import SkillsRegistry


# Communication Types Usage Guidelines:
# 
# The MUD client interface has two distinct text display areas with different purposes:
#
# 1. DYNAMIC Box (CommTypes.DYNAMIC):
#    - Used for transient game events, actions, and messages that occur in real-time
#    - Examples: Combat messages, character actions, error messages, command responses
#    - Messages in this box represent things that "happen" rather than persistent information
#    - These messages naturally scroll up and out of view as gameplay progresses
#
# 2. STATIC Box (CommTypes.STATIC):
#    - Used for persistent information displays that players may want to reference
#    - Examples: Character stats, inventory lists, equipment information, room descriptions
#    - Content in this box represents "state" rather than events
#    - This information remains visible until explicitly replaced by other static content
#
# Best Practices:
# - Use DYNAMIC for actions, events, and ephemeral messages
# - Use STATIC for state information, lists, and reference material
# - Error messages about command execution go to DYNAMIC (e.g., "You can't do that")
# - Detailed informational displays go to STATIC (e.g., "Your inventory contains...")
#
# This separation provides players with a clearer view of game state vs. game events.

class CommandHandler(CommandHandlerInterface):
    _game_state: ComprehensiveGameState = live_game_state
    executing_actors = {}

    command_handlers = {
        # privileged commands
        "show": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_show(char, input),
        "echo": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_echo(char, input),
        "echoto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_echoto(char, input),
        "echoexcept": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_echoexcept(char, input),
        "settempvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_settempvar(char, input),
        "setpermvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setpermvar(char, input),
        "spawn": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_spawn(char, input),
        "makeadmin": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_makeadmin(char, input),
        "possess": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_possess(char, input),
        "goto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_goto(char, input),
        "list": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_list(char, input),
        "at": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_at(char, input),
        "setloglevel": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setloglevel(char, input),
        "setlogfilter": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setlogfilter(char, input),
        "getlogfilter": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_getlogfilter(char, input),
        "deltempvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_deltempvar(char, input),
        "delpermvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_delpermvar(char, input),
        "save": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_save(char, input),
        "load": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_load(char, input),
        "saves": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_saves(char, input),
        "deletesave": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_deletesave(char, input),
        "command": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_command(char, input),
        "stop": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stop(char, input),
        "walkto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_walkto(char, input),
        "delay": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_delay(char, input),
        "setquestvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setquestvar(char, input),
        "getquestvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_getquestvar(char, input),
        "spawnobj": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_spawnobj(char, input),
        "pause": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_pause(char, input),
        "damage": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_damage(char, input),
        "heal": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_heal(char, input),
        "removeitem": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_removeitem(char, input),
        "transfer": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_transfer(char, input),
        "force": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_force(char, input),
        "interrupt": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_interrupt(char, input),

        # normal commands
        "give": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_give(char, input),
        "north": lambda command, char, input: CommandHandler.handle_movement(command, char, "north"),
        "n": lambda command, char, input: CommandHandler.handle_movement(command, char, "north"),
        "south": lambda command, char, input: CommandHandler.handle_movement(command, char, "south"),
        "s": lambda command, char, input: CommandHandler.handle_movement(command, char, "south"),
        "east": lambda command, char, input: CommandHandler.handle_movement(command, char, "east"),
        "e": lambda command, char, input: CommandHandler.handle_movement(command, char, "east"),
        "west": lambda command, char, input: CommandHandler.handle_movement(command, char, "west"),
        "w": lambda command, char, input: CommandHandler.handle_movement(command, char, "west"),
        "down": lambda command, char, input: CommandHandler.handle_movement(command, char, "down"),
        "d": lambda command, char, input: CommandHandler.handle_movement(command, char, "down"),
        "up": lambda command, char, input: CommandHandler.handle_movement(command, char, "up"),
        "u": lambda command, char, input: CommandHandler.handle_movement(command, char, "up"),
        "out": lambda command, char, input: CommandHandler.handle_movement(command, char, "out"),
        "in": lambda command, char, input: CommandHandler.handle_movement(command, char, "in"),
        "say": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_say(char, input),
        "sayto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sayto(char, input),
        "ask": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_ask(char, input),
        "tell": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_tell(char, input, is_whisper=False),
        "whisper": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_tell(char, input, is_whisper=True),
        "emote": lambda command, char,input: CommandHandlerInterface.get_instance().cmd_emote(char, input),
        "look": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "l": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "attack": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "kill": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "inventory": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "inv": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "i": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "get": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_get(char, input),
        "take": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_get(char, input),
        "drop": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_drop(char, input),
        "put": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_put(char, input),
        "open": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_open(char, input),
        "close": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_close(char, input),
        "lock": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_lock(char, input),
        "unlock": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_unlock(char, input),
        "use": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_use(char, input),
        "quaff": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quaff(char, input),
        "drink": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_drink(char, input),
        "apply": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_apply(char, input),
        "eat": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_eat(char, input),
        "examine": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "ex": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "inspect": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inspect(char, input),
        "equip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "eq": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "unequip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_unequip(char, input),
        "stand": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stand(char, input),
        "sit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sit(char, input),
        "sleep": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sleep(char, input),
        "meditate": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_meditate(char, input),
        "med": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_meditate(char, input),
        "flee": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_flee(char, input),
        "leaverandom": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_leaverandom(char, input),
        "skills": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_skills(char, input),
        "character": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "char": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "triggers": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_triggers(char, input),
        "quit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quit(char, input),
        "logout": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quit(char, input),
        "savegame": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_savegame(char, input),
        # various emotes are in the EMOTE_MESSAGES dict below
    }

    @classmethod
    async def handle_movement(cls, command, char, direction):
        logger = StructuredLogger(__name__, prefix="handle_movement()> ")
        try:
            await CoreActionsInterface.get_instance().world_move(char, direction)
        except KeyError as e:
            logger.warning(f"Movement failed - destination room not found: {e} when moving {direction} from {char.location_room.name}")
            await char.send_text(CommTypes.DYNAMIC, "There is a problem with going that direction.")

    async def process_command(cls, actor: Actor, input: str, vars: dict = None, from_script: bool = False):
        logger = StructuredLogger(__name__, prefix="process_command()> ")
        # print(actor)
        logger.debug3(f"processing input for actor {actor.id}: {input}")
        
        # Echo the command back to the user (but not for script-invoked commands)
        if not from_script:
            await actor.send_text(CommTypes.DYNAMIC, f"> {input}")
        
        if actor.reference_number is None:
            raise Exception(f"Actor {actor.id} has no reference number.")
        
        # Track executing actors (but skip for nested script-invoked commands)
        is_nested = actor.rid in cls.executing_actors
        if not is_nested:
            logger.debug3(f"pushing {actor.rid} ({input}) onto executing_actors")
            cls.executing_actors[actor.rid] = input
        msg = None
        for ch in cls.executing_actors:
            logger.debug3(f"executing_actors 1: {ch}")
        commands = [cmd.strip() for cmd in input.split(';') if cmd.strip()]
        try:
            if not commands:
                msg = "Did you want to do something?"
            else:
                # Process first command normally
                first_command = commands[0]
                if first_command == "":
                    msg = "Did you want to do something?"
                elif actor.actor_type == ActorType.CHARACTER and actor.is_dead():
                    msg = "You are dead.  You can't do anything."
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                    and not first_command.startswith("stand"):
                    msg = "You can't do that while you're sleeping."
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                    and not first_command.startswith("stand"):
                    msg = "You can't do that while you're sitting."
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
                    msg = "You are stunned!"
                elif actor.is_busy(cls._game_state.get_current_tick()):
                    # Queue the commands if the actor is busy
                    for cmd in commands:
                        actor.command_queue.append(cmd)
                    msg = "You are busy. Your command has been queued."
                else:
                    parts = split_preserving_quotes(first_command)
                    if len(parts) == 0:
                        msg = "Did you want to do something?"
                    else:
                        command = parts[0]
                        if command in cls.command_handlers:
                            await cls.command_handlers[command](command, actor, ' '.join(parts[1:]))
                        else:
                            if command in cls.EMOTE_MESSAGES:
                                await cls.cmd_specific_emote(command, actor, ' '.join(parts[1:]))
                            else:
                                logger.debug3(f"checking skills registry for: {first_command}")
                                skill_name, remainder = SkillsRegistry.parse_skill_name_from_input(first_command)
                                if skill_name:  
                                    logger.debug3(f"found skill: {skill_name}")
                                    await SkillsRegistry.invoke_skill_by_name(cls._game_state, actor, skill_name, remainder, 0)
                                else:
                                    logger.debug3(f"no skill found")
                                    logger.debug3(f"Unknown command: {command}")
                                    msg = "Unknown command"

                # Queue any additional commands
                if len(commands) > 1:
                    actor.command_queue.extend(commands[1:])
                    if not msg:  # Only add queue message if there wasn't an error message
                        msg = f"Queued {len(commands)-1} additional command(s)."
        except KeyError:
            logger.error(f"KeyError processing command {command}")
            msg = "Command failure."
            raise
        except:
            logger.exception(f"exception handling input '{input}' for actor {actor.rid}")
            raise

        if msg and hasattr(actor, 'connection') and actor.connection:
            await actor.send_text(CommTypes.DYNAMIC, msg)
        elif msg:
            set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        
        # Only remove from executing_actors if we added it (not a nested call)
        if not is_nested:
            if not actor.rid in cls.executing_actors:
                logger.warning(f"actor {actor.rid} not in executing_actors")
            else:
                del cls.executing_actors[actor.rid]


    async def cmd_say(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_say()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        await actor.send_text(CommTypes.DYNAMIC, f"You say, \"{text}\"")
        room = actor.location_room if actor.location_room else actor.in_actor.location_room if actor.in_actor else None
        if room:
            if actor.actor_type == ActorType.CHARACTER:
                await room.echo(CommTypes.DYNAMIC, f"{actor.art_name_cap} says, \"{text}\"", vars, exceptions=[actor], game_state=cls._game_state, skip_triggers=True)
            elif actor.actor_type == ActorType.OBJECT:
                await room.echo(CommTypes.DYNAMIC, f"{actor.art_name_cap} says, \"{text}\"", vars, exceptions=[actor], game_state=cls._game_state, skip_triggers=True)
            elif actor.actor_type == ActorType.ROOM:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state, skip_triggers=True)
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")
            if actor != room and TriggerType.CATCH_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.CATCH_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and TriggerType.CATCH_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.CATCH_SAY]:
                        await trig.run(ch, text, vars, cls._game_state)
        else:
            actor.send_text(CommTypes.DYNAMIC, "You have no location room.")
            logger.error(f"Actor {actor.rid} has no location room.")

    async def cmd_sayto(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_sayto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Say to whom?")
            return
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Say what?")
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        target = cls._game_state.find_target_character(actor, pieces[0])
        logger.debug3(f"target: {target}")
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Say to whom?")
            return
        text = ' '.join(pieces[1:])
        msg = f"You say to {target.name}, \"{text}\""
        vars = set_vars(actor, actor, target, msg)
        await actor.send_text(CommTypes.DYNAMIC, f"You say to {target.name}, \"{text}\"")
        msg = f"{actor.art_name_cap} says to you, \"{text}\""
        vars = set_vars(actor, actor, target, msg)
        await target.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        room = actor._location_room if actor._location_room else actor.in_actor_.location_room_
        
        # Check if target has LLM conversation enabled
        from .llm_npc_conversation import NPCConversationHandler
        if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
            # Use LLM conversation handler for this NPC
            await cls._handle_llm_conversation(actor, target, text, room)
        elif target != actor and TriggerType.CATCH_SAY in target.triggers_by_type:
            # Fall back to traditional CATCH_SAY triggers
            for trig in target.triggers_by_type[TriggerType.CATCH_SAY]:
                await trig.run(target, text, vars, cls._game_state)
        
        if room:
            msg = f"{actor.art_name_cap} says to {target.name}, \"{text}\""
            vars = set_vars(actor, actor, target, msg)
            await actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state = cls._game_state)
            if actor != room and TriggerType.CATCH_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.CATCH_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and ch != target and TriggerType.CATCH_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.CATCH_SAY]:
                        await trig.run(ch, text, vars, cls._game_state)

    async def cmd_ask(cls, actor: Actor, input: str):
        """
        Ask a question to someone in the room. Works like sayto but with different messages.
        Triggers LLM conversation or CATCH_SAY triggers.
        
        Usage: ask <target> <question>
        """
        logger = StructuredLogger(__name__, prefix="cmd_ask()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Ask whom?")
            return
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Ask what?")
            return
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        target = cls._game_state.find_target_character(actor, pieces[0])
        logger.debug3(f"target: {target}")
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Ask whom?")
            return
        text = ' '.join(pieces[1:])
        msg = f"You ask {target.name}, \"{text}\""
        vars = set_vars(actor, actor, target, msg)
        await actor.send_text(CommTypes.DYNAMIC, f"You ask {target.name}, \"{text}\"")
        msg = f"{actor.art_name_cap} asks you, \"{text}\""
        vars = set_vars(actor, actor, target, msg)
        await target.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        room = actor._location_room if actor._location_room else actor.in_actor_.location_room_
        
        # Check if target has LLM conversation enabled
        from .llm_npc_conversation import NPCConversationHandler
        if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
            # Use LLM conversation handler for this NPC
            await cls._handle_llm_conversation(actor, target, text, room)
        elif target != actor and TriggerType.CATCH_SAY in target.triggers_by_type:
            # Fall back to traditional CATCH_SAY triggers
            for trig in target.triggers_by_type[TriggerType.CATCH_SAY]:
                await trig.run(target, text, vars, cls._game_state)
        
        if room:
            msg = f"{actor.art_name_cap} asks {target.name}, \"{text}\""
            vars = set_vars(actor, actor, target, msg)
            await actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state = cls._game_state)
            if actor != room and TriggerType.CATCH_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.CATCH_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and ch != target and TriggerType.CATCH_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.CATCH_SAY]:
                        await trig.run(ch, text, vars, cls._game_state)
    
    async def _handle_llm_conversation(cls, actor: Actor, target: Character, text: str, room) -> None:
        """Handle LLM-driven NPC conversation."""
        logger = StructuredLogger(__name__, prefix="_handle_llm_conversation()> ")
        
        from .llm_npc_conversation import get_conversation_handler
        
        try:
            handler = get_conversation_handler()
            result = await handler.process_speech(actor, target, text, cls._game_state)
            
            if result.error:
                logger.error(f"LLM conversation error: {result.error}")
                # NPC falls back to confused response on error
                await room.echo(
                    CommTypes.DYNAMIC,
                    f"{target.art_name_cap} looks at {actor.name} with a puzzled expression.",
                    game_state=cls._game_state
                )
                return
            
            if result.dialogue:
                # Show NPC's response to everyone in the room
                await room.echo(
                    CommTypes.DYNAMIC,
                    f'{target.art_name_cap} says to {actor.name}, "{result.dialogue}"',
                    game_state=cls._game_state
                )
            
            # Handle special NPC actions
            if result.state_change.npc_action:
                await cls._handle_llm_npc_action(
                    actor, target, result.state_change.npc_action, room
                )
                
        except Exception as e:
            logger.error(f"Exception in LLM conversation: {e}")
            import traceback
            traceback.print_exc()
            # Silent failure - NPC just doesn't respond
    
    async def _handle_llm_npc_action(cls, actor: Actor, target: Character, action: str, room) -> None:
        """Handle special actions signaled by the LLM during conversation."""
        logger = StructuredLogger(__name__, prefix="_handle_llm_npc_action()> ")
        
        action = action.lower().strip()
        
        if action == "ends_conversation":
            await room.echo(
                CommTypes.DYNAMIC,
                f"{target.art_name_cap} turns away, ending the conversation.",
                exceptions=[target],
                game_state=cls._game_state
            )
        
        elif action == "attacks":
            # Initiate combat with the player
            logger.debug(f"NPC {target.name} is attacking {actor.name}")
            # TODO: Integrate with your combat system
            # For now, just announce the intent
            await room.echo(
                CommTypes.DYNAMIC,
                f"{target.art_name_cap} suddenly lunges at {actor.name}!",
                game_state=cls._game_state
            )
            # You would call your combat initiation here, e.g.:
            # await cls._game_state.initiate_combat(target, actor)
        
        elif action == "flees":
            logger.debug(f"NPC {target.name} is fleeing from {actor.name}")
            await room.echo(
                CommTypes.DYNAMIC,
                f"{target.art_name_cap} backs away nervously and hurries off.",
                exceptions=[target],
                game_state=cls._game_state
            )
            # TODO: Actually move the NPC to another room
        
        elif action == "gives_item":
            logger.debug(f"NPC {target.name} wants to give item to {actor.name}")
            # TODO: Implement item giving logic
            # This would need to know WHAT item to give
            await room.echo(
                CommTypes.DYNAMIC,
                f"{target.art_name_cap} reaches into a pocket...",
                game_state=cls._game_state
            )

    async def cmd_echo(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_echo()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        if actor._location_room:
            if actor.actor_type == ActorType.CHARACTER:
                await actor._location_room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await actor._location_room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                # print("***")
                # print(text)
                # print("***")
                await actor._location_room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")
        await actor.send_text(CommTypes.DYNAMIC, text)


    async def cmd_echoto(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_echoto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Echo what?")
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        target = cls._game_state.find_target_character(actor, pieces[0])
        logger.debug3(f"target: {target}")
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
            return
        text = ' '.join(pieces[1:])
        vars = set_vars(actor, actor, target, text)
        msg = f"You echo '{text}' to {target.name}."
        await target.echo(CommTypes.DYNAMIC, text, vars, game_state=cls._game_state)
        await actor.send_text(CommTypes.DYNAMIC, msg)


    async def cmd_echoexcept(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_echoexcept()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
            return
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Echo what?")
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding excludee: {pieces[1]}")
        excludee = cls._game_state.find_target_character(actor, pieces[1])
        logger.debug3(f"excludee: {excludee}")
        if excludee == None:
            await actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
            return
        exclude = [ excludee ]
        text = ' '.join(pieces[1:])
        msg = f"To everyone except {exclude[0].name} you echo '{text}'."
        vars = set_vars(actor, actor, exclude[0], msg)
        await actor.echo(CommTypes.DYNAMIC, text, vars, exceptions=exclude, game_state=cls._game_state)
        await actor.send_text(CommTypes.DYNAMIC, msg)


    async def cmd_damage(cls, actor: Actor, input: str):
        """
        Apply damage to a target. This is a privileged/script command.
        
        Usage: damage <target> <amount> <damage_type>
        
        The amount can be:
        - A constant: damage target 10 fire
        - Dice notation: damage target 2d6+3 fire
        - Dice without bonus: damage target 2d6 fire
        
        Examples:
            damage %S% 10 fire
            damage guard 2d6+5 slashing
            damage %T% 1d8 cold
        """
        from .utility import roll_dice, get_dice_parts
        logger = StructuredLogger(__name__, prefix="cmd_damage()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: damage <target> <amount> <damage_type>")
            return
        
        target_name = pieces[0]
        damage_str = pieces[1]
        damage_type_str = pieces[2].upper()
        
        # Find target
        target = cls._game_state.find_target_character(actor, target_name)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return
        
        # Parse damage amount (supports dice notation like "2d6+3" or constants like "10")
        dice_parts = get_dice_parts(damage_str)
        if dice_parts[0] > 0:  # Has dice to roll
            damage = roll_dice(dice_parts[0], dice_parts[1], dice_parts[2])
        else:
            damage = dice_parts[2]  # Just use the constant
        
        # Parse damage type
        try:
            damage_type = DamageType[damage_type_str]
        except KeyError:
            valid_types = ", ".join([dt.name.lower() for dt in DamageType])
            await actor.send_text(CommTypes.DYNAMIC, f"Unknown damage type: {damage_type_str}. Valid types: {valid_types}")
            return
        
        # Apply damage
        await CoreActionsInterface.get_instance().do_damage(actor, target, damage, damage_type)
        logger.debug3(f"Applied {damage} {damage_type.name.lower()} damage to {target.name}")


    async def cmd_heal(cls, actor: Actor, input: str):
        """
        Heal a target. This is a privileged/script command.
        
        Usage: heal <target> <amount>
        
        The amount can be:
        - A constant: heal target 20
        - Dice notation: heal target 2d6+5
        
        Examples:
            heal %S% 20
            heal player 3d8+10
        """
        from .utility import roll_dice, get_dice_parts
        logger = StructuredLogger(__name__, prefix="cmd_heal()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: heal <target> <amount>")
            return
        
        target_name = pieces[0]
        heal_str = pieces[1]
        
        # Find target
        target = cls._game_state.find_target_character(actor, target_name)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return
        
        # Parse heal amount (supports dice notation like "2d6+3" or constants like "20")
        dice_parts = get_dice_parts(heal_str)
        if dice_parts[0] > 0:  # Has dice to roll
            heal_amount = roll_dice(dice_parts[0], dice_parts[1], dice_parts[2])
        else:
            heal_amount = dice_parts[2]  # Just use the constant
        
        # Apply healing
        old_hp = target.current_hit_points
        target.current_hit_points = min(target.max_hit_points, target.current_hit_points + heal_amount)
        actual_heal = target.current_hit_points - old_hp
        
        # Send messages
        if actual_heal > 0:
            msg = f"You heal {target.art_name} for {actual_heal} HP!"
            await actor.send_text(CommTypes.DYNAMIC, msg)
            if target != actor:
                msg = f"{actor.art_name_cap} heals you for {actual_heal} HP!"
                await target.send_text(CommTypes.DYNAMIC, msg)
            
            # Send status update if target is a PC
            if target.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await target.send_status_update()
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is already at full health.")
        
        logger.debug3(f"Healed {target.name} for {actual_heal} HP")


    async def cmd_tell(cls, actor: Actor, input: str, is_whisper: bool = False):
        """
        Send a private message to another character.
        
        Usage:
            tell <target> <message>  - Send to anyone in the world
            whisper <target> <message>  - Send to someone in the same room only
        """
        logger = StructuredLogger(__name__, prefix="cmd_tell()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}, is_whisper: {is_whisper}")
        
        verb = "whisper" if is_whisper else "tell"
        verb_past = "whisper" if is_whisper else "tell"
        
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, f"{verb.capitalize()} who?")
            return
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, f"{verb.capitalize()} what?")
            return
            
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        
        # For whisper, only search in the same room. For tell, search world.
        if is_whisper:
            target = cls._game_state.find_target_character(actor, pieces[0], search_world=False)
        else:
            target = cls._game_state.find_target_character(actor, pieces[0], search_world=True)
        
        logger.debug3(f"target: {target}")
        if target is None:
            if is_whisper:
                await actor.send_text(CommTypes.DYNAMIC, "They're not here.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"{verb.capitalize()} who?")
            return
        
        text = ' '.join(pieces[1:])
        
        if is_whisper:
            # Whisper - private, but others in room can see it happening
            msg = f"{firstcap(actor.name)} whispers something to you: '{text}'."
            await target.echo(CommTypes.DYNAMIC, msg, game_state=cls._game_state)
            await actor.send_text(CommTypes.DYNAMIC, f"You whisper to {target.name} '{text}'.")
            
            # Others in the room see the whisper but not the content
            room_msg = f"{firstcap(actor.name)} whispers something to {target.name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, room_msg, 
                                           exceptions=[actor, target], 
                                           game_state=cls._game_state)
        else:
            # Tell - completely private
            msg = f"{firstcap(actor.name)} tells you '{text}'."
            vars = set_vars(actor, actor, target, msg)
            logger.debug3("sending message to target")
            await target.echo(CommTypes.DYNAMIC, msg, game_state=cls._game_state)
            await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name} '{text}'.")
        
        # If target is an NPC in the same room, trigger NPC response (LLM or CATCH_SAY)
        room = actor._location_room if actor._location_room else None
        if room and target in room.get_characters():
            from .llm_npc_conversation import NPCConversationHandler
            if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
                # Use LLM conversation handler for this NPC
                await cls._handle_llm_conversation(actor, target, text, room)
            elif TriggerType.CATCH_SAY in target.triggers_by_type:
                # Fall back to traditional CATCH_SAY triggers
                for trig in target.triggers_by_type[TriggerType.CATCH_SAY]:
                    await trig.run(target, text, vars, cls._game_state)


    async def cmd_emote(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_emote()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        await actor.send_text(CommTypes.DYNAMIC, f"You emote, \"{text}\"")
        if actor._location_room:
            if actor.actor_type == ActorType.CHARACTER:
                if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    await actor._location_room.echo(CommTypes.DYNAMIC, f"... {actor.name} {text}", vars, exceptions=[actor], game_state=cls._game_state)
                else:
                    await actor._location_room.echo(CommTypes.DYNAMIC, f"{actor.art_name_cap} {text}", vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await actor._location_room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                await actor._location_room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")


    EMOTE_MESSAGES = {
        "kick": {   'notarget' : { 'actor': "You let loose with a wild kick.", 'room': "$cap(%a%) lets loose with a wild kick." },
                    'target' : { 'actor': "You kick %t%.", 'room': "$cap(%a%) kicks %t%." , 'target': "$cap(%a%) kicks you."} },
        "kiss": {   'notarget' : { 'actor': 'You kiss the air.', 'room': '$cap(%a%) kisses the air.'},
                    'target': {'actor': "You kiss %t%.", 'room': "$cap(%a%) kisses %t%.", 'target': "$cap(%a%) kisses you." }},
        "lick": {   'notarget': { 'actor': 'You lick the air.', 'room': '$cap(%a%) licks the air.'},
                    'target': {'actor': "You lick %t%.", 'room': "$cap(%s%) licks %t%.", 'target': "$cap(%s%) licks you." }},
        "congratulate": {   'notarget' : { 'actor' : 'You congratulate yourself.', 'room' : '$cap(%a%) congratulates %{P}self.'},
                            'target' : { 'actor': "You congratulate %t%.", 'room': "$cap(%a%) congratulates %t%." , 'target': "$cap(%a%) congratulates you."}},
        "bow": {    'notarget': { 'actor': 'You take a bow.', 'room': 'Makes a sweeping bow.'}, 
                    'target' : {'actor': "You bow to %t%.", 'room': "$cap(%a%) bows to %t%.", 'target': "$cap(%a%) bows to you." }},
        "thank": {  'notarget': { 'actor' : 'You thank everyone.', 'room' : '$cap(%a%) thanks everyone.' },
                    'target' : {'actor': "You thank %t%.", 'room': "$cap(%a%) thanks %t%.", 'target': "$cap(%a%) thanks you." }},
        "sing": {   'notarget' : {'actor': 'You sing your heart out.', 'room' : '$cap(%a%) sings %P% heart out.' },
                    'target': {'actor': "You sing to %t%.", 'room': "$cap(%a%) sings to %t%.", 'target': "$cap(%a%) sings to you." }},
        "dance": { 'notarget' : {'actor': 'You dance a jig.', 'room' : '$cap(%a%) dances a jig.' },
                    'target': {'actor': "You dance with %t%.", 'room': "$cap(%a%) dances with %t%.", 'target': "$cap(%a%) dances with you." }},
                    "touch": { 'notarget' : {'actor': 'You touch yourself.', 'room' : '$cap(%a%) touches %P%self.' },
                    'target': {'actor': "You touch %t%.", 'room': "$cap(%a%) touches %t%.", 'target': "$cap(%a%) touches you." }},
        "wink": {   'notarget': {'actor': 'You wink mischievously.', 'room': '$cap(%a%) winks mischievously.'},
                    'target': {'actor': "You wink at %t%.", 'room': "$cap(%a%) winks at %t%.", 'target': "$cap(%a%) winks at you."} },
        "laugh": {  'notarget': {'actor': 'You burst into laughter.', 'room': '$cap(%a%) bursts into laughter.'},
                    'target': {'actor': "You laugh with %t%.", 'room': "$cap(%a%) laughs with %t%.", 'target': "$cap(%a%) laughs with you."} },
        "sigh":  {  'notarget': {'actor': 'You sigh deeply.', 'room': '$cap(%a%) sighs deeply.'},
                    'target': {'actor': "You sigh at %t%.", 'room': "$cap(%a%) sighs at %t%.", 'target': "$cap(%a%) sighs at you."} },
        "nod": {    'notarget': {'actor': 'You nod thoughtfully.', 'room': '$cap(%a%) nods thoughtfully.'},
                    'target': {'actor': "You nod at %t%.", 'room': "$cap(%a%) nods at %t%.", 'target': "$cap(%a%) nods at you."} },
        "shrug": {  'notarget': {'actor': 'You shrug indifferently.', 'room': '$cap(%a%) shrugs indifferently.'},
                    'target': {'actor': "You shrug at %t%.", 'room': "$cap(%a%) shrugs at %t%.", 'target': "$cap(%a%) shrugs at you."} },
        "cheer": {  'notarget': {'actor': 'You cheer loudly.', 'room': '$cap(%a%) cheers loudly.'},
                    'target': {'actor': "You cheer for %t%.", 'room': "$cap(%a%) cheers for %t%.", 'target': "$cap(%a%) cheers for you."} },
        "frown": {  'notarget': {'actor': 'You frown deeply.', 'room': '$cap(%a%) frowns deeply.'},
                    'target': {'actor': "You frown at %t%.", 'room': "$cap(%a%) frowns at %t%.", 'target': "$cap(%a%) frowns at you."} },
        "wave": {   'notarget': {'actor': 'You wave at no one in particular.', 'room': '$cap(%a%) waves at no one in particular.'},
                    'target': {'actor': "You wave at %t%.", 'room': "$cap(%a%) waves at %t%.", 'target': "$cap(%a%) waves at you."} },
        "clap": {   'notarget': {'actor': 'You clap your hands.', 'room': '$cap(%a%) claps %P% hands.'},
                    'target': {'actor': "You clap for %t%.", 'room': "$cap(%a%) claps for %t%.", 'target': "$cap(%a%) claps for you."} },
        "gaze": {   'notarget': {'actor': 'You gaze into the distance.', 'room': '$cap(%a%) gazes into the distance.'},
                    'target': {'actor': "You gaze at %t%.", 'room': "$cap(%a%) gazes at %t%.", 'target': "$cap(%a%) gazes at you."} },
        "smile": {
            'notarget': {'actor': 'You smile warmly.', 'room': '$cap(%a%) smiles warmly.'},
            'target': {'actor': "You smile at %t%.", 'room': "$cap(%a%) smiles at %t%.", 'target': "$cap(%a%) smiles at you."}
        },
        "glare": {
            'notarget': {'actor': 'You glare into the distance.', 'room': '$cap(%a%) glares into the distance.'},
            'target': {'actor': "You glare at %t%.", 'room': "$cap(%a%) glares at %t%.", 'target': "$cap(%a%) glares at you."}
        },
        "cry": {
            'notarget': {'actor': 'Tears well up in your eyes.', 'room': '$cap(%a%) starts to cry.'},
            'target': {'actor': "You cry on %t%'s shoulder.", 'room': "$cap(%a%) cries on %t%'s shoulder.", 'target': "$cap(%a%) cries on your shoulder."}
        },
        "yawn": {
            'notarget': {'actor': 'You yawn loudly.', 'room': '$cap(%a%) yawns loudly.'},
            'target': {'actor': "You yawn at %t%.", 'room': "$cap(%a%) yawns at %t%.", 'target': "$cap(%a%) yawns at you."}
        },
        "think": {
            'notarget': {'actor': 'You look thoughtful.', 'room': '$cap(%a%) looks thoughtful.'},
            'target': {'actor': "You ponder %t%.", 'room': "$cap(%a%) ponders %t%.", 'target': "$cap(%a%) ponders about you."}
        }
        }

    async def cmd_specific_emote(cls, command: str, actor: Actor, input: str):
        # TODO:L: add additional logic for no args, for "me", for objects
        logger = StructuredLogger(__name__, prefix="cmd_specific_emote()> ")
        logger.debug3(f"command: {command}, actor.rid: {actor.rid}, input: {input}")
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            logger.debug3("no pieces")
            actor_msg = firstcap(cls.EMOTE_MESSAGES[command]["notarget"]['actor'])
            room_msg = firstcap(cls.EMOTE_MESSAGES[command]["notarget"]['room'])
            target_msg = None
            target = None
        else:
            logger.debug3(f"finding target: actor={actor.rid} target={pieces[0]}")
            target = cls._game_state.find_target_character(actor, pieces[0])
            if target == None:
                logger.debug3("can't find target")
                await actor.send_text(CommTypes.DYNAMIC, f"{command} whom?")
                return
            actor_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['actor'])
            room_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['room'])
            target_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['target'])
            logger.debug3(f"actor_msg: {actor_msg}, room_msg: {room_msg}, target_msg: {target_msg}")

        if target:
            vars = set_vars(actor, actor, target, actor_msg)
            await actor.echo(CommTypes.DYNAMIC, actor_msg, vars, game_state=cls._game_state)
            await target.echo(CommTypes.DYNAMIC, target_msg, vars, game_state=cls._game_state)
        else:
            target = actor
            vars = set_vars(actor, actor, actor, actor_msg)
            await actor.echo(CommTypes.DYNAMIC, actor_msg, vars, game_state=cls._game_state)
        if actor._location_room:
            if actor.actor_type == ActorType.CHARACTER:
                await actor._location_room.echo(CommTypes.DYNAMIC, "... " 
                                               + room_msg, vars, 
                                               exceptions=([actor] if target == None else [actor, target]), 
                                               game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await actor._location_room.echo(CommTypes.DYNAMIC, room_msg, vars, 
                                               exceptions=([actor] if target == None else [actor, target]), 
                                               game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                await actor._location_room.echo(CommTypes.DYNAMIC, room_msg, vars, 
                                               exceptions=([actor] if target == None else [actor, target]), 
                                               game_state=cls._game_state) 
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")


    async def cmd_setvar_helper(cls, actor: Actor, input: str, target_dict_fn: Callable[[Actor], dict], target_name: str):
        # TODO:M: add targeting objects and rooms
        logger = StructuredLogger(__name__, prefix="cmd_setvar_helper()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}, target_name: {target_name}")
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            logger.warn(f"({pieces}) Set {target_name} var on what kind of target?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var on what kind of target?")
            return
        if pieces[0].lower() != "char":
            logger.warn(f"({pieces}) Only character targets allowed at the moment.")
            await actor.send_text(CommTypes.DYNAMIC, "Only character targets allowed at the moment.")
            return
        if len(pieces) < 2:
            logger.warn(f"({pieces}) Set {target_name} var on whom?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var on whom?")
            return
        if len(pieces) < 3:
            logger.warn(f"({pieces}) Set which {target_name} var?")
            await actor.send_text(CommTypes.DYNAMIC, "Set which temp var?")
            return
        if len(pieces) < 4:
            logger.warn(f"({pieces}) Set {target_name} var to what?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var to what?")
            return
        target = cls._game_state.find_target_character(actor, pieces[1], search_world=True)
        if target == None:
            logger.warn(f"({pieces}) Could not find target.")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
            return
        var_value = ' '.join(pieces[3:])
        vars = set_vars(actor, actor, target, var_value)
        logger.debug3(f"target.name: {target.name}, {target_name} var: {pieces[2]}, var_value: {var_value}")
        var_value = replace_vars(var_value, vars)
        target_dict_fn(target)[pieces[2]] = var_value
        await actor.send_text(CommTypes.DYNAMIC, f"Set {target_name} var {pieces[2]} on {target.name} to {var_value}.")

    async def cmd_settempvar(cls, actor: Actor, input: str):
        await cls.cmd_setvar_helper(actor, input, lambda d : d.temp_variables, "temp")

    async def cmd_setpermvar(cls, actor: Actor, input: str):
        await cls.cmd_setvar_helper(actor, input, lambda d: d.perm_variables, "perm")

    async def cmd_setquestvar(cls, actor: Actor, input: str):
        """
        Set a quest variable for a player with automatic knowledge updates.
        
        Usage: setquestvar <target> <var_id> <value>
        
        Examples:
            setquestvar me murder_mystery.found_body true
            setquestvar @P123 gloomy_graveyard.murder_mystery.identified_killer blacksmith
        
        The var_id can be:
        - Local (2 parts): murder_mystery.found_body - uses target's current zone
        - Full (3 parts): gloomy_graveyard.murder_mystery.found_body
        
        If the variable is defined in the quest schema with knowledge_updates,
        the appropriate world knowledge will be updated automatically.
        """
        logger = StructuredLogger(__name__, prefix="cmd_setquestvar()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Set quest var on whom?")
            return
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Set which quest var?")
            return
        if len(pieces) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Set quest var to what value?")
            return
        
        # Find target (can be "me", a name, or a reference)
        target_str = pieces[0]
        if target_str.lower() == "me":
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, target_str, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_str}'.")
            return
        
        var_id = pieces[1]
        value_str = ' '.join(pieces[2:])
        
        # Parse value - try to interpret as bool/int, fall back to string
        value: Any
        if value_str.lower() == "true":
            value = True
        elif value_str.lower() == "false":
            value = False
        elif value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
            value = int(value_str)
        else:
            value = value_str
        
        # Use the quest schema system
        from .quest_schema import set_quest_var
        set_quest_var(target, var_id, value)
        
        await actor.send_text(CommTypes.DYNAMIC, f"Set quest var '{var_id}' = {value} on {target.name}.")

    async def cmd_getquestvar(cls, actor: Actor, input: str):
        """
        Get a quest variable value for a player.
        
        Usage: getquestvar <target> <var_id>
        
        Examples:
            getquestvar me murder_mystery.found_body
            getquestvar @P123 gloomy_graveyard.murder_mystery.identified_killer
        """
        logger = StructuredLogger(__name__, prefix="cmd_getquestvar()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Get quest var for whom?")
            return
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Get which quest var?")
            return
        
        # Find target
        target_str = pieces[0]
        if target_str.lower() == "me":
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, target_str, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_str}'.")
            return
        
        var_id = pieces[1]
        
        from .quest_schema import get_quest_var
        value = get_quest_var(target, var_id)
        
        await actor.send_text(CommTypes.DYNAMIC, f"Quest var '{var_id}' for {target.name} = {value}")


    async def cmd_show(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_show()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Show what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_character(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Show to whom?")
            return
        text = ' '.join(pieces[1:])
        vars = set_vars(actor, actor, target, text)
        await target.echo(CommTypes.DYNAMIC, text, vars, game_state=cls._game_state)
        await actor.send_text(CommTypes.DYNAMIC, f"You show {target.name} {text}")

    async def cmd_look(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_look()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await CoreActionsInterface.get_instance().do_look_room(actor, actor.location_room)
            return
        pieces = split_preserving_quotes(input)
        keyword = pieces[0].lower()
        
        # Check for "look in <container>" or "look at <target>"
        if len(pieces) > 1 and pieces[0].lower() in ["at", "in"]:
            keyword = pieces[1].lower()
        
        # Check for looking in a direction
        direction_aliases = {
            'n': 'north', 's': 'south', 'e': 'east', 'w': 'west',
            'u': 'up', 'd': 'down', 'north': 'north', 'south': 'south',
            'east': 'east', 'west': 'west', 'up': 'up', 'down': 'down',
            'in': 'in', 'out': 'out'
        }
        
        if keyword in direction_aliases:
            direction = direction_aliases[keyword]
            if direction in actor.location_room.exits:
                exit_obj = actor.location_room.exits[direction]
                if exit_obj.description:
                    await actor.send_text(CommTypes.DYNAMIC, exit_obj.description)
                elif exit_obj.has_door:
                    if exit_obj.is_closed:
                        await actor.send_text(CommTypes.DYNAMIC, f"You see {exit_obj.art_name}. It is closed.")
                    else:
                        await actor.send_text(CommTypes.DYNAMIC, f"You see {exit_obj.art_name}. It is open.")
                else:
                    await actor.send_text(CommTypes.DYNAMIC, f"You see an exit leading {direction}.")
                return
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"There is no exit to the {direction}.")
                return
        
        # Search order: room characters, room objects, inventory objects
        target = cls._game_state.find_target_character(actor, keyword)
        if target is None:
            target = cls._game_state.find_target_object(keyword, actor)  # room objects
        if target is None:
            # Search inventory
            for obj in actor.contents:
                if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                    target = obj
                    break
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, "Look at what?")
            return
        
        if isinstance(target, Character):
            await CoreActionsInterface.get_instance().do_look_character(actor, target)
        elif isinstance(target, Object):
            await CoreActionsInterface.get_instance().do_look_object(actor, target)
            # Fire CATCH_LOOK triggers on the object if it has any
            if TriggerType.CATCH_LOOK in target.triggers_by_type:
                vars = set_vars(actor, actor, target, keyword)
                for trigger in target.triggers_by_type[TriggerType.CATCH_LOOK]:
                    await trigger.run(actor, keyword, vars, cls._game_state)
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Look at what?")


    async def cmd_spawn(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_spawn()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor has admin permissions
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to spawn NPCs.")
            return
            
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")
            return
            
        # Find the NPC template
        npc_id = input.strip()
        if "." not in npc_id:
            npc_id = f"{actor.location_room.zone.id}.{npc_id}"
            
        npc_template = cls._game_state.world_definition.characters.get(npc_id)
        # logger.critical(f"npc_id: {npc_id}")
        # logger.critical(f"npc_template: {npc_template}")
        # for k in cls._game_state.world_definition.characters:
        #     logger.critical(f"defn id: {cls._game_state.world_definition.characters[k].definition_zone_id}.{cls._game_state.world_definition.characters[k].id}")
        if not npc_template:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find NPC template '{npc_id}'")
            return
            
        # Create the NPC
        new_npc = Character.create_from_definition(npc_template, cls._game_state)
        if not new_npc:
            await actor.send_text(CommTypes.DYNAMIC, "Failed to create NPC")
            return
            
        # Ensure connection is properly set to None
        logger.debug3(f"Verifying connection is None for new NPC {new_npc.name} - connection: {new_npc.connection}")
        if new_npc.connection is not None:
            logger.warning(f"Connection was not None for spawned NPC! Forcing to None.")
            new_npc.connection = None
            
        # Place NPC in the current room
        await CoreActionsInterface.get_instance().arrive_room(new_npc, actor.location_room)
        await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_npc.art_name}")
        await CoreActionsInterface.get_instance().do_look_room(actor, actor.location_room)


    async def cmd_spawnobj(cls, actor: Actor, input: str):
        """
        Spawn an object at a specified location.
        
        Usage: spawnobj <object_id> [location]
        
        Location can be:
        - 'here' (default) - spawn in current room
        - 'me' - spawn in actor's inventory
        - 'zone.room' - spawn in specific room
        
        Examples:
            spawnobj sword
            spawnobj gloomy_graveyard.butler_cufflink here
            spawnobj healing_potion me
            spawnobj key gloomy_graveyard.manor_house_entrance
        """
        logger = StructuredLogger(__name__, prefix="cmd_spawnobj()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor has admin permissions
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to spawn objects.")
            return
            
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: spawnobj <object_id> [here|me|zone.room]")
            return
        
        pieces = split_preserving_quotes(input)
        obj_id = pieces[0]
        location = pieces[1] if len(pieces) > 1 else "here"
        
        # Normalize object ID
        if "." not in obj_id:
            obj_id = f"{actor.location_room.zone.id}.{obj_id}"
        
        # Find the object template
        obj_template = cls._game_state.world_definition.objects.get(obj_id)
        if not obj_template:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find object template '{obj_id}'")
            return
        
        # Create the object
        new_obj = Object.create_from_definition(obj_template)
        if not new_obj:
            await actor.send_text(CommTypes.DYNAMIC, "Failed to create object")
            return
        
        # Determine destination
        if location.lower() == "here":
            # Spawn in current room
            actor.location_room.add_object(new_obj)
            await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} in the room.")
        elif location.lower() == "me":
            # Spawn in actor's inventory
            actor.add_to_inventory(new_obj)
            await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} in your inventory.")
        else:
            # Spawn in specific room
            if "." in location:
                zone_id, room_id = location.split(".", 1)
            else:
                zone_id = actor.location_room.zone.id
                room_id = location
            
            zone = cls._game_state.zones.get(zone_id)
            if not zone:
                await actor.send_text(CommTypes.DYNAMIC, f"Zone '{zone_id}' not found.")
                return
            
            room = zone.rooms.get(room_id)
            if not room:
                await actor.send_text(CommTypes.DYNAMIC, f"Room '{room_id}' not found in zone '{zone_id}'.")
                return
            
            room.add_object(new_obj)
            await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} in {room.name}.")


    async def cmd_give(cls, actor: Actor, input: str):
        """
        Give an item from inventory to another character.
        
        Usage: give <item> <target>
        
        Examples:
            give sword guard
            give "rusty key" old_tom
        """
        logger = StructuredLogger(__name__, prefix="cmd_give()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Give what to whom?")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Give what to whom? Usage: give <item> <target>")
            return
        
        item_name = pieces[0]
        target_name = pieces[1]
        
        # Find the item in actor's inventory
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(item_name) or obj.name.lower() == item_name.lower():
                item = obj
                break
        
        if not item:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{item_name}'.")
            return
        
        # Find the target character
        target = cls._game_state.find_target_character(actor, target_name)
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find '{target_name}'.")
            return
        
        if target == actor:
            await actor.send_text(CommTypes.DYNAMIC, "You can't give something to yourself.")
            return
        
        # Transfer the item
        actor.remove_from_inventory(item)
        target.add_to_inventory(item)
        
        # Messages
        await actor.send_text(CommTypes.DYNAMIC, f"You give {item.art_name} to {target.name}.")
        await target.send_text(CommTypes.DYNAMIC, f"{actor.name} gives you {item.art_name}.")
        
        msg = f"{actor.art_name_cap} gives {item.art_name} to {target.name}."
        vars = set_vars(actor, actor, target, msg)
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls._game_state)
        
        # Fire ON_RECEIVE triggers on the target (for NPC quest reactions)
        # Target (NPC) executes the script, giver is %s%/%S%
        if TriggerType.ON_RECEIVE in target.triggers_by_type:
            receive_vars = set_vars(target, actor, actor, msg)
            receive_vars.update({
                'item': item.name,
                'item_id': item.id,
                'item_name': item.name,
                'giver': actor.name,
                'giver_id': actor.id,
            })
            for trigger in target.triggers_by_type[TriggerType.ON_RECEIVE]:
                await trigger.run(target, item.id, receive_vars, cls._game_state)


    async def cmd_pause(cls, actor: Actor, input: str):
        """
        Pause script execution for a specified number of seconds.
        
        Usage: pause <seconds>
        
        This uses the scheduled events system to delay subsequent commands.
        Primarily used in scripts for dramatic effect.
        
        Examples:
            pause 2
            pause 0.5
        """
        import asyncio
        logger = StructuredLogger(__name__, prefix="cmd_pause()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Pause for how many seconds?")
            return
        
        try:
            seconds = float(input.strip())
        except ValueError:
            await actor.send_text(CommTypes.DYNAMIC, f"Invalid duration: {input}")
            return
        
        if seconds < 0:
            await actor.send_text(CommTypes.DYNAMIC, "Duration cannot be negative.")
            return
        
        if seconds > 60:
            await actor.send_text(CommTypes.DYNAMIC, "Maximum pause duration is 60 seconds.")
            return
        
        # Use asyncio.sleep for the pause
        await asyncio.sleep(seconds)


    async def cmd_removeitem(cls, actor: Actor, input: str):
        """
        Remove an item from a character's inventory (destroys it).
        
        This is a privileged/script command for quest completion, item consumption, etc.
        
        Usage: removeitem <target> <item>
        
        Target can be:
        - 'me' - remove from the actor's inventory
        - character name/reference - remove from that character
        
        Examples:
            removeitem me old_key
            removeitem %S% quest_item
        """
        logger = StructuredLogger(__name__, prefix="cmd_removeitem()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: removeitem <target> <item>")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: removeitem <target> <item>")
            return
        
        target_name = pieces[0]
        item_name = pieces[1]
        
        # Find target character
        if target_name.lower() == "me":
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_name}'.")
            return
        
        # Find item in target's inventory
        item = None
        for obj in target.contents:
            if obj.matches_keyword(item_name) or obj.name.lower() == item_name.lower() or obj.id == item_name:
                item = obj
                break
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"{target.name} doesn't have '{item_name}'.")
            return
        
        # Remove and destroy the item
        target.remove_from_inventory(item)
        item.is_deleted = True
        
        # Send feedback
        if target == actor:
            await actor.send_text(CommTypes.DYNAMIC, f"{item.art_name_cap} has been removed from your inventory.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Removed {item.art_name} from {target.name}'s inventory.")


    async def cmd_transfer(cls, actor: Actor, input: str):
        """
        Transfer a character to a specific room.
        
        This is a privileged/script command. Shows magical teleport effects.
        
        Usage: transfer <target> <zone.room>
        
        Examples:
            transfer %S% gloomy_graveyard.manor_house_foyer
            transfer me debug_zone.starting_room
        """
        logger = StructuredLogger(__name__, prefix="cmd_transfer()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: transfer <target> <zone.room>")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: transfer <target> <zone.room>")
            return
        
        target_name = pieces[0]
        destination = pieces[1]
        
        # Find target character
        if target_name.lower() == "me":
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_name}'.")
            return
        
        # Parse destination
        if "." in destination:
            zone_id, room_id = destination.split(".", 1)
        else:
            zone_id = actor.location_room.zone.id if actor.location_room else None
            room_id = destination
        
        if not zone_id:
            await actor.send_text(CommTypes.DYNAMIC, "Could not determine zone.")
            return
        
        zone = cls._game_state.zones.get(zone_id)
        if not zone:
            await actor.send_text(CommTypes.DYNAMIC, f"Zone '{zone_id}' not found.")
            return
        
        room = zone.rooms.get(room_id)
        if not room:
            await actor.send_text(CommTypes.DYNAMIC, f"Room '{room_id}' not found in zone '{zone_id}'.")
            return
        
        # Echo departure message
        if target.location_room:
            msg = f"{target.art_name_cap} vanishes in a puff of smoke!"
            await target.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[target], game_state=cls._game_state)
            await target.send_text(CommTypes.DYNAMIC, "You feel a magical force pulling you away...")
            target.location_room.remove_character(target)
            target.location_room = None
        
        # Arrive at destination
        await CoreActionsInterface.get_instance().arrive_room(target, room)
        
        # Echo arrival message
        msg = f"{target.art_name_cap} appears with a thunderclap!"
        await room.echo(CommTypes.DYNAMIC, msg, exceptions=[target], game_state=cls._game_state)
        await target.send_text(CommTypes.DYNAMIC, "...and find yourself somewhere else!")


    async def cmd_interrupt(cls, actor: Actor, input: str):
        """
        Clear a character's command queue.
        
        This is a privileged/script command. Useful for:
        - Admins stopping a runaway NPC
        - Scripts forcing immediate reactions: force guard interrupt; attack player
        
        Usage: interrupt <target>
        
        Examples:
            interrupt guard
            force guard interrupt; attack player
        """
        logger = StructuredLogger(__name__, prefix="cmd_interrupt()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: interrupt <target>")
            return
        
        target_name = input.strip()
        
        # Find target character
        target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_name}'.")
            return
        
        # Clear the command queue
        queue_size = len(target.command_queue)
        target.command_queue.clear()
        
        logger.debug(f"Cleared {queue_size} command(s) from {target.name}'s queue")
        await actor.send_text(CommTypes.DYNAMIC, f"Cleared {queue_size} queued command(s) from {target.name}.")


    async def cmd_force(cls, actor: Actor, input: str):
        """
        Force a character to execute one or more commands.
        
        This is a privileged/script command.
        
        Usage: force <target> <command>[;<command>;...]
        
        Multiple commands can be separated by semicolons. They will be added
        to the target's command queue and executed in order.
        
        Examples:
            force guard say Halt! Who goes there?
            force butler unlock bedroom_door; open bedroom_door; emote enters his room
            force %T% drop sword
        """
        logger = StructuredLogger(__name__, prefix="cmd_force()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: force <target> <command>[;<command>;...]")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: force <target> <command>[;<command>;...]")
            return
        
        target_name = pieces[0]
        command_string = ' '.join(pieces[1:])
        
        # Find target character
        target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_name}'.")
            return
        
        # Split commands by semicolon
        commands = [cmd.strip() for cmd in command_string.split(';') if cmd.strip()]
        
        # Add all commands to the target's command queue and execute them
        logger.debug(f"Forcing {target.name} to execute {len(commands)} command(s): {commands}")
        for command in commands:
            await cls.process_command(target, command, {})


    def _find_exit_door(cls, actor: Actor, keyword: str):
        """
        Find an exit with a door matching the given keyword.
        Returns tuple of (direction, Exit) or (None, None) if not found.
        """
        from .nondb_models.room_interface import Exit
        keyword_lower = keyword.lower()
        for direction, exit_obj in actor.location_room.exits.items():
            if exit_obj.has_door and exit_obj.matches_keyword(keyword_lower):
                return direction, exit_obj
            # Also match direction names like "north door"
            if keyword_lower == direction or keyword_lower == f"{direction} door":
                if exit_obj.has_door:
                    return direction, exit_obj
        return None, None


    def _get_linked_exit(cls, exit_obj):
        """
        Get the linked exit for a door, if any.
        Returns tuple of (Room, direction, Exit) or (None, None, None).
        """
        if not exit_obj.linked_exit:
            return None, None, None
        
        parts = exit_obj.linked_exit.split('.')
        if len(parts) != 3:
            return None, None, None
        
        zone_id, room_id, direction = parts
        zone = cls._game_state.zones.get(zone_id)
        if not zone:
            return None, None, None
        
        room = zone.rooms.get(room_id)
        if not room:
            return None, None, None
        
        linked_exit = room.exits.get(direction)
        if not linked_exit:
            return None, None, None
        
        return room, direction, linked_exit


    def _is_privileged_actor(cls, actor: Actor) -> bool:
        """Check if actor can bypass door key requirements."""
        from .nondb_models.character_interface import PermanentCharacterFlags
        return (actor.has_game_flags(GamePermissionFlags.IS_ADMIN) or 
                actor.actor_type == ActorType.ROOM or 
                actor.actor_type == ActorType.OBJECT or
                (actor.actor_type == ActorType.CHARACTER and 
                 not actor.has_perm_flags(PermanentCharacterFlags.IS_PC)))


    async def cmd_open(cls, actor: Actor, input: str):
        """
        Open an openable object or exit door.
        
        If actor is admin, NPC, room, or object - always succeeds.
        Otherwise, checks if locked.
        """
        logger = StructuredLogger(__name__, prefix="cmd_open()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Open what?")
            return
        
        pieces = split_preserving_quotes(input)
        keyword = pieces[0]
        
        # Search room objects, then inventory
        target = cls._game_state.find_target_object(keyword, actor)
        if target is None:
            for obj in actor.contents:
                if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                    target = obj
                    break
        
        # If no object found, check for exit doors
        exit_direction, exit_obj = None, None
        if target is None:
            exit_direction, exit_obj = cls._find_exit_door(actor, keyword)
        
        if target is None and exit_obj is None:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that here.")
            return
        
        is_privileged = cls._is_privileged_actor(actor)
        
        if exit_obj:
            # Opening an exit door
            if not exit_obj.is_closed:
                await actor.send_text(CommTypes.DYNAMIC, f"{exit_obj.art_name_cap} is already open.")
                return
            
            if exit_obj.is_locked and not is_privileged:
                await actor.send_text(CommTypes.DYNAMIC, f"{exit_obj.art_name_cap} is locked.")
                return
            
            exit_obj.is_closed = False
            await actor.send_text(CommTypes.DYNAMIC, f"You open {exit_obj.art_name}.")
            
            msg = f"{actor.art_name_cap} opens {exit_obj.art_name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[actor], game_state=cls._game_state)
            
            # Sync linked exit and echo to both rooms
            linked_room, linked_dir, linked_exit = cls._get_linked_exit(exit_obj)
            if linked_exit:
                linked_exit.is_closed = False
                # Echo to the other room - they see/hear the door open
                msg = f"The {linked_exit.door_name} opens."
                await linked_room.echo(CommTypes.DYNAMIC, msg, game_state=cls._game_state)
        else:
            # Opening an object
            if not target.has_flags(ObjectFlags.IS_OPENABLE):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't open {target.art_name}.")
                return
            
            if not target.has_flags(ObjectFlags.IS_CLOSED):
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is already open.")
                return
            
            if target.has_flags(ObjectFlags.IS_LOCKED) and not is_privileged:
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is locked.")
                return
            
            target.remove_flags(ObjectFlags.IS_CLOSED)
            await actor.send_text(CommTypes.DYNAMIC, f"You open {target.art_name}.")
            
            msg = f"{actor.art_name_cap} opens {target.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            
            # Fire ON_OPEN triggers (object executes, player is %s%/%S%)
            if TriggerType.ON_OPEN in target.triggers_by_type:
                trigger_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_OPEN]:
                    await trigger.run(target, target.id, trigger_vars, cls._game_state)


    async def cmd_close(cls, actor: Actor, input: str):
        """Close an openable object or exit door."""
        logger = StructuredLogger(__name__, prefix="cmd_close()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Close what?")
            return
        
        pieces = split_preserving_quotes(input)
        keyword = pieces[0]
        
        target = cls._game_state.find_target_object(keyword, actor)
        if target is None:
            for obj in actor.contents:
                if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                    target = obj
                    break
        
        # If no object found, check for exit doors
        exit_direction, exit_obj = None, None
        if target is None:
            exit_direction, exit_obj = cls._find_exit_door(actor, keyword)
        
        if target is None and exit_obj is None:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that here.")
            return
        
        if exit_obj:
            # Closing an exit door
            if exit_obj.is_closed:
                await actor.send_text(CommTypes.DYNAMIC, f"{exit_obj.art_name_cap} is already closed.")
                return
            
            exit_obj.is_closed = True
            await actor.send_text(CommTypes.DYNAMIC, f"You close {exit_obj.art_name}.")
            
            msg = f"{actor.art_name_cap} closes {exit_obj.art_name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[actor], game_state=cls._game_state)
            
            # Sync linked exit and echo to both rooms
            linked_room, linked_dir, linked_exit = cls._get_linked_exit(exit_obj)
            if linked_exit:
                linked_exit.is_closed = True
                # Echo to the other room - they see/hear the door close
                msg = f"The {linked_exit.door_name} closes."
                await linked_room.echo(CommTypes.DYNAMIC, msg, game_state=cls._game_state)
        else:
            # Closing an object
            if not target.has_flags(ObjectFlags.IS_OPENABLE):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't close {target.art_name}.")
                return
            
            if target.has_flags(ObjectFlags.IS_CLOSED):
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is already closed.")
                return
            
            target.set_flags(ObjectFlags.IS_CLOSED)
            await actor.send_text(CommTypes.DYNAMIC, f"You close {target.art_name}.")
            
            msg = f"{actor.art_name_cap} closes {target.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            
            # Fire ON_CLOSE triggers (object executes, player is %s%/%S%)
            if TriggerType.ON_CLOSE in target.triggers_by_type:
                trigger_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_CLOSE]:
                    await trigger.run(target, target.id, trigger_vars, cls._game_state)


    async def cmd_lock(cls, actor: Actor, input: str):
        """
        Lock a lockable object or exit door.
        
        If actor is admin, NPC, room, or object - always succeeds.
        Otherwise, requires having the correct key.
        """
        logger = StructuredLogger(__name__, prefix="cmd_lock()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Lock what?")
            return
        
        pieces = split_preserving_quotes(input)
        keyword = pieces[0]
        
        target = cls._game_state.find_target_object(keyword, actor)
        if target is None:
            for obj in actor.contents:
                if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                    target = obj
                    break
        
        # If no object found, check for exit doors
        exit_direction, exit_obj = None, None
        if target is None:
            exit_direction, exit_obj = cls._find_exit_door(actor, keyword)
        
        if target is None and exit_obj is None:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that here.")
            return
        
        is_privileged = cls._is_privileged_actor(actor)
        
        if exit_obj:
            # Locking an exit door
            if exit_obj.is_locked:
                await actor.send_text(CommTypes.DYNAMIC, f"{exit_obj.art_name_cap} is already locked.")
                return
            
            if not exit_obj.is_closed:
                await actor.send_text(CommTypes.DYNAMIC, f"You need to close {exit_obj.art_name} first.")
                return
            
            # Check for key
            key_id = exit_obj.key_id
            if key_id and not is_privileged:
                has_key = False
                for obj in actor.contents:
                    if obj.id == key_id or obj.matches_keyword(key_id):
                        has_key = True
                        break
                if not has_key:
                    await actor.send_text(CommTypes.DYNAMIC, f"You don't have the key to {exit_obj.art_name}.")
                    return
            
            exit_obj.is_locked = True
            await actor.send_text(CommTypes.DYNAMIC, f"You lock {exit_obj.art_name}.")
            
            msg = f"{actor.art_name_cap} locks {exit_obj.art_name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[actor], game_state=cls._game_state)
            
            # Sync linked exit
            linked_room, linked_dir, linked_exit = cls._get_linked_exit(exit_obj)
            if linked_exit:
                linked_exit.is_locked = True
                # No echo for locking from other side - it's silent
        else:
            # Locking an object
            if not target.has_flags(ObjectFlags.IS_LOCKABLE):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't lock {target.art_name}.")
                return
            
            if target.has_flags(ObjectFlags.IS_LOCKED):
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is already locked.")
                return
            
            if target.has_flags(ObjectFlags.IS_OPENABLE) and not target.has_flags(ObjectFlags.IS_CLOSED):
                await actor.send_text(CommTypes.DYNAMIC, f"You need to close {target.art_name} first.")
                return
            
            key_id = target.get_perm_var("key_id", None)
            if key_id and not is_privileged:
                has_key = False
                for obj in actor.contents:
                    if obj.id == key_id or obj.matches_keyword(key_id):
                        has_key = True
                        break
                if not has_key:
                    await actor.send_text(CommTypes.DYNAMIC, f"You don't have the key to {target.art_name}.")
                    return
            
            target.set_flags(ObjectFlags.IS_LOCKED)
            await actor.send_text(CommTypes.DYNAMIC, f"You lock {target.art_name}.")
            
            msg = f"{actor.art_name_cap} locks {target.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            
            # Fire ON_LOCK triggers (object executes, player is %s%/%S%)
            if TriggerType.ON_LOCK in target.triggers_by_type:
                trigger_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_LOCK]:
                    await trigger.run(target, target.id, trigger_vars, cls._game_state)


    async def cmd_unlock(cls, actor: Actor, input: str):
        """
        Unlock a lockable object or exit door.
        
        If actor is admin, NPC, room, or object - always succeeds.
        Otherwise, requires having the correct key.
        """
        logger = StructuredLogger(__name__, prefix="cmd_unlock()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Unlock what?")
            return
        
        pieces = split_preserving_quotes(input)
        keyword = pieces[0]
        
        target = cls._game_state.find_target_object(keyword, actor)
        if target is None:
            for obj in actor.contents:
                if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                    target = obj
                    break
        
        # If no object found, check for exit doors
        exit_direction, exit_obj = None, None
        if target is None:
            exit_direction, exit_obj = cls._find_exit_door(actor, keyword)
        
        if target is None and exit_obj is None:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that here.")
            return
        
        is_privileged = cls._is_privileged_actor(actor)
        
        if exit_obj:
            # Unlocking an exit door
            if not exit_obj.is_locked:
                await actor.send_text(CommTypes.DYNAMIC, f"{exit_obj.art_name_cap} is not locked.")
                return
            
            # Check for key
            key_id = exit_obj.key_id
            if key_id and not is_privileged:
                has_key = False
                for obj in actor.contents:
                    if obj.id == key_id or obj.matches_keyword(key_id):
                        has_key = True
                        break
                if not has_key:
                    await actor.send_text(CommTypes.DYNAMIC, f"You don't have the key to {exit_obj.art_name}.")
                    return
            
            exit_obj.is_locked = False
            await actor.send_text(CommTypes.DYNAMIC, f"You unlock {exit_obj.art_name}.")
            
            msg = f"{actor.art_name_cap} unlocks {exit_obj.art_name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[actor], game_state=cls._game_state)
            
            # Sync linked exit
            linked_room, linked_dir, linked_exit = cls._get_linked_exit(exit_obj)
            if linked_exit:
                linked_exit.is_locked = False
                # No echo for unlocking from other side - it's silent
        else:
            # Unlocking an object
            if not target.has_flags(ObjectFlags.IS_LOCKABLE):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't unlock {target.art_name}.")
                return
            
            if not target.has_flags(ObjectFlags.IS_LOCKED):
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is not locked.")
                return
            
            key_id = target.get_perm_var("key_id", None)
            if key_id and not is_privileged:
                has_key = False
                for obj in actor.contents:
                    if obj.id == key_id or obj.matches_keyword(key_id):
                        has_key = True
                        break
                if not has_key:
                    await actor.send_text(CommTypes.DYNAMIC, f"You don't have the key to {target.art_name}.")
                    return
            
            target.remove_flags(ObjectFlags.IS_LOCKED)
            await actor.send_text(CommTypes.DYNAMIC, f"You unlock {target.art_name}.")
            
            msg = f"{actor.art_name_cap} unlocks {target.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            
            # Fire ON_UNLOCK triggers (object executes, player is %s%/%S%)
            if TriggerType.ON_UNLOCK in target.triggers_by_type:
                trigger_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_UNLOCK]:
                    await trigger.run(target, target.id, trigger_vars, cls._game_state)


    async def cmd_use(cls, actor: Actor, input: str):
        """
        Use an object, optionally on a target.
        
        Usage: 
            use <item>
            use <item> on <target>
        
        Examples:
            use potion
            use key on door
            use lever
        """
        logger = StructuredLogger(__name__, prefix="cmd_use()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Use what?")
            return
        
        # Parse "use X on Y" format
        parts = input.lower().split(" on ", 1)
        item_name = parts[0].strip()
        target_name = parts[1].strip() if len(parts) > 1 else None
        
        # Find the item (inventory first, then room)
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(item_name) or obj.name.lower() == item_name:
                item = obj
                break
        
        if item is None:
            item = cls._game_state.find_target_object(item_name, actor)
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{item_name}'.")
            return
        
        # Find target if specified
        target = None
        if target_name:
            # Try object first
            target = cls._game_state.find_target_object(target_name, actor)
            if target is None:
                for obj in actor.contents:
                    if obj.matches_keyword(target_name) or obj.name.lower() == target_name:
                        target = obj
                        break
            # Try character
            if target is None:
                target = cls._game_state.find_target_character(actor, target_name)
        
        # Check if this is a consumable item we can handle directly
        if item.object_flags.are_flags_set(ObjectFlags.IS_CONSUMABLE) or \
           item.object_flags.are_flags_set(ObjectFlags.IS_POTION) or \
           item.object_flags.are_flags_set(ObjectFlags.IS_BANDAGE) or \
           item.object_flags.are_flags_set(ObjectFlags.IS_FOOD):
            await cls._use_consumable(actor, item, target)
            return
        
        # Check if item has ON_USE triggers
        if TriggerType.ON_USE not in item.triggers_by_type:
            if target:
                await actor.send_text(CommTypes.DYNAMIC, f"You can't use {item.art_name} on {target.art_name}.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"You can't figure out how to use {item.art_name}.")
            return
        
        # Build vars - item executes, player is %s%/%S%, target is %t%/%T%
        use_vars = set_vars(item, actor, target if target else actor, item.name)
        if target:
            use_vars['target'] = target.name
            use_vars['target_id'] = target.id
        
        # Fire ON_USE triggers (object executes)
        triggered = False
        for trigger in item.triggers_by_type[TriggerType.ON_USE]:
            result = await trigger.run(item, item.id, use_vars, cls._game_state)
            if result:
                triggered = True
        
        if not triggered:
            if target:
                await actor.send_text(CommTypes.DYNAMIC, f"Using {item.art_name} on {target.art_name} has no effect.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"Using {item.art_name} has no effect.")


    async def _use_consumable(cls, actor: Actor, item: Object, target: Actor = None):
        """
        Handle using a consumable item (potion, bandage, food).
        Applies healing/restoration effects and removes/decrements the item.
        """
        from .utility import roll_dice, get_dice_parts
        
        logger = StructuredLogger(__name__, prefix="_use_consumable()> ")
        
        # Determine the actual target (self if not specified)
        heal_target = target if target and target.actor_type == ActorType.CHARACTER else actor
        
        # Check if bandage - can't use in combat
        if item.object_flags.are_flags_set(ObjectFlags.IS_BANDAGE):
            if actor.fighting_whom is not None:
                await actor.send_text(CommTypes.DYNAMIC, "You can't apply a bandage while fighting!")
                return
        
        # Calculate healing amount
        heal_amount = item.heal_amount
        if item.heal_dice:
            dice_parts = get_dice_parts(item.heal_dice)
            if dice_parts:
                heal_amount += roll_dice(dice_parts[0], dice_parts[1]) + dice_parts[2]
        
        # Apply effects
        effects_applied = []
        
        # HP healing
        if heal_amount > 0:
            old_hp = heal_target.current_hit_points
            heal_target.current_hit_points = min(heal_target.max_hit_points, 
                                                  heal_target.current_hit_points + heal_amount)
            actual_heal = heal_target.current_hit_points - old_hp
            if actual_heal > 0:
                effects_applied.append(f"healed {actual_heal} HP")
        
        # Mana restoration
        if item.mana_restore > 0 and heal_target.max_mana > 0:
            old_mana = heal_target.current_mana
            heal_target.current_mana = min(heal_target.max_mana, 
                                           heal_target.current_mana + item.mana_restore)
            actual_restore = int(heal_target.current_mana - old_mana)
            if actual_restore > 0:
                effects_applied.append(f"restored {actual_restore} mana")
        
        # Stamina restoration
        if item.stamina_restore > 0 and heal_target.max_stamina > 0:
            old_stamina = heal_target.current_stamina
            heal_target.current_stamina = min(heal_target.max_stamina, 
                                              heal_target.current_stamina + item.stamina_restore)
            actual_restore = int(heal_target.current_stamina - old_stamina)
            if actual_restore > 0:
                effects_applied.append(f"restored {actual_restore} stamina")
        
        # Determine the verb based on item type
        if item.object_flags.are_flags_set(ObjectFlags.IS_POTION):
            verb = "quaff"
            verb_past = "quaff"
        elif item.object_flags.are_flags_set(ObjectFlags.IS_BANDAGE):
            verb = "apply"
            verb_past = "applies"
        elif item.object_flags.are_flags_set(ObjectFlags.IS_FOOD):
            verb = "eat"
            verb_past = "eats"
        else:
            verb = "use"
            verb_past = "uses"
        
        # Send messages
        if item.use_message:
            # Custom use message
            msg = item.use_message
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, heal_target, msg), 
                           game_state=cls._game_state)
        else:
            # Default messages
            if heal_target == actor:
                await actor.send_text(CommTypes.DYNAMIC, f"You {verb} {item.art_name}.")
                msg = f"{firstcap(actor.name)} {verb_past} {item.art_name}."
                await actor.location_room.echo(CommTypes.DYNAMIC, msg, 
                                               set_vars(actor, actor, actor, msg),
                                               exceptions=[actor], game_state=cls._game_state)
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"You {verb} {item.art_name} on {heal_target.art_name}.")
                await heal_target.send_text(CommTypes.DYNAMIC, f"{firstcap(actor.name)} {verb_past} {item.art_name} on you.")
                msg = f"{firstcap(actor.name)} {verb_past} {item.art_name} on {heal_target.art_name}."
                await actor.location_room.echo(CommTypes.DYNAMIC, msg,
                                               set_vars(actor, actor, heal_target, msg),
                                               exceptions=[actor, heal_target], game_state=cls._game_state)
        
        # Report effects
        if effects_applied:
            effects_str = ", ".join(effects_applied)
            if heal_target == actor:
                await actor.send_text(CommTypes.DYNAMIC, f"You feel better! ({effects_str})")
            else:
                await heal_target.send_text(CommTypes.DYNAMIC, f"You feel better! ({effects_str})")
                await actor.send_text(CommTypes.DYNAMIC, f"{firstcap(heal_target.name)} is healed. ({effects_str})")
        
        # Send status update
        if heal_target.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await heal_target.send_status_update()
        
        # Handle item consumption
        if item.charges == -1:
            # Single use - destroy the item
            if item.in_actor:
                item.in_actor.contents.remove(item)
            item.delete()
        elif item.charges > 0:
            item.charges -= 1
            if item.charges == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"{firstcap(item.art_name)} is now empty.")


    async def cmd_quaff(cls, actor: Actor, input: str):
        """Drink a potion."""
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Quaff what?")
            return
        
        # Find the potion in inventory
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(input.lower()) or obj.name.lower() == input.lower():
                item = obj
                break
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{input}'.")
            return
        
        if not item.object_flags.are_flags_set(ObjectFlags.IS_POTION):
            await actor.send_text(CommTypes.DYNAMIC, f"You can't quaff {item.art_name}.")
            return
        
        await cls._use_consumable(actor, item)


    async def cmd_drink(cls, actor: Actor, input: str):
        """Alias for quaff."""
        await cls.cmd_quaff(actor, input)


    async def cmd_apply(cls, actor: Actor, input: str):
        """Apply a bandage to yourself or another character."""
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Apply what?")
            return
        
        # Parse "apply X to Y" format
        parts = input.lower().split(" to ", 1)
        item_name = parts[0].strip()
        target_name = parts[1].strip() if len(parts) > 1 else None
        
        # Find the bandage in inventory
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(item_name) or obj.name.lower() == item_name:
                item = obj
                break
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{item_name}'.")
            return
        
        if not item.object_flags.are_flags_set(ObjectFlags.IS_BANDAGE):
            await actor.send_text(CommTypes.DYNAMIC, f"You can't apply {item.art_name} as a bandage.")
            return
        
        # Find target if specified
        target = None
        if target_name:
            target = cls._game_state.find_target_character(actor, target_name)
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't see '{target_name}' here.")
                return
        
        await cls._use_consumable(actor, item, target)


    async def cmd_eat(cls, actor: Actor, input: str):
        """Eat food."""
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Eat what?")
            return
        
        # Find the food in inventory
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(input.lower()) or obj.name.lower() == input.lower():
                item = obj
                break
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{input}'.")
            return
        
        if not item.object_flags.are_flags_set(ObjectFlags.IS_FOOD):
            await actor.send_text(CommTypes.DYNAMIC, f"You can't eat {item.art_name}.")
            return
        
        await cls._use_consumable(actor, item)


    async def cmd_makeadmin(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_makeadmin()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor has admin permissions
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to make others admin.")
            return
            
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Make whom admin?")
            return
            
        # Find the target character
        target = cls._game_state.find_target_character(actor, input)
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Could not find that character.")
            return
            
        # Add admin flags to target
        target.add_game_flags(GamePermissionFlags.IS_ADMIN)
        
        # Notify the player
        await actor.send_text(CommTypes.DYNAMIC, f"Made {target.art_name} an admin.")
        await target.send_text(CommTypes.DYNAMIC, "You have been granted admin privileges.")

    async def cmd_possess(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_possess()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor has admin permissions
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to possess NPCs.")
            return
            
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Possess whom?")
            return
            
        try:
            # Find the target character, excluding the initiating actor
            logger.debug3(f"Attempting to find possess target: {input}")
            target = cls._game_state.find_target_character(actor, input, exclude_initiator=True)
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, "Could not find that character.")
                return
                
            logger.debug3(f"Found possess target: {target.rid}, name: {target.name}")
            logger.debug3(f"Possess Target connection: {target.connection}")
            logger.debug3(f"PossessActor connection: {actor.connection}")
            
            # Don't allow possessing yourself - this should never happen now with exclude_initiator=True
            if target == actor:
                await actor.send_text(CommTypes.DYNAMIC, "You can't possess yourself.")
                return
                
            # Save the current character's state
            logger.debug2(f"Possessing {target.art_name}")
            old_char = actor
            old_connection = old_char.connection
            was_admin = old_char.has_game_flags(GamePermissionFlags.IS_ADMIN)
            
            if old_connection is None:
                logger.debug2("Possess Actor has no connection!")
                await actor.send_text(CommTypes.DYNAMIC, "You have no connection to transfer.")
                return
            
            # If the target somehow has a connection, fix it by setting to None
            if target.connection is not None:
                logger.debug3(f"Possess Target has a connection object - resetting it to None")
                target.connection = None
                        
            # Notify the player before transferring connection
            logger.debug3(f"Sending pre-transfer notification")
            await actor.send_text(CommTypes.DYNAMIC, f"You are about to possess {target.art_name}")
            await asyncio.sleep(0) # Yield control to allow pending writes
                
            # Reuse the existing connection for the target
            consumer = old_connection.consumer_
            old_connection.character = target
            target.connection = old_connection
            old_char.connection = None

            # Update consumer's character reference if necessary
            if hasattr(consumer, 'character'):
                consumer.character = target
            
            # Add player flags to target
            logger.debug3("Adding player flags to possess target")
            target.add_perm_flags(PermanentCharacterFlags.IS_PC)
            if was_admin:
                target.add_game_flags(GamePermissionFlags.IS_ADMIN)
            
            # Remove player flags from old character
            logger.debug3("Removing player flags from old possess character")
            old_char.remove_perm_flags(PermanentCharacterFlags.IS_PC)
            old_char.remove_game_flags(GamePermissionFlags.IS_ADMIN)
            
            # Update game state
            logger.debug2(f"Removing old possess character from game state: {old_char.rid}")
            if old_char in cls._game_state.players:
                cls._game_state.players.remove(old_char)
            else:
                logger.debug2(f"Old possess character {old_char.rid} not found in players list")
                
            logger.debug2(f"Adding new possess character to game state: {target.rid}")
            if target not in cls._game_state.players:
                cls._game_state.players.append(target)
            
            # Send notification after transfer
            logger.debug3(f"Sending post-transfer possess notification")
            await target.send_text(CommTypes.DYNAMIC, f"You are now possessing {target.art_name}")
            await target.send_text(CommTypes.DYNAMIC, "Your old character has been saved. Use 'load' to return to it later.")
            
            # Force a room look to orient the player
            logger.debug3(f"Forcing possess target room look")
            await asyncio.sleep(0) # Yield again before the final look
            await CoreActionsInterface.get_instance().do_look_room(target, target.location_room)
            
        except Exception as e:
            logger.error(f"Error during possession: {str(e)}")
            logger.exception("Exception during possession")
            await actor.send_text(CommTypes.DYNAMIC, f"Failed to possess character: {str(e)}")
            return

    async def cmd_goto(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_goto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Go to where?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_room(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Go to where?")
            return
        await CoreActionsInterface.get_instance().arrive_room(actor, target)


    async def cmd_list(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_list()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "List what?")
            return
        pieces = split_preserving_quotes(input)
        if pieces[0].lower() == "chars":
            chars = [c for c in Actor.references_.values() if c.actor_type == ActorType.CHARACTER]
            await actor.send_text(CommTypes.DYNAMIC, f"Characters: {', '.join([c.rid for c in chars])}")
        elif pieces[0].lower() == "objects":
            objs = [o for o in Actor.references_.values() if o.actor_type == ActorType.OBJECT]
            await actor.send_text(CommTypes.DYNAMIC, f"Objects: {', '.join([o.rid for o in objs])}")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "List what?")

    async def cmd_attack(cls, command: str, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_attack()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Attack what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_character(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Attack what?")
            return
        # Prevent attacking unkillable NPCs (important NPCs without respawn)
        if target.is_unkillable:
            await actor.send_text(CommTypes.DYNAMIC, f"You cannot attack {target.art_name}.")
            return
        await CoreActionsInterface.get_instance().start_fighting(actor, target)
        # TODO:L: maybe some situations where target doesn't retaliate?
        await CoreActionsInterface.get_instance().start_fighting(target, actor)


    async def cmd_flee(cls, actor: Actor, input: str):
        """
        Attempt to flee from combat.
        
        Success is based on:
        - Dexterity modifier: +(DEX - 10) * 4
        - Rogue class bonus: +10 per rogue level tier (max +30)
        - Number of attackers: -10 per enemy attacking you
        - Low HP bonus: +15 if HP < 25%
        - Stunned/Frozen/Sleeping: Cannot flee
        - Sitting: -20 penalty
        
        Flee direction is weighted 70% toward retreat (direction entered from),
        30% random from available exits.
        
        Guards can block exits to rooms they guard.
        """
        import random
        from .constants import CharacterClassRole
        from .nondb_models.character_interface import CharacterAttributes, TemporaryCharacterFlags
        
        logger = StructuredLogger(__name__, prefix="cmd_flee()> ")
        logger.debug3(f"actor.rid: {actor.rid}")
        
        # Must be fighting
        if actor.fighting_whom is None:
            await actor.send_text(CommTypes.DYNAMIC, "You're not fighting anyone!")
            return
        
        # Cannot flee while incapacitated
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            await actor.send_text(CommTypes.DYNAMIC, "You're too stunned to flee!")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_FROZEN):
            await actor.send_text(CommTypes.DYNAMIC, "You're frozen solid and can't move!")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.DYNAMIC, "You can't flee while sleeping!")
            return
        
        room = actor.location_room
        if not room or not room.exits:
            await actor.send_text(CommTypes.DYNAMIC, "There's nowhere to flee!")
            return
        
        # Build list of valid exits (not blocked by guards)
        valid_exits = []
        for direction, exit_obj in room.exits.items():
            # Check for closed doors
            if exit_obj.has_door and exit_obj.is_closed:
                continue
            
            # Determine full destination
            destination = exit_obj.destination
            if "." in destination:
                zone_id, room_id = destination.split(".")
            else:
                zone_id = room.zone.id
                room_id = destination
            full_destination = f"{zone_id}.{room_id}"
            
            # Check if guarded
            blocking_guard = actor.get_guarded_destination(full_destination)
            if blocking_guard:
                continue
            
            valid_exits.append(direction)
        
        if not valid_exits:
            await actor.send_text(CommTypes.DYNAMIC, "There's no way past your enemies!")
            return
        
        # Calculate flee success chance
        base_chance = 50
        flee_roll = random.randint(1, 100)
        
        # Dexterity modifier: +(DEX - 10) * 4
        dex = actor.attributes.get(CharacterAttributes.DEXTERITY, 10)
        dex_mod = (dex - 10) * 4
        
        # Rogue class bonus: +10 per tier (levels 1-9 = +10, 10-19 = +20, 20+ = +30)
        rogue_level = actor.levels_by_role.get(CharacterClassRole.ROGUE, 0)
        rogue_bonus = 0
        if rogue_level >= 20:
            rogue_bonus = 30
        elif rogue_level >= 10:
            rogue_bonus = 20
        elif rogue_level >= 1:
            rogue_bonus = 10
        
        # Penalty for number of attackers: -10 per enemy
        num_attackers = sum(1 for c in room.get_characters() if c.fighting_whom == actor)
        attacker_penalty = num_attackers * 10
        
        # Low HP bonus: +15 if HP < 25%
        hp_bonus = 0
        if actor.current_hit_points < actor.max_hit_points * 0.25:
            hp_bonus = 15
        
        # Sitting penalty
        sit_penalty = 0
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            sit_penalty = 20
        
        # Calculate total
        flee_check = flee_roll + dex_mod + rogue_bonus + hp_bonus - attacker_penalty - sit_penalty
        
        logger.debug3(f"Flee check: roll={flee_roll} + dex={dex_mod} + rogue={rogue_bonus} + hp={hp_bonus} - attackers={attacker_penalty} - sit={sit_penalty} = {flee_check} vs {base_chance}")
        
        if flee_check < base_chance:
            # Failed to flee
            await actor.send_text(CommTypes.DYNAMIC, "You try to flee but can't get away!")
            msg = f"{actor.art_name_cap} tries to flee but fails!"
            vars = set_vars(room, actor, actor, msg)
            await room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            return
        
        # Success! Determine direction
        # 70% chance to go back the way we came if that's a valid option
        flee_direction = None
        if actor.last_entered_from and actor.last_entered_from in valid_exits:
            if random.randint(1, 100) <= 70:
                flee_direction = actor.last_entered_from
        
        # Otherwise random from valid exits
        if not flee_direction:
            flee_direction = random.choice(valid_exits)
        
        # Stop fighting - handle both the fleeing character and those fighting them
        actor.fighting_whom = None
        if actor in cls._game_state.get_characters_fighting():
            cls._game_state.remove_character_fighting(actor)
        
        # Enemies who were fighting the fleeing character should try to find new targets
        for enemy in room.get_characters():
            if enemy.fighting_whom == actor:
                enemy.fighting_whom = None
                if enemy in cls._game_state.get_characters_fighting():
                    cls._game_state.remove_character_fighting(enemy)
                # Try to find a new opponent
                await CoreActionsInterface.get_instance().fight_next_opponent(enemy)
        
        # Notify
        await actor.send_text(CommTypes.DYNAMIC, f"You flee {flee_direction}!")
        msg = f"{actor.art_name_cap} flees {flee_direction}!"
        vars = set_vars(room, actor, actor, msg, {'direction': flee_direction})
        await room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
        
        # Actually move
        await CoreActionsInterface.get_instance().world_move(actor, flee_direction)


    async def cmd_inspect(cls, actor: Actor, input: str):
        # TODO:L: fighting who / fought by?
        # TODO:H: classes
        # TODO:H: inventory
        # TODO:H: equipment
        # TODO:M: dmg resist & reduct
        # TODO:M: natural attacks
        logger = StructuredLogger(__name__, prefix="cmd_inspect()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Inspect what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_character(actor, pieces[0])
        if target == None:
            target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Inspect what?")
            return
        if isinstance(target, Character):
            await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is a level {target.total_levels()} character.")
            await actor.send_text(CommTypes.DYNAMIC, f"HP: {target.current_hit_points}/{target.max_hit_points}")
            if target.fighting_whom:
                await actor.send_text(CommTypes.DYNAMIC, f"Fighting: {target.fighting_whom.art_name}")
            if target.fought_by:
                await actor.send_text(CommTypes.DYNAMIC, f"Fought by: {target.fought_by.art_name}")
        elif isinstance(target, Object):
            await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is an object.")
            if target.damage_type:
                await actor.send_text(CommTypes.DYNAMIC, f"Damage: {target.damage_num_dice}d{target.damage_dice_size}+{target.damage_bonus} ({target.damage_type.name.lower()})")
            if target.attack_bonus:
                await actor.send_text(CommTypes.DYNAMIC, f"Attack bonus: {target.attack_bonus}")
            if target.weight:
                await actor.send_text(CommTypes.DYNAMIC, f"Weight: {target.weight}")
            if target.value:
                await actor.send_text(CommTypes.DYNAMIC, f"Value: {target.value}")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Inspect what?")

    async def cmd_inventory(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_inventory()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Determine target (self or specified character)
        if not input or input == "" or not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            target = actor
            msg = "Your inventory:"
        else:
            pieces = split_preserving_quotes(input)
            target = cls._game_state.find_target_character(actor, pieces[0])
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, "Character not found.")
                return
            msg = f"Inventory for {target.art_name_cap}:"

        await actor.send_text(CommTypes.STATIC, msg)
        
        if not target.contents:
            await actor.send_text(CommTypes.STATIC, "    Nothing.")
            return
            
        # Recursive helper function to display container contents
        async def display_container_contents(container, indent_level=0):
            indent = "    " * indent_level
            
            for item in container.contents:
                # Check if item is a container with contents
                if hasattr(item, "contents") and item.contents:
                    await actor.send_text(CommTypes.STATIC, f"{indent}{item.art_name}, containing:")
                    await display_container_contents(item, indent_level + 1)
                else:
                    await actor.send_text(CommTypes.STATIC, f"{indent}{item.art_name}")
        
        # Display top-level inventory
        await display_container_contents(target, 1)


    async def cmd_at(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_at()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_room(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        await CoreActionsInterface.get_instance().arrive_room(actor, target)

    async def cmd_get(cls, actor: Actor, input: str):
        """
        Get an item from the room or from a container.
        
        Usage:
            get <item>              - Get item from room floor
            get <item> from <container>  - Get item from a container
            get <item> <container>       - Same as above
        """
        # TODO:M: add max carry weight
        logger = StructuredLogger(__name__, prefix="cmd_get()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Get what?")
            return
        pieces = split_preserving_quotes(input)
        
        # Check for "get X from Y" syntax
        container = None
        item_keyword = pieces[0]
        
        if len(pieces) >= 3 and pieces[1].lower() == "from":
            # "get sword from chest"
            item_keyword = pieces[0]
            container_keyword = ' '.join(pieces[2:])
            container = cls._find_container(actor, container_keyword)
            if container is None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't see any '{container_keyword}' here.")
                return
        elif len(pieces) >= 2 and pieces[1].lower() != "from":
            # "get sword chest" - interpret second word as container
            item_keyword = pieces[0]
            container_keyword = ' '.join(pieces[1:])
            container = cls._find_container(actor, container_keyword)
            # If no container found, fall back to normal get (maybe they typed "get the sword")
        
        if container:
            # Get from container
            if not container.has_flags(ObjectFlags.IS_CONTAINER):
                await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is not a container.")
                return
            if container.has_flags(ObjectFlags.IS_CLOSED):
                await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is closed.")
                return
            
            # Check corpse ownership (player corpses can only be looted by their owner)
            from .nondb_models.objects import Corpse
            if isinstance(container, Corpse) and not container.can_be_looted_by(actor):
                await actor.send_text(CommTypes.DYNAMIC, f"You cannot loot {container.art_name}.")
                return
            
            # Find the item in the container
            target = None
            for obj in container.contents:
                if obj.matches_keyword(item_keyword) or obj.name.lower() == item_keyword.lower():
                    target = obj
                    break
            
            if target is None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't see that in {container.art_name}.")
                return
            
            if hasattr(target, 'has_flags') and target.has_flags(ObjectFlags.NO_TAKE):
                await actor.send_text(CommTypes.DYNAMIC, "You can't pick that up.")
                return
            
            # Fire ON_GET triggers before picking up (object executes, player is %s%/%S%)
            if TriggerType.ON_GET in target.triggers_by_type:
                get_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_GET]:
                    await trigger.run(target, target.id, get_vars, cls._game_state)
            
            container.contents.remove(target)
            actor.add_to_inventory(target)
            await actor.send_text(CommTypes.DYNAMIC, f"You get {target.art_name} from {container.art_name}.")
            
            msg = f"{actor.art_name_cap} gets {target.art_name} from {container.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
        else:
            # Get from room floor (original behavior)
            target = cls._game_state.find_target_object(item_keyword, actor)
            if target is None:
                await actor.send_text(CommTypes.DYNAMIC, "Get what?")
                return
            if target.location_room != actor.location_room:
                await actor.send_text(CommTypes.DYNAMIC, "That's not here.")
                return
            if hasattr(target, 'has_flags') and target.has_flags(ObjectFlags.NO_TAKE):
                await actor.send_text(CommTypes.DYNAMIC, "You can't pick that up.")
                return
            
            # Fire ON_GET triggers before picking up (object executes, player is %s%/%S%)
            if TriggerType.ON_GET in target.triggers_by_type:
                get_vars = set_vars(target, actor, actor, target.name)
                for trigger in target.triggers_by_type[TriggerType.ON_GET]:
                    await trigger.run(target, target.id, get_vars, cls._game_state)
            
            target.location_room.remove_object(target)
            actor.add_to_inventory(target)
            await actor.send_text(CommTypes.DYNAMIC, f"You get {target.art_name}.")
            
            msg = f"{actor.art_name_cap} picks up {target.art_name}."
            vars = set_vars(actor, actor, target, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)


    def _find_container(cls, actor: Actor, keyword: str):
        """Helper to find a container in room or inventory."""
        # Search room objects
        for obj in actor.location_room.contents:
            if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                return obj
        # Search inventory
        for obj in actor.contents:
            if obj.matches_keyword(keyword) or obj.name.lower() == keyword.lower():
                return obj
        return None


    async def cmd_put(cls, actor: Actor, input: str):
        """
        Put an item from inventory into a container.
        
        Usage:
            put <item> in <container>
            put <item> <container>
        """
        logger = StructuredLogger(__name__, prefix="cmd_put()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Put what where?")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Put what where?")
            return
        
        item_keyword = pieces[0]
        
        # Handle "put X in Y" or "put X Y"
        if pieces[1].lower() == "in" and len(pieces) >= 3:
            container_keyword = ' '.join(pieces[2:])
        else:
            container_keyword = ' '.join(pieces[1:])
        
        # Find item in inventory
        item = None
        for obj in actor.contents:
            if obj.matches_keyword(item_keyword) or obj.name.lower() == item_keyword.lower():
                item = obj
                break
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have any '{item_keyword}'.")
            return
        
        # Find container
        container = cls._find_container(actor, container_keyword)
        if container is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't see any '{container_keyword}' here.")
            return
        
        if not container.has_flags(ObjectFlags.IS_CONTAINER):
            await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is not a container.")
            return
        
        if container.has_flags(ObjectFlags.IS_CLOSED):
            await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is closed.")
            return
        
        if item == container:
            await actor.send_text(CommTypes.DYNAMIC, "You can't put something inside itself!")
            return
        
        # Move item from inventory to container
        actor.remove_from_inventory(item)
        container.contents.append(item)
        item.location_room = None  # No longer on the floor
        
        await actor.send_text(CommTypes.DYNAMIC, f"You put {item.art_name} in {container.art_name}.")
        
        msg = f"{actor.art_name_cap} puts {item.art_name} in {container.art_name}."
        vars = set_vars(actor, actor, item, msg)
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)


    async def cmd_drop(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_drop()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Drop what?")
            return
        pieces = split_preserving_quotes(input)
        
        # Search in actor's inventory
        target = None
        for obj in actor.contents:
            if obj.matches_keyword(pieces[0]) or obj.name.lower() == pieces[0].lower():
                target = obj
                break
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, "You don't have that.")
            return
        
        # Fire ON_DROP triggers before dropping (object executes, player is %s%/%S%)
        if TriggerType.ON_DROP in target.triggers_by_type:
            drop_vars = set_vars(target, actor, actor, target.name)
            for trigger in target.triggers_by_type[TriggerType.ON_DROP]:
                await trigger.run(target, target.id, drop_vars, cls._game_state)
        
        actor.remove_from_inventory(target)
        actor.location_room.add_object(target)
        await actor.send_text(CommTypes.DYNAMIC, f"You drop {target.art_name}.")
        
        msg = f"{actor.art_name_cap} drops {target.art_name}."
        vars = set_vars(actor, actor, target, msg)
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)


    async def cmd_equip(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_equip()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
        
        # Check for admin viewing another character's equipment
        if actor.has_game_flags(GamePermissionFlags.IS_ADMIN) and input:
            pieces = split_preserving_quotes(input)
            if len(pieces) > 1 and pieces[0].lower() in ["char", "character"]:
                target_name = ' '.join(pieces[1:])
                target = cls._game_state.find_target_character(actor, target_name, search_world=True)
                if target:
                    # Display target's equipment to the admin
                    await cls.cmd_equip_list(target, actor)
                    return
                else:
                    await actor.send_text(CommTypes.DYNAMIC, f"Could not find character '{target_name}'.")
                    return
                    
        # Normal equip handling
        if actor.fighting_whom != None:
            msg = "You can't equip while fighting!"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return
        if input == "":
            await cls.cmd_equip_list(actor, None)
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Equip what?")
            return
        if target.location_room != actor.location_room:
            await actor.send_text(CommTypes.DYNAMIC, "You don't have that.")
            return
        if not target.equip_locations:
            await actor.send_text(CommTypes.DYNAMIC, "You can't equip that.")
            return
        equip_location = None
        for loc in target.equip_locations:
            if actor.equipped[loc] == None:
                equip_location = loc
                break
        if equip_location == None:
            await actor.send_text(CommTypes.DYNAMIC, "There's not an open spot for it.")
            return
        target.location_room.remove_object(target)
        actor.equip_item(equip_location, target)
        await actor.send_text(CommTypes.DYNAMIC, f"You equip {target.art_name}.")


    async def cmd_unequip(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_unequip()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can unequip things.")
            return
        if actor.fighting_whom != None:
            msg = "You can't unequip while fighting!"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "Unequip what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Unequip what?")
            return
        if not target.equipped_location:
            await actor.send_text(CommTypes.DYNAMIC, "That's not equipped.")
            return
        equip_location = target.equipped_location
        actor.unequip_location(equip_location)
        actor.add_object(target)
        await actor.send_text(CommTypes.DYNAMIC, f"You unequip {target.art_name}.")


    async def cmd_equip_list(cls, actor: Actor, viewer: Actor = None):
        logger = StructuredLogger(__name__, prefix="cmd_equip_list()> ")
        logger.debug3(f"actor.rid: {actor.rid}, viewer: {viewer.rid if viewer else 'None'}")
        if actor.actor_type != ActorType.CHARACTER:
            if viewer:
                await viewer.send_text(CommTypes.DYNAMIC, "Only characters can have equipment.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
            
        # Group equipment slots for better organization
        slot_groups = {
            "Head": [EquipLocation.HEAD],
            "Body": [EquipLocation.BODY, EquipLocation.BACK],
            "Arms": [EquipLocation.ARMS, EquipLocation.HANDS, EquipLocation.WRISTS],
            "Legs": [EquipLocation.LEGS, EquipLocation.FEET],
            "Weapons": [EquipLocation.MAIN_HAND, EquipLocation.OFF_HAND, EquipLocation.BOTH_HANDS],
            "Accessories": [EquipLocation.NECK, EquipLocation.WAIST, EquipLocation.LEFT_FINGER, EquipLocation.RIGHT_FINGER, EquipLocation.EYES]
        }
        
        # Customize the message based on who's viewing
        if viewer and viewer != actor:
            # Admin viewing another character's equipment
            msg_parts = [f"=== {actor.art_name_cap}'s Equipment ===\n"]
        else:
            # Character viewing their own equipment
            msg_parts = ["=== Your Equipment ===\n"]
            
        equipped_count = 0
        
        # Display equipment by group
        for group_name, slots in slot_groups.items():
            group_items = []
            
            for loc in slots:
                if actor.equipped[loc] is not None:
                    equipped_count += 1
                    group_items.append(f"  {loc.name:<20} {actor.equipped[loc].art_name}")
                else:
                    group_items.append(f"  {loc.name:<20} nothing")
            
            if group_items:
                msg_parts.append(f"{group_name}:\n")
                msg_parts.extend([f"{item}\n" for item in group_items])
                msg_parts.append("\n")
        
        # Show summary at the end
        if equipped_count == 0:
            if viewer and viewer != actor:
                msg_parts.append(f"{actor.art_name_cap} isn't wearing or wielding anything.\n")
            else:
                msg_parts.append("You aren't wearing or wielding anything.\n")
        else:
            if viewer and viewer != actor:
                msg_parts.append(f"{actor.art_name_cap} has {equipped_count} item(s) equipped.\n")
            else:
                msg_parts.append(f"You have {equipped_count} item(s) equipped.\n")
                
        # Send to the appropriate recipient
        if viewer and viewer != actor:
            await viewer.send_text(CommTypes.STATIC, "".join(msg_parts))
        else:
            await actor.send_text(CommTypes.STATIC, "".join(msg_parts))


    async def cmd_setloglevel(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_setloglevel()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        loglevels = {
            "debug": logging.DEBUG,
            "debug1": logging.DEBUG,
            "debug2": logging.DEBUG,
            "debug3": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        pieces = input.split(' ')
        if len(pieces) < 1 or pieces[0].lower() not in loglevels:
            await actor.send_text(CommTypes.DYNAMIC, "Set log to what?")
            return
        logger.info(f"set log level to {pieces[0]}")
        logger.setLevel(loglevels[pieces[0].lower()])
        await actor.send_text(CommTypes.DYNAMIC, f"Set log level to {pieces[0]}.")


    async def cmd_setlogfilter(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_setlogfilter()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Set logfilter to what?")
            return
        if pieces[0].lower() == "all":
            logger.set_allowed_prefixes("")
            await actor.send_text(CommTypes.DYNAMIC, f"Set logfilter to all.")
            return
        elif pieces[0].lower() == "none":
            logger.set_allowed_prefixes(None)
            await actor.send_text(CommTypes.DYNAMIC, f"Set logfilter to none.")
            return
        logger.info(f"set logfilter to {','.join(pieces)}")
        logger.set_allowed_prefixes(pieces)
        await actor.send_text(CommTypes.DYNAMIC, f"Set logfilter to {','.join(pieces)}.")
        await actor.send_text(CommTypes.DYNAMIC, f"Logfilter is {','.join(logger.get_allowed_prefixes())}.")
    

    async def cmd_getlogfilter(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_getlogfilter()> ")
        await actor.send_text(CommTypes.DYNAMIC, f"Logfilter is {','.join(logger.get_allowed_prefixes())}.")


    async def cmd_delvar_helper(cls, actor: Actor, input: str, target_dict_fn: Callable[[Actor], dict], target_name: str):
        # TODO:M: add targeting objects and rooms
        logger = StructuredLogger(__name__, prefix="cmd_delvar_helper()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}, target_name: {target_name}")
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            logger.warn(f"({pieces}) Delete {target_name} var on what kind of target?")
            await actor.send_text(CommTypes.DYNAMIC, f"Delete {target_name} var on what kind of target?")
            return
        if pieces[0].lower() != "char":
            logger.warn(f"({pieces}) Only character targets allowed at the moment.")
            await actor.send_text(CommTypes.DYNAMIC, "Only character targets allowed at the moment.")
            return
        if len(pieces) < 2:
            logger.warn(f"({pieces}) Delete {target_name} var on whom?")
            await actor.send_text(CommTypes.DYNAMIC, f"Delete {target_name} var on whom?")
            return
        if len(pieces) < 3:
            logger.warn(f"({pieces}) Delete which {target_name} var?")
            await actor.send_text(CommTypes.DYNAMIC, "Delete which temp var?")
            return
        target = cls._game_state.find_target_character(actor, pieces[1], search_world=True)
        if target == None:
            logger.warn(f"({pieces}) Could not find target.")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
            return
        logger.debug3(f"target.name: {target.name}, {target_name} delete var: {pieces[2]}")
        del target_dict_fn(target)[pieces[2]]
        await actor.send_text(CommTypes.DYNAMIC, f"Deleted {target_name} var {pieces[2]} on {target.name}")


    async def cmd_deltempvar(cls, actor: Actor, input: str):
        await cls.cmd_delvar_helper(actor, input, lambda d : d.temp_variables, "temp")

    async def cmd_delpermvar(cls, actor: Actor, input: str):
        await cls.cmd_delvar_helper(actor, input, lambda d : d.perm_variables, "perm")

    async def cmd_stand(cls, actor: Actor, input: str):
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can stand.")
            return
        if not actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not actor.is_meditating:
            await actor.send_text(CommTypes.DYNAMIC, "You're already standing.")
            return
        
        if any(actor.get_character_states_by_type(CharacterStateForcedSitting))\
               or any(actor.get_character_states_by_type(CharacterStateForcedSleeping)):
            msg = f"You can't stand up right now."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), game_state=cls._game_state)
            return

        # Stop meditating when standing
        actor.is_meditating = False
        
        await actor.send_text(CommTypes.DYNAMIC, "You stand up.")
        msg = f"{firstcap(actor.name)} stands up."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING | TemporaryCharacterFlags.IS_SITTING)
    
    async def cmd_sit(cls, actor: Actor, input: str):
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can sit.")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            await actor.send_text(CommTypes.DYNAMIC, "You're already sitting.")
            return
        if any(actor.get_character_states_by_type(CharacterStateForcedSleeping)):
            msg = f"You can't sit down right now."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), game_state=cls._game_state)
            return
        if actor.fighting_whom is not None:
            await actor.send_text(CommTypes.DYNAMIC, "You can't sit down while fighting!")
            return
            
        # Stop meditating if sitting/standing
        actor.is_meditating = False
        
        await actor.send_text(CommTypes.DYNAMIC, "You sit down.")
        msg = f"{firstcap(actor.name)} sits down."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)
        actor.set_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        

    async def cmd_sleep(cls, actor: Actor, input: str):
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can sleep.")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.DYNAMIC, "You're already sleeping.")
            return
        if actor.fighting_whom is not None:
            await actor.send_text(CommTypes.DYNAMIC, "You can't sleep while fighting!")
            return
        
        # Stop meditating when sleeping
        actor.is_meditating = False
            
        await actor.send_text(CommTypes.DYNAMIC, "You doze off.")
        msg = f"{firstcap(actor.name)} falls asleep."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        actor.set_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)


    async def cmd_meditate(cls, actor: Actor, input: str):
        """
        Enter a meditative state for faster mana regeneration.
        Requires sitting or standing still (not fighting).
        """
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can meditate.")
            return
        if actor.is_meditating:
            await actor.send_text(CommTypes.DYNAMIC, "You're already meditating.")
            return
        if actor.fighting_whom is not None:
            await actor.send_text(CommTypes.DYNAMIC, "You can't meditate while fighting!")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.DYNAMIC, "You can't meditate while sleeping!")
            return
        
        # Check if character has any mana pool (Mage/Cleric levels)
        if actor.max_mana <= 0:
            await actor.send_text(CommTypes.DYNAMIC, "You have no magical abilities to focus on.")
            return
        
        actor.is_meditating = True
        
        await actor.send_text(CommTypes.DYNAMIC, "You close your eyes and begin to meditate, focusing your mind on the magical energies around you.")
        msg = f"{firstcap(actor.name)} closes their eyes and begins to meditate."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)


    async def cmd_leaverandom(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_leaverandom()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if (actor.fighting_whom != None):
            await actor.send_text(CommTypes.DYNAMIC, "You can't leave while fighting!")
            return
        
        # Check if the actor wants to stay in the current zone
        stay_in_zone = False
        if input and input.strip().lower() == "stayinzone":
            stay_in_zone = True
            
        # Get valid exits
        if actor.location_room is None:
            await actor.send_text(CommTypes.DYNAMIC, "You are not in a room.")
            return
        else:
            valid_directions = list(actor.location_room.exits.keys())
            
        # Filter exits if staying in zone
        if stay_in_zone:
            filtered_directions = []
            current_zone = actor.location_room.zone.id
            
            for direction in valid_directions:
                exit_obj = actor.location_room.exits[direction]
                destination = exit_obj.destination  # Exit object has .destination property
                # Check if destination is in the same zone
                if "." in destination:
                    zone_id, _ = destination.split(".")
                    if zone_id == current_zone:
                        filtered_directions.append(direction)
                else:
                    # If no zone specified, it's in the current zone
                    filtered_directions.append(direction)
                    
            valid_directions = filtered_directions
            
        logger.debug3("valid_exits: " + str(valid_directions))
        num_exits = len(valid_directions)
        if num_exits == 0:
            if stay_in_zone:
                await actor.send_text(CommTypes.DYNAMIC, "There are no exits that stay in the current zone.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, "There are no exits here.")
            return
            
        exit_num = random.randint(0, num_exits - 1)
        msg = f"You randomly decide to go {valid_directions[exit_num]}."
        logger.debug3("msg: " + msg)
        vars = set_vars(actor, actor, None, msg)
        await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        await CoreActionsInterface.get_instance().world_move(actor, valid_directions[exit_num])
        
    async def cmd_save(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_save()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can save games.")
            return
            
        # TODO: In final version, players will only get one save slot
        # For now, allow named saves for testing purposes
        save_name = input.strip() if input.strip() else "default"
        
        # Save the game state
        success = cls._game_state.save_game_state(actor.name, save_name)
        
        if success:
            await actor.send_text(CommTypes.DYNAMIC, f"Game saved as '{save_name}'.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Failed to save game as '{save_name}'.")
    
    async def cmd_load(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_load()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can load games.")
            return
            
        # TODO: In final version, players will only get one save slot
        # For now, allow named saves for testing purposes
        if not input.strip():
            await actor.send_text(CommTypes.DYNAMIC, "Load which save? Use 'saves' command to list available saves.")
            return
            
        save_name = input.strip()
        
        # Load the game state
        success = cls._game_state.load_game_state(actor.name, save_name)
        
        if success:
            await actor.send_text(CommTypes.DYNAMIC, f"Game '{save_name}' loaded successfully.")
            # Refresh the player's view of their current location
            await CoreActionsInterface.get_instance().do_look_room(actor, actor._location_room)
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Failed to load game '{save_name}'. Save not found or error occurred.")
    
    async def cmd_saves(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_saves()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can list saves.")
            return
            
        # Get list of saves
        saves_list = cls._game_state.list_game_saves(actor.name)
        
        if not saves_list:
            await actor.send_text(CommTypes.DYNAMIC, "You don't have any saved games.")
            return
            
        # Format the output
        msg_parts = ["Your saved games:\n"]
        for i, (save_name, timestamp) in enumerate(saves_list, 1):
            msg_parts.append(f"{i}. {save_name} - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
        await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
    
    async def cmd_deletesave(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_deletesave()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can delete saves.")
            return
            
        if not input.strip():
            await actor.send_text(CommTypes.DYNAMIC, "Delete which save? Use 'saves' command to list available saves.")
            return
            
        save_name = input.strip()
        
        # Delete the save
        success = cls._game_state.delete_game_save(actor.name, save_name)
        
        if success:
            await actor.send_text(CommTypes.DYNAMIC, f"Save '{save_name}' deleted.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Failed to delete save '{save_name}'. Save not found.")

    async def cmd_quit(cls, actor: Actor, input: str):
        """Handle the quit/logout command - save character and disconnect."""
        logger = StructuredLogger(__name__, prefix="cmd_quit()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can quit.")
            return
        
        # Check if in combat
        if actor.fighting_whom is not None:
            await actor.send_text(CommTypes.DYNAMIC, "You cannot quit while in combat!")
            return
        
        await actor.send_text(CommTypes.DYNAMIC, "Saving your character...")
        
        # Save using the new YAML-based system
        from .player_save_manager import player_save_manager
        from .constants import Constants
        
        success = player_save_manager.save_character(
            actor,
            save_states=Constants.SAVE_CHARACTER_STATES,
            save_cooldowns=Constants.SAVE_CHARACTER_COOLDOWNS
        )
        
        if success:
            await actor.send_text(CommTypes.DYNAMIC, "Character saved. Goodbye!")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Warning: Failed to save character, but logging out anyway. Goodbye!")
        
        # Remove from combat tracking if somehow still there
        if actor in cls._game_state.characters_fighting:
            cls._game_state.characters_fighting.remove(actor)
        
        # Notify room
        if actor.location_room:
            msg = f"{actor.art_name_cap} has left the game."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[actor], game_state=cls._game_state)
            actor.location_room.remove_character(actor)
            actor.location_room = None
        
        # Remove from players list
        if actor in cls._game_state.players:
            cls._game_state.players.remove(actor)
        
        # Clear connection
        if actor.connection:
            connection = actor.connection
            actor.connection = None
            if connection in cls._game_state.connections:
                cls._game_state.connections.remove(connection)
            # Close the websocket
            if hasattr(connection, 'consumer_') and connection.consumer_:
                try:
                    await connection.consumer_.close()
                except Exception as e:
                    logger.debug3(f"Error closing websocket: {e}")
        
        logger.info(f"Player {actor.name} quit the game")

    async def cmd_savegame(cls, actor: Actor, input: str):
        """Handle the savegame command - manually save character to YAML file."""
        logger = StructuredLogger(__name__, prefix="cmd_savegame()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can save.")
            return
        
        from .player_save_manager import player_save_manager
        from .constants import Constants
        
        success = player_save_manager.save_character(
            actor,
            save_states=Constants.SAVE_CHARACTER_STATES,
            save_cooldowns=Constants.SAVE_CHARACTER_COOLDOWNS
        )
        
        if success:
            await actor.send_text(CommTypes.DYNAMIC, "Character saved.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Failed to save character.")

    async def cmd_command(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_command()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor has admin permissions
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to force commands.")
            return
            
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Command whom to do what?")
            return
            
        # Split input into target and command
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Command whom to do what?")
            return
            
        # Find the target character
        target = cls._game_state.find_target_character(actor, pieces[0])
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Could not find that character.")
            return
            
        # Get the command to execute
        command = ' '.join(pieces[1:])
        
        # Notify the actor
        await actor.send_text(CommTypes.DYNAMIC, f"Forcing {target.art_name} to: {command}")
        
        # Execute the command for the target
        await cls.process_command(target, command)

    async def cmd_stop(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_stop()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.command_queue:
            num_commands = len(actor.command_queue)
            actor.command_queue.clear()
            await actor.send_text(CommTypes.DYNAMIC, f"Stopped {num_commands} queued command(s).")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "You have no queued commands to stop.")

    def find_path(cls, start_room: Room, target_room: Room) -> List[str]:
        """Find the shortest path between two rooms using breadth-first search."""
        if start_room == target_room:
            return []
            
        # Keep track of visited rooms and their parent rooms
        visited = {start_room: None}
        queue = [start_room]
        
        while queue:
            current = queue.pop(0)
            
            # Check all exits from current room
            for direction, dest_id in current.exits.items():
                if "." in dest_id:
                    zone_id, room_id = dest_id.split(".")
                else:
                    zone_id = current.zone.id
                    room_id = dest_id
                    
                next_room = cls._game_state.get_zone_by_id(zone_id).rooms[room_id]
                
                if next_room == target_room:
                    # Found the target, reconstruct the path
                    path = [direction]
                    while current != start_room:
                        # Find the direction that led to current room
                        for dir, room_id in visited[current].exits.items():
                            if "." in room_id:
                                z_id, r_id = room_id.split(".")
                            else:
                                z_id = visited[current].zone.id
                                r_id = room_id
                            if cls._game_state.get_zone_by_id(z_id).rooms[r_id] == current:
                                path.append(dir)
                                break
                        current = visited[current]
                    return list(reversed(path))
                    
                if next_room not in visited:
                    visited[next_room] = current
                    queue.append(next_room)
        
        return None  # No path found

    async def cmd_walkto(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_walkto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Walk to what?")
            return
            
        # Try to find target in order: characters, objects, rooms
        target = cls._game_state.find_target_character(actor, input, search_world=True)
        if not target:
            target = cls._game_state.find_target_object(input, actor, search_world=True)
        if not target:
            target = cls._game_state.find_target_room(actor, input, actor.location_room.zone)
            
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Could not find that target.")
            return
            
        # Get the target's room
        target_room = target.location_room if hasattr(target, 'location_room') else target
        
        # Find path to target
        path = cls.find_path(actor.location_room, target_room)
        if not path:
            await actor.send_text(CommTypes.DYNAMIC, "You can't find a path to that target.")
            return
            
        # Queue the movement commands
        for direction in path:
            actor.command_queue.append(direction)
            
        await actor.send_text(CommTypes.DYNAMIC, f"Queued {len(path)} movement command(s) to reach {target.art_name}.")

    async def cmd_delay(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_delay()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Delay for how many milliseconds?")
            return
            
        try:
            delay_ms = int(input)
            if delay_ms < 0:
                await actor.send_text(CommTypes.DYNAMIC, "Delay must be a positive number.")
                return
        except ValueError:
            await actor.send_text(CommTypes.DYNAMIC, "Please specify a valid number of milliseconds.")
            return
            
        # Convert milliseconds to ticks using Constants.GAME_TICK_SEC
        tick_ms = int(Constants.GAME_TICK_SEC * 1000)  # Convert seconds to milliseconds
        rounded_ms = round(delay_ms / tick_ms) * tick_ms
        delay_ticks = max(1, rounded_ms // tick_ms)
        
        # Create and start a cooldown that doesn't make the actor busy
        delay_cooldown = Cooldown(actor, "delay", cls._game_state, cooldown_source=actor, 
                                 cooldown_vars=None, cooldown_end_fn=lambda: None)
        delay_cooldown.start(cls._game_state.current_tick, 0, 
                           cls._game_state.current_tick + delay_ticks)
        
        if rounded_ms != delay_ms:
            await actor.send_text(CommTypes.DYNAMIC, f"Delaying for {rounded_ms} milliseconds (rounded from {delay_ms}ms).")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Delaying for {delay_ms} milliseconds.")

    async def cmd_skills(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_skills()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if input and input != "":
            if actor.actor_type != ActorType.CHARACTER:
                await actor.send_text(CommTypes.DYNAMIC, "Only characters have skills.")
                return
            target = actor
        else:
            pieces = split_preserving_quotes(input)
            target = cls._game_state.find_target_character(actor, pieces[0])
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, "No target found.")
                return
        for skill_name, skill_level in target.skill_levels.items():
            await actor.send_text(CommTypes.DYNAMIC, f"{skill_name}: {skill_level}")

    async def cmd_character(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_character()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Determine target (self or specified character)
        if not input or input == "" or not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            target = actor
        else:
            pieces = split_preserving_quotes(input)
            target = cls._game_state.find_target_character(actor, pieces[0])
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, "Character not found.")
                return
        
        # Check if viewer has admin privileges
        is_admin = actor.has_game_flags(GamePermissionFlags.IS_ADMIN)
        
        # Build character info display
        await actor.send_text(CommTypes.STATIC, f"===== {target.art_name_cap} =====")
        
        # Basic info
        level_info = f"Level {target.total_levels()}"
        await actor.send_text(CommTypes.STATIC, f"{level_info}")
        
        # HP and status
        hp_percent = int((target.current_hit_points / target.max_hit_points) * 100) if target.max_hit_points > 0 else 0
        await actor.send_text(CommTypes.STATIC, f"HP: {target.current_hit_points}/{target.max_hit_points} ({hp_percent}%)")
        
        # Mana (if any)
        if target.max_mana > 0:
            mana_percent = int((target.current_mana / target.max_mana) * 100) if target.max_mana > 0 else 0
            await actor.send_text(CommTypes.STATIC, f"Mana: {int(target.current_mana)}/{target.max_mana} ({mana_percent}%)")
        
        # Stamina (if any)
        if target.max_stamina > 0:
            stamina_percent = int((target.current_stamina / target.max_stamina) * 100) if target.max_stamina > 0 else 0
            await actor.send_text(CommTypes.STATIC, f"Stamina: {int(target.current_stamina)}/{target.max_stamina} ({stamina_percent}%)")
        
        # Status indicators
        if target.is_dead():
            await actor.send_text(CommTypes.STATIC, "Status: DEAD")
        elif target.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.STATIC, "Status: Sleeping")
        elif target.is_meditating:
            await actor.send_text(CommTypes.STATIC, "Status: Meditating")
        elif target.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            await actor.send_text(CommTypes.STATIC, "Status: Sitting")
        elif target.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
            await actor.send_text(CommTypes.STATIC, "Status: Stunned")
        elif target.fighting_whom:
            await actor.send_text(CommTypes.STATIC, f"Status: Fighting {target.fighting_whom.art_name}")
        else:
            await actor.send_text(CommTypes.STATIC, "Status: Standing")
        
        # Display equipped items
        await actor.send_text(CommTypes.STATIC, "\n--- Equipment ---")
        has_equipment = False
        for loc in EquipLocation:
            if target.equipped[loc]:
                has_equipment = True
                await actor.send_text(CommTypes.STATIC, f"{loc.name}: {target.equipped[loc].art_name}")
        if not has_equipment:
            await actor.send_text(CommTypes.STATIC, "Nothing equipped")
        
        # Display skills
        await actor.send_text(CommTypes.STATIC, "\n--- Skills ---")
        if not target.skill_levels:
            await actor.send_text(CommTypes.STATIC, "No skills")
        else:
            for skill_name, skill_level in target.skill_levels.items():
                await actor.send_text(CommTypes.STATIC, f"    {skill_name:30}: {skill_level:>2}")
        
        # Admin-only information
        if is_admin:
            await actor.send_text(CommTypes.STATIC, "\n--- Admin Info ---")
            await actor.send_text(CommTypes.STATIC, f"Reference ID: {target.rid}")
            await actor.send_text(CommTypes.STATIC, f"Location: {target.location_room.id if target.location_room else 'None'}")
            
            # Flags display
            perm_flags = [f.name for f in PermanentCharacterFlags if target.has_perm_flags(f)]
            temp_flags = [f.name for f in TemporaryCharacterFlags if target.has_temp_flags(f)]
            game_flags = [f.name for f in GamePermissionFlags if target.has_game_flags(f)]
            
            if perm_flags:
                await actor.send_text(CommTypes.STATIC, f"Permanent Flags: {', '.join(perm_flags)}")
            if temp_flags:
                await actor.send_text(CommTypes.STATIC, f"Temporary Flags: {', '.join(temp_flags)}")
            if game_flags:
                await actor.send_text(CommTypes.STATIC, f"Permission Flags: {', '.join(game_flags)}")
            
            # Variables
            if target.temp_variables:
                await actor.send_text(CommTypes.STATIC, "Temp Variables:")
                for key, value in target.temp_variables.items():
                    await actor.send_text(CommTypes.STATIC, f"  {key}: {value}")
            
            if target.perm_variables:
                await actor.send_text(CommTypes.STATIC, "Perm Variables:")
                for key, value in target.perm_variables.items():
                    await actor.send_text(CommTypes.STATIC, f"  {key}: {value}")


    async def cmd_triggers(cls, actor: Actor, input: str):
        # triggers <character|room|object> <name|me|here> <enable|disable|show|list> [<all|trigger_id>]
        
        async def list_triggers(actor: Actor, target: Character | Room | Object, target_triggers: list[Trigger]):
            if actor == target:
                await actor.send_text(CommTypes.STATIC, f"Your triggers:")
            else:
                await actor.send_text(CommTypes.STATIC, f"Triggers for {target.art_name_cap}:")
            if not target_triggers:
                 await actor.send_text(CommTypes.STATIC, "  None found.")
                 return
                 
            for trigger in target_triggers:
                state = "(disabled)" if trigger.disabled_ else ""
                await actor.send_text(CommTypes.STATIC, f"  ID: {trigger.id:<25} Type: {trigger.trigger_type_:<15} {state}")
                if trigger.criteria_:
                     # await actor.send_text(CommTypes.STATIC, "    Criteria:")
                     for crit in trigger.criteria_:
                         count = 0
                         await actor.send_text(CommTypes.STATIC, f"      Crit #{count}: {crit.subject} {crit.operator} {crit.predicate}")
                         count += 1
        
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "What?")
            return
        
        pieces = split_preserving_quotes(input)
        
        # Handle case with no arguments (list all global triggers)
        if not pieces:
            pieces.append("char")
            pieces.append("me")
            pieces.append("list")
            
        elif pieces[0] == "me" and len(pieces) == 1:
            pieces.insert(0, "char")
            pieces.append("list")
            
        elif (pieces[0].lower() != "me" or pieces[1].lower() != "list") and len(pieces) < 3:
            await actor.send_text(CommTypes.STATIC, "Usage: triggers <target_type> <target_name> <action> [trigger_specifier]")
            await actor.send_text(CommTypes.STATIC, "  Target Types: character, char, me, self, room, here, obj, object")
            await actor.send_text(CommTypes.STATIC, "  Actions: enable, disable, show, list")
            await actor.send_text(CommTypes.STATIC, "  Trigger Specifier (needed for enable/disable/show): all | <trigger_id>")
            return
            
        target_type = pieces[0].lower()
        target_name = pieces[1]
        action = pieces[2].lower()
        
        # Validate target type
        if target_type not in ["character", "char", "me", "self", "room", "here", "obj", "object"]:
            await actor.send_text(CommTypes.STATIC, "Invalid target type. Use: character, char, me, self, room, here, obj, object")
            return
            
        # Validate action
        valid_actions = ["enable", "disable", "show", "list"]
        if action not in valid_actions:
            await actor.send_text(CommTypes.STATIC, f"Invalid action. Use: {', '.join(valid_actions)}")
            return

        # Find the target
        target = None
        if target_type in ["character", "char", "me", "self"]:
            if target_type in ["me", "self"]:
                if len(pieces) > 2: # 'me'/'self' replaces target_name, shift other args
                   action = pieces[1].lower()
                   target_name = "me" # Set target_name for display purposes
                   if action not in valid_actions:
                       await actor.send_text(CommTypes.STATIC, f"Invalid action. Use: {', '.join(valid_actions)}")
                       return
                   if len(pieces) > 3:
                       trigger_specifier = pieces[2] # Adjusted index
                   elif action in ["enable", "disable", "show"]:
                       await actor.send_text(CommTypes.STATIC, f"Action '{action}' requires a trigger specifier (all or ID).")
                       return
                else:
                   await actor.send_text(CommTypes.STATIC, "Please specify an action (enable, disable, show, list).")
                   return
                target = actor
            else:
                target = cls._game_state.find_target_character(actor, target_name)
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Character '{target_name}' not found.")
                return
        elif target_type in ["room", "here"]:
            if target_type == "here":
                if len(pieces) > 2: # 'here' replaces target_name, shift other args
                    action = pieces[1].lower()
                    target_name = "here" # Set target_name for display purposes
                    if action not in valid_actions:
                        await actor.send_text(CommTypes.STATIC, f"Invalid action. Use: {', '.join(valid_actions)}")
                        return
                    if len(pieces) > 3:
                         trigger_specifier = pieces[2] # Adjusted index
                    elif action in ["enable", "disable", "show"]:
                         await actor.send_text(CommTypes.STATIC, f"Action '{action}' requires a trigger specifier (all or ID).")
                         return
                else:
                    await actor.send_text(CommTypes.STATIC, "Please specify an action (enable, disable, show, list).")
                    return
                target = actor.location_room
                if not target:
                     await actor.send_text(CommTypes.STATIC, "You are not in a room.")
                     return
            else:
                target = cls._game_state.find_target_room(actor, target_name)
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Room '{target_name}' not found.")
                return
        elif target_type in ["obj", "object"]:
            target = cls._game_state.find_target_object(actor, target_name, search_world=True) # Search world for objects too
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Object '{target_name}' not found.")
                return
                
        # --- Handle actions ---
        
        # Get the triggers attached to the target
        target_triggers = list(itertools.chain.from_iterable(target.triggers_by_type.values()))

        if action == "list":
            # List action requires exactly 3 arguments (or 2 for me/here)
            expected_len = 2 if target_type in ["me", "self", "here"] else 3
            if len(pieces) != expected_len:
                 await actor.send_text(CommTypes.STATIC, f"Usage: triggers {target_type} {target_name} list")
                 return
             
            await list_triggers(actor, target, target_triggers)

            return
        expected_len = 3 if target_type in ["me", "self", "here"] else 4
        if len(pieces) < expected_len:
             await actor.send_text(CommTypes.STATIC, f"Action '{action}' requires a trigger specifier (all or ID).")
             await actor.send_text(CommTypes.STATIC, f"Usage: triggers {target_type} {target_name} {action} <all|trigger_id>")
             return
             
        trigger_specifier = pieces[expected_len-1] # Get specifier based on adjusted index

        if trigger_specifier == "all":
            triggers_to_modify = target_triggers
            if not triggers_to_modify and action != "show": # 'show all' doesn't make sense
                 await actor.send_text(CommTypes.STATIC, f"Target {target.art_name_cap} has no triggers to {action}.")
                 return
        else:
            triggers_to_modify = [trigger for trigger in target_triggers if trigger.id == trigger_specifier]
            if not triggers_to_modify:
                await actor.send_text(CommTypes.STATIC, f"Target {target.art_name_cap} does not have a trigger with ID '{trigger_specifier}'.")
                return

        if action == "enable":
            for trigger in triggers_to_modify:
                trigger.enable()
                await actor.send_text(CommTypes.STATIC, f"Enabled trigger '{trigger.id}' on {target.art_name_cap}.")
            return
        elif action == "disable":
            for trigger in triggers_to_modify:
                trigger.disable()
                await actor.send_text(CommTypes.STATIC, f"Disabled trigger '{trigger.id}' on {target.art_name_cap}.")
            return
        elif action == "show":
            if trigger_specifier == "all":
                 await actor.send_text(CommTypes.STATIC, "Cannot use 'show all'. Please specify a single trigger ID to show.")
                 return
            if len(triggers_to_modify) != 1: # Should be redundant due to find logic, but safe check
                await actor.send_text(CommTypes.STATIC, "Error: Found multiple triggers matching ID (this shouldn't happen).")
                return
                
            trigger = triggers_to_modify[0]
            await actor.send_text(CommTypes.STATIC, f"Trigger '{trigger.id}' on {target.art_name_cap}:")
            await actor.send_text(CommTypes.STATIC, f"  Type: {trigger.trigger_type_}")
            await actor.send_text(CommTypes.STATIC, f"  Disabled: {trigger.disabled_}")
            await actor.send_text(CommTypes.STATIC, "  Criteria:")
            if not trigger.criteria_:
                 await actor.send_text(CommTypes.STATIC, "    None")
            else:
                for crit in trigger.criteria_:
                    await actor.send_text(CommTypes.STATIC, f"    {crit.subject} {crit.operator} {crit.predicate}")
            await actor.send_text(CommTypes.STATIC, "  Script:")
            script_lines = trigger.script_.split("\n")
            if not trigger.script_ or not script_lines or (len(script_lines) == 1 and not script_lines[0].strip()):
                 await actor.send_text(CommTypes.STATIC, "    (Empty)")
            else:
                for line in script_lines:
                     await actor.send_text(CommTypes.STATIC, f"    {line}")
            return
            
        # Fallback error - should not be reached if action validation is correct
        await actor.send_text(CommTypes.STATIC, "An unexpected error occurred processing the command.")
        return
