import asyncio
from .structured_logger import StructuredLogger, set_current_actor, clear_current_actor, flush_admin_log_queue
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
from .nondb_models.character_interface import CharacterInterface, CharacterAttributes, \
    EquipLocation, PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags
from .nondb_models.object_interface import ObjectInterface, ObjectFlags
from .nondb_models.objects import Object
from .nondb_models.room_interface import RoomInterface
from .nondb_models.triggers import TriggerType, Trigger, TriggerOnSignal
from .nondb_models import world
from .utility import replace_vars, firstcap, set_vars, split_preserving_quotes, article_plus_name, normalize_var_value
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

    # Commands that cannot be executed via the "command" command (privileged/script-only)
    privileged_commands = {
        "show", "echo", "echoto", "echoexcept", "settempvar", "setpermvar", "spawn",
        "makeadmin", "possess", "goto", "list", "at", "setloglevel", "setlogfilter",
        "getlogfilter", "deltempvar", "delpermvar", "showvars", "save", "load", "saves", "deletesave",
        "stop", "walkto", "route", "delay", "setquestvar", "getquestvar", "spawnobj",
        "pause", "damage", "heal", "removeitem", "transfer", "force", "command",
        "interrupt", "teleport", "reload", "setstat", "getstat", "signal", "deregistersignals", "_trigger_start", "_trigger_end",
        "showscripts", "debug", "applystate", "where"
    }

    # Instant commands - these don't take any time and immediately process the next queued command
    # Useful for internal commands that shouldn't delay script execution
    instant_commands = {
        "_trigger_start", "_trigger_end",
        "settempvar", "setpermvar", "deltempvar", "delpermvar", "showvars",
        "setquestvar", "getquestvar", "setstat", "getstat", "signal", "deregistersignals"
    }

    # Commands whose argument text should keep user capitalization (say, whisper, echo, emotes, etc.)
    # Commands whose args must not be lowercased (e.g. contain refs like |C455 or quoted text)
    PRESERVE_CAPITALIZATION_COMMANDS = frozenset({
        "say", "whisper", "sayto", "ask", "echo", "echoto", "echoexcept", "emote",
        "setquestvar", "getquestvar", "signal",
    })

    # Debug sections toggleable via "debug <name>" / "debug -<name>". name must be in this list.
    DEBUG_SECTIONS = [
        {"name": "object_commands", "description": "Emits all object-executed commands to the debug log."},
        {"name": "setquestvar", "description": "Emits detailed setquestvar flow to the log (target, resolved key, perm_variables)."},
        {"name": "give", "description": "Emits detailed give command flow (actor type, zone, target, object lookup, etc.)."},
        {"name": "trigger_run", "description": "Log trigger execution (run/script/criteria) only for triggers on actors in your room."},
        {"name": "npc_commands", "description": "Log commands issued by NPCs only when the NPC is in your room."},
    ]

    @classmethod
    def is_instant_command(cls, command_str: str) -> bool:
        """
        Check if a command is an instant command that doesn't take any game time.
        
        Instant commands don't delay processing of the next queued command.
        """
        if not command_str:
            return False
        first_word = command_str.strip().split()[0].lower() if command_str.strip() else ""
        return first_word in cls.instant_commands
    
    @classmethod
    async def process_command_queue(cls, actor: Actor, game_state: 'ComprehensiveGameState') -> bool:
        """
        Process commands from an actor's queue, handling instant commands.
        
        After executing any command, peeks at the next command in queue.
        If the next command is instant, executes it immediately without waiting
        for a game tick. Continues until queue is empty or next command is non-instant.
        
        Returns:
            bool: True if any command was processed, False if queue was empty
        """
        if not actor.command_queue:
            return False
        
        while actor.command_queue:
            # Pop and execute current command
            current_command = actor.command_queue.pop(0)
            
            try:
                await cls.process_command(actor, current_command)
            except Exception as e:
                logger = StructuredLogger(__name__, prefix="process_command_queue()> ")
                logger.error(f"Error processing queued command for {actor.rid}: {e}")
            
            # Peek at next command - if it's instant, continue immediately
            if actor.command_queue:
                next_command = actor.command_queue[0]  # Peek, don't pop
                if cls.is_instant_command(next_command):
                    continue  # Next command is instant, process it now
            
            # Next command is not instant (or queue empty), stop and wait for next tick
            break
        
        return True

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
        "showvars": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_showvars(char, input),
        "save": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_save(char, input),
        "load": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_load(char, input),
        "saves": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_saves(char, input),
        "deletesave": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_deletesave(char, input),
        "debug": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_debug(char, input),
        "stop": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stop(char, input),
        "walkto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_walkto(char, input),
        "route": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_route(char, input),
        "delay": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_delay(char, input),
        "setquestvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setquestvar(char, input),
        "getquestvar": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_getquestvar(char, input),
        "quests": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quests(char, input),
        "spawnobj": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_spawnobj(char, input),
        "pause": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_pause(char, input),
        "damage": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_damage(char, input),
        "heal": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_heal(char, input),
        "applystate": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_applystate(char, input),
        "setstat": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_setstat(char, input),
        "getstat": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_getstat(char, input),
        "removeitem": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_removeitem(char, input),
        "transfer": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_transfer(char, input),
        "force": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_force(char, input),
        "command": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_command(char, input),
        "interrupt": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_interrupt(char, input),
        "teleport": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_teleport(char, input),
        "reload": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_reload(char, input),
        "_trigger_start": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_trigger_start(char, input),
        "_trigger_end": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_trigger_end(char, input),

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
        "go": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_go(char, input),
        "enter": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_go(char, input),
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
        "read": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_read(char, input),
        "examine": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "ex": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "inspect": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inspect(char, input),
        "equip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "eq": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "unequip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_unequip(char, input),
        "stand": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stand(char, input),
        "sit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sit(char, input),
        "rest": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_rest(char, input),
        "sleep": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sleep(char, input),
        "meditate": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_meditate(char, input),
        "med": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_meditate(char, input),
        "flee": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_flee(char, input),
        "leaverandom": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_leaverandom(char, input),
        "skills": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_skills(char, input),
        "level": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_level(char, input),
        "levelup": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_levelup(char, input),
        "skillup": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_skillup(char, input),
        "improvestat": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_improvestat(char, input),
        "character": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "char": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "self": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_self(char, input),
        "status": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_status(char, input),
        "where": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_where(char, input),
        "triggers": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_triggers(char, input),
        "showscripts": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_showscripts(char, input),
        "quit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quit(char, input),
        "logout": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_quit(char, input),
        "savegame": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_savegame(char, input),
        "commands": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_commands(char, input),
        "signal": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_signal(char, input),
        "deregistersignals": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_deregistersignals(char, input),
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

    CARDINAL_ALIASES = {
        'n': 'north', 'north': 'north',
        's': 'south', 'south': 'south',
        'e': 'east', 'east': 'east',
        'w': 'west', 'west': 'west',
        'u': 'up', 'up': 'up',
        'd': 'down', 'down': 'down',
    }

    @classmethod
    async def cmd_go(cls, actor: Actor, input: str):
        """Handle 'go <keyword>' and 'enter <keyword>' for non-cardinal exits."""
        if not input or not input.strip():
            await actor.send_text(CommTypes.DYNAMIC, "Go where?")
            return

        keyword = input.strip().lower()

        # If it's a cardinal direction, just delegate to normal movement
        if keyword in cls.CARDINAL_ALIASES:
            await cls.handle_movement("go", actor, cls.CARDINAL_ALIASES[keyword])
            return

        # Fire CATCH_GO triggers on the room -- script can intercept and handle
        room = actor.location_room
        if TriggerType.CATCH_GO in room.triggers_by_type:
            go_vars = set_vars(room, actor, actor, keyword)
            for trigger in room.triggers_by_type[TriggerType.CATCH_GO]:
                if await trigger.run(actor, keyword, go_vars, cls._game_state):
                    return

        # Check room exits for the keyword
        if keyword in room.exits:
            await cls.handle_movement("go", actor, keyword)
            return

        await actor.send_text(CommTypes.DYNAMIC, "You can't go that way.")

    @classmethod
    async def _try_catch_command_triggers(cls, actor: Actor, command_lower: str, full_input: str) -> bool:
        """
        Check room, room objects, room NPCs, and each character's top-level inventory
        for catch_command triggers. If the command word matches a trigger's list, run it.
        Returns True if a trigger ran (command processing should stop), False otherwise.
        """
        room = getattr(actor, "location_room", None)
        if room is None:
            return False
        # Convention: actor = trigger owner, subject = command issuer; target is nothing.
        def catch_vars(owner):
            return set_vars(owner, actor, None, full_input, {"text": full_input})
        # Room
        if TriggerType.CATCH_COMMAND in room.triggers_by_type:
            for trigger in room.triggers_by_type[TriggerType.CATCH_COMMAND]:
                if await trigger.run(actor, command_lower, catch_vars(room), cls._game_state):
                    return True
        # Objects in room
        for obj in list(room.contents):
            if TriggerType.CATCH_COMMAND in obj.triggers_by_type:
                for trigger in obj.triggers_by_type[TriggerType.CATCH_COMMAND]:
                    if await trigger.run(actor, command_lower, catch_vars(obj), cls._game_state):
                        return True
        # Characters in room (NPCs and PC)
        for char in list(room.characters):
            if TriggerType.CATCH_COMMAND in char.triggers_by_type:
                for trigger in char.triggers_by_type[TriggerType.CATCH_COMMAND]:
                    if await trigger.run(actor, command_lower, catch_vars(char), cls._game_state):
                        return True
        # Each character's top-level inventory (not items inside containers)
        for char in list(room.characters):
            for item in list(char.contents):
                if TriggerType.CATCH_COMMAND in item.triggers_by_type:
                    for trigger in item.triggers_by_type[TriggerType.CATCH_COMMAND]:
                        if await trigger.run(actor, command_lower, catch_vars(item), cls._game_state):
                            return True
        return False

    @classmethod
    async def process_command(cls, actor: Actor, input: str, vars: dict = None, from_script: bool = False) -> bool:
        """
        Process a command for an actor.
        
        Returns:
            bool: True if command succeeded (or made progress), False if it failed completely
        """
        from .command_handler_interface import CommandResult
        logger = StructuredLogger(__name__, prefix="process_command()> ")
        # print(actor)
        logger.debug3(f"processing input for actor {actor.id}: {input}")
        
        # Set current actor context for admin log echoing (warning+ messages echoed to admins)
        set_current_actor(actor)
        
        # Debug: log every command issued by an object when object_commands debug is on (at debug level so it can be squelched)
        if actor.actor_type == ActorType.OBJECT and cls._game_state.is_debug_enabled("object_commands"):
            ref = (Constants.REFERENCE_SYMBOL + actor.reference_number) if actor.reference_number else "?"
            logger.debug(f"[object_commands] {actor.id} ({ref}) did: {input}")

        # Debug: log commands issued by NPCs when npc_commands is on and NPC is in same room as activator
        if (actor.actor_type == ActorType.CHARACTER
                and hasattr(actor, 'has_perm_flags') and not actor.has_perm_flags(PermanentCharacterFlags.IS_PC)
                and cls._game_state.is_debug_enabled("npc_commands")):
            get_activator = getattr(cls._game_state, 'get_debug_activator_character', None)
            if get_activator:
                activator = get_activator('npc_commands')
                if activator and getattr(activator, 'location_room', None) and getattr(actor, 'location_room', None) is activator.location_room:
                    ref = (Constants.REFERENCE_SYMBOL + actor.reference_number) if actor.reference_number else "?"
                    logger.debug(f"[npc_commands] {actor.name} ({ref}) did: {input!r}")

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
        succeeded = True  # Assume success unless we hit an error
        command_lower = ""  # used for routing and error logging
        for ch in cls.executing_actors:
            logger.debug3(f"executing_actors 1: {ch}")
        
        # Check if this is a 'force' command - if so, don't split by semicolon
        # because force handles semicolon-separated commands internally for the target
        input_stripped = input.strip()
        first_word = input_stripped.split()[0].lower() if input_stripped else ""
        
        # Don't record internal trigger commands in the trigger context
        is_internal_trigger_cmd = first_word in ("_trigger_start", "_trigger_end")
        
        if first_word == "force":
            commands = [input_stripped]
        else:
            commands = [cmd.strip() for cmd in input.split(';') if cmd.strip()]
        try:
            if not commands:
                msg = "Did you want to do something?"
                succeeded = False
            else:
                # Process first command normally
                first_command = commands[0]
                if first_command == "":
                    msg = "Did you want to do something?"
                    succeeded = False
                elif actor.actor_type == ActorType.CHARACTER and actor.is_dead():
                    msg = "You are dead.  You can't do anything."
                    succeeded = False
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                    and not first_command.startswith("stand"):
                    msg = "You can't do that while you're sleeping."
                    succeeded = False
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                    and not first_command.startswith("stand"):
                    msg = "You can't do that while you're sitting."
                    succeeded = False
                elif actor.actor_type == ActorType.CHARACTER \
                    and actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
                    msg = "You are stunned!"
                    succeeded = False
                elif actor.is_busy(cls._game_state.get_current_tick()):
                    # Queue the commands if the actor is busy
                    for cmd in commands:
                        actor.command_queue.append(cmd)
                    msg = "You are busy. Your command has been queued."
                    # Queued is still considered "success" as it will execute later
                    succeeded = True
                else:
                    parts = split_preserving_quotes(first_command)
                    if len(parts) == 0:
                        msg = "Did you want to do something?"
                        succeeded = False
                    else:
                        # Route by lowercase command so "Get", "GET", "get" all work
                        command_lower = parts[0].lower()
                        rest = ' '.join(parts[1:])
                        # Lowercase argument text for all commands except say/whisper/echo/emote etc.
                        preserve_cap = (command_lower in cls.PRESERVE_CAPITALIZATION_COMMANDS
                                       or command_lower in cls.EMOTE_MESSAGES)
                        if not preserve_cap:
                            rest = (rest or "").lower()
                        # Try catch_command triggers first (room → objects → NPCs → inventories)
                        if await cls._try_catch_command_triggers(actor, command_lower, first_command):
                            pass  # trigger ran and command processing stops
                        elif command_lower in cls.command_handlers:
                            # Privileged commands: only admins or NPCs/scripts may use them
                            if command_lower in cls.privileged_commands:
                                is_pc = hasattr(actor, 'has_perm_flags') and actor.has_perm_flags(PermanentCharacterFlags.IS_PC)
                                if is_pc and not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
                                    await actor.send_text(CommTypes.DYNAMIC, "You don't have permission to do that.")
                                else:
                                    await cls.command_handlers[command_lower](command_lower, actor, rest)
                            else:
                                await cls.command_handlers[command_lower](command_lower, actor, rest)
                        elif command_lower in cls.EMOTE_MESSAGES:
                            await cls.cmd_specific_emote(command_lower, actor, rest)
                        else:
                            input_for_skill = (command_lower + ' ' + rest) if rest else command_lower
                            logger.debug3(f"checking skills registry for: {input_for_skill}")
                            skill_name, remainder = SkillsRegistry.parse_skill_name_from_input(input_for_skill)
                            if skill_name:
                                logger.debug3(f"found skill: {skill_name}")
                                await SkillsRegistry.invoke_skill_by_name(cls._game_state, actor, skill_name, remainder, 0)
                            else:
                                logger.debug3(f"no skill found")
                                logger.debug3(f"Unknown command: {command_lower}")
                                msg = "Unknown command"
                                succeeded = False

                # Queue any additional commands
                if len(commands) > 1:
                    actor.command_queue.extend(commands[1:])
                    if not msg:  # Only add queue message if there wasn't an error message
                        msg = f"Queued {len(commands)-1} additional command(s)."
        except KeyError:
            logger.error(f"KeyError processing command {command_lower}")
            msg = "Command failure."
            succeeded = False
            raise
        except:
            logger.exception(f"exception handling input '{input}' for actor {actor.rid}")
            succeeded = False
            raise
        finally:
            # Flush any queued admin log messages and clear the actor context
            await flush_admin_log_queue()
            clear_current_actor()

        if msg and hasattr(actor, 'connection') and actor.connection:
            await actor.send_text(CommTypes.DYNAMIC, msg)
        elif msg:
            set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        
        # Record command result in trigger context if active (but not for internal trigger commands)
        if not is_internal_trigger_cmd and actor.trigger_context is not None and actor.trigger_context.current_trigger is not None:
            # Only record the first command (the one we actually executed)
            cmd_to_record = commands[0] if commands else input
            actor.trigger_context.current_trigger.command_results.append(
                CommandResult(command=cmd_to_record, succeeded=succeeded, message=msg)
            )
            logger.debug3(f"Recorded command result: {cmd_to_record} -> {'succeeded' if succeeded else 'failed'}")
        
        # Only remove from executing_actors if we added it (not a nested call)
        if not is_nested:
            if not actor.rid in cls.executing_actors:
                logger.warning(f"actor {actor.rid} not in executing_actors")
            else:
                del cls.executing_actors[actor.rid]
        
        return succeeded


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
            if actor != room and TriggerType.ON_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.ON_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and TriggerType.ON_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.ON_SAY]:
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
        room = actor.location_room

        # Run ON_TELL triggers on the target (directed speech: sayto/tell/whisper/ask)
        from .llm_npc_conversation import NPCConversationHandler
        any_trigger_fired = False
        if target != actor and TriggerType.ON_TELL in target.triggers_by_type:
            for trig in target.triggers_by_type[TriggerType.ON_TELL]:
                if await trig.run(target, text, vars, cls._game_state):
                    any_trigger_fired = True

        # If no trigger fired but NPC has LLM, call LLM directly
        if not any_trigger_fired and room and target in room.get_characters():
            if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
                await cls._handle_llm_conversation(actor, target, text, room)

        if room:
            msg = f"{actor.art_name_cap} says to {target.name}, \"{text}\""
            vars = set_vars(actor, actor, target, msg)
            await room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state = cls._game_state)
            if actor != room and TriggerType.ON_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.ON_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and ch != target and TriggerType.ON_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.ON_SAY]:
                        await trig.run(ch, text, vars, cls._game_state)

    async def cmd_ask(cls, actor: Actor, input: str):
        """
        Ask a question to someone in the room. Works like sayto but with different messages.
        
        If target has triggers: runs triggers (which queue script commands and _trigger_end).
        If target has LLM but no triggers: calls LLM directly.
        If target has both: triggers run first, then _trigger_end sends results to LLM.
        
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
        room = actor.location_room

        # Run ON_TELL triggers on the target (directed speech: ask)
        from .llm_npc_conversation import NPCConversationHandler
        any_trigger_fired = False
        if target != actor and TriggerType.ON_TELL in target.triggers_by_type:
            for trig in target.triggers_by_type[TriggerType.ON_TELL]:
                if await trig.run(target, text, vars, cls._game_state):
                    any_trigger_fired = True

        # If no trigger fired but NPC has LLM, call LLM directly
        if not any_trigger_fired and room and target in room.get_characters():
            if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
                await cls._handle_llm_conversation(actor, target, text, room)

        if room:
            msg = f"{actor.art_name_cap} asks {target.name}, \"{text}\""
            vars = set_vars(actor, actor, target, msg)
            await room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state = cls._game_state)
            if actor != room and TriggerType.ON_SAY in room.triggers_by_type:
                for trig in room.triggers_by_type[TriggerType.ON_SAY]:
                    await trig.run(room, text, vars, cls._game_state)
            for ch in room.get_characters():
                if ch != actor and ch != target and TriggerType.ON_SAY in ch.triggers_by_type:
                    for trig in ch.triggers_by_type[TriggerType.ON_SAY]:
                        await trig.run(ch, text, vars, cls._game_state)
    
    @staticmethod
    def _is_transient_llm_error(error_str: str) -> bool:
        """True if the error is transient (service/network), so player can 'try again'."""
        if not error_str:
            return False
        s = error_str.upper()
        transient_markers = (
            "503", "504", "UNAVAILABLE", "TIMEOUT", "CONNECTION", "NETWORK",
            "SERVICE UNAVAILABLE", "GATEWAY", "OVERLOADED", "RESOURCE_EXHAUSTED",
        )
        return any(m in s for m in transient_markers)

    async def _handle_llm_conversation(cls, actor: Actor, target: Character, text: str, room, trigger_actions: list = None) -> None:
        """
        Handle LLM-driven NPC conversation.
        
        Args:
            actor: The player speaking
            target: The NPC being spoken to
            text: What the player said
            room: The room where this is happening
            trigger_actions: Optional list of trigger scripts that just ran (to provide context to LLM)
        """
        logger = StructuredLogger(__name__, prefix="_handle_llm_conversation()> ")
        
        from .llm_npc_conversation import get_conversation_handler
        
        try:
            handler = get_conversation_handler()
            result = await handler.process_speech(actor, target, text, cls._game_state, trigger_actions=trigger_actions)
            
            if result.error:
                if cls._is_transient_llm_error(result.error):
                    logger.debug(f"LLM conversation error (transient): {result.error}")
                    await room.echo(
                        CommTypes.DYNAMIC,
                        f'{target.art_name_cap} says to {actor.name}, "Sorry, I didn\'t hear that. Would you mind repeating?"',
                        game_state=cls._game_state
                    )
                else:
                    logger.error(f"LLM conversation error: {result.error}")
                    await room.echo(
                        CommTypes.DYNAMIC,
                        f"{target.art_name_cap} looks at {actor.name} with a puzzled expression.",
                        game_state=cls._game_state
                    )
                return
            
            # Show any emotes extracted from the response (displayed as actions, not speech).
            # Skip very short emotes (e.g. "*mis*") which are often LLM truncation artifacts.
            for emote in result.emotes:
                if len(emote.strip()) >= 4:
                    await room.echo(
                        CommTypes.DYNAMIC,
                        f'{target.art_name_cap} {emote}',
                        game_state=cls._game_state
                    )
            
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
        room = actor.location_room
        if room:
            if actor.actor_type == ActorType.CHARACTER:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
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
        actual_heal = target.increase_hp(heal_amount)
        
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

    async def cmd_applystate(cls, actor: Actor, input: str):
        """
        Apply a timed state to a target (room, object, or character). Privileged/script command.

        Usage: applystate <target> <state_name> <duration_seconds> [state-specific args...]

        States and their extra arguments:
          experiencemodifier <multiplier>   e.g. 0.75 death penalty, 1.25 scroll of learning (target must be character)
          admin   (FOR DEBUGGING) temporary is_admin for duration (target must be character)
        """
        from .utility import ticks_from_seconds
        logger = StructuredLogger(__name__, prefix="cmd_applystate()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")

        pieces = split_preserving_quotes(input)
        if len(pieces) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: applystate <target> <state_name> <duration_seconds> [state args...]")
            return

        target_name = pieces[0].strip()
        state_name = pieces[1].strip().lower()
        duration_str = pieces[2].strip()
        extra = pieces[3:] if len(pieces) > 3 else []

        try:
            duration_sec = float(duration_str)
            if duration_sec <= 0:
                raise ValueError("duration must be positive")
        except ValueError:
            await actor.send_text(CommTypes.DYNAMIC, f"Invalid duration: {duration_str}. Use a positive number of seconds.")
            return

        duration_ticks = ticks_from_seconds(int(duration_sec))
        if duration_ticks <= 0:
            await actor.send_text(CommTypes.DYNAMIC, "Duration too small for the game tick rate; use a larger value.")
            return

        # Resolve target: character, object, or room
        target = None
        start_room = getattr(actor, 'location_room', None)
        start_zone = getattr(start_room, 'zone', None) if start_room else None

        if target_name.strip().startswith(Constants.REFERENCE_SYMBOL):
            ref_key = cls._game_state._normalize_reference_key(target_name.strip()[len(Constants.REFERENCE_SYMBOL):])
            target = Actor.get_reference(ref_key) if ref_key else None
        if target is None and target_name.strip().lower() == "here" and start_room:
            target = start_room
        if target is None:
            target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        if target is None and start_room:
            target = cls._game_state.find_target_object(target_name, actor=actor, start_room=start_room)
        if target is None and start_zone:
            target = cls._game_state.find_target_room(actor, target_name, start_zone)

        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return

        # Dispatch by state name; each branch validates target type and extra args, then applies
        if state_name == "experiencemodifier":
            if not isinstance(target, Character):
                await actor.send_text(CommTypes.DYNAMIC, "experiencemodifier state requires a character target.")
                return
            if len(extra) < 1:
                await actor.send_text(CommTypes.DYNAMIC, "Usage: applystate <target> experiencemodifier <duration_seconds> <xp_multiplier>")
                return
            try:
                multiplier = float(extra[0])
            except ValueError:
                await actor.send_text(CommTypes.DYNAMIC, f"Invalid xp multiplier: {extra[0]}. Use a number (e.g. 0.75 or 1.25).")
                return
            from .nondb_models.actor_states import CharacterStateExperienceModifier, get_actor_state
            if (existing := get_actor_state(target, CharacterStateExperienceModifier)) is not None:
                await actor.send_text(CommTypes.DYNAMIC, f"Target already has an experience modifier ({existing.modifier}x); applied another (multipliers stack).")
            state = CharacterStateExperienceModifier(
                actor=target,
                game_state=cls._game_state,
                source_actor=actor,
                state_type_name="perspicacious",
                modifier=multiplier,
            )
            await state.apply_state(
                start_tick=cls._game_state.get_current_tick(),
                duration_ticks=duration_ticks,
            )
            await actor.send_text(CommTypes.DYNAMIC, f"Applied experiencemodifier (multiplier {multiplier}) to {target.art_name} for {duration_sec:.0f} seconds.")
            return

        # FOR DEBUGGING REMOVE BEFORE PRODUCTION: admin state (temporary is_admin for duration)
        if state_name == "admin":
            if not isinstance(target, Character):
                await actor.send_text(CommTypes.DYNAMIC, "admin state requires a character target.")
                return
            from .nondb_models.actor_states import CharacterStateAdmin
            state = CharacterStateAdmin(
                actor=target,
                game_state=cls._game_state,
                source_actor=actor,
                state_type_name="godlike",
            )
            await state.apply_state(
                start_tick=cls._game_state.get_current_tick(),
                duration_ticks=duration_ticks,
            )
            await actor.send_text(CommTypes.DYNAMIC, f"Applied admin (godlike) to {target.art_name} for {duration_sec:.0f} seconds.")
            return

        await actor.send_text(CommTypes.DYNAMIC, f"Unknown state: {state_name}. Known states: experiencemodifier, admin.")

    async def cmd_setstat(cls, actor: Actor, input: str):
        """
        Set a numeric stat on a character (admin-only, in-room only, instant).
        Supports dice notation for amount where applicable (e.g. 2d6+3).

        Usage: setstat <target> <stat> <amount>
        Amount: number, dice (e.g. 2d6+3), or prefix with + (add to current) / - (subtract from current, min 0).

        Stats: hp, max_hp, mana, max_mana, stamina, max_stamina, xp,
               str|strength, dex|dexterity, con|constitution,
               int|intelligence, wis|wisdom, cha|charisma,
               unspent_attribute_points
        """
        from .utility import roll_dice, get_dice_parts
        logger = StructuredLogger(__name__, prefix="cmd_setstat()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")

        pieces = split_preserving_quotes(input)
        if len(pieces) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: setstat <target> <stat> <amount>  (amount may be +N or -N for relative)")
            return

        target_name = pieces[0]
        stat_name = pieces[1].strip().lower()
        amount_str = pieces[2].strip()

        # Relative mode: + add to current, - subtract from current (min 0)
        relative_mode = None  # None, '+', '-'
        if amount_str.startswith('+'):
            relative_mode = '+'
            amount_str = amount_str[1:].strip()
        elif amount_str.startswith('-'):
            relative_mode = '-'
            amount_str = amount_str[1:].strip()

        # In-room only
        target = cls._game_state.find_target_character(actor, target_name, search_world=False)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return

        if not isinstance(target, Character):
            await actor.send_text(CommTypes.DYNAMIC, "Target is not a character.")
            return

        # Parse amount: dice (e.g. 2d6+3) or constant
        if 'd' in amount_str.lower():
            dice_parts = get_dice_parts(amount_str)
            if dice_parts[0] > 0:
                amount = roll_dice(dice_parts[0], dice_parts[1], dice_parts[2])
            else:
                amount = dice_parts[2]
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                await actor.send_text(CommTypes.DYNAMIC, "Amount must be a number or dice (e.g. 2d6+3). Prefix + or - for relative.")
                return

        # Stat name -> (display_name, setter: callable that takes target and value; returns True if attribute so we recalc)
        def _set_hp(c, v):
            c.set_hp_to(max(0, min(c.max_hit_points, v)))
        def _set_max_hp(c, v):
            v = max(0, v)
            c.max_hit_points = v
            c.current_hit_points = min(c.current_hit_points, v)
        def _set_mana(c, v):
            c.set_mana_to(max(0, min(c.max_mana, v)))
        def _set_max_mana(c, v):
            v = max(0, v)
            c.max_mana = v
            c.current_mana = min(c.current_mana, v)
        def _set_stamina(c, v):
            c.set_stamina_to(max(0, min(c.max_stamina, v)))
        def _set_max_stamina(c, v):
            v = max(0, v)
            c.max_stamina = v
            c.current_stamina = min(c.current_stamina, v)
        def _set_xp(c, v):
            c.experience_points = max(0, v)
        def _set_attr(attr):
            def _set(c, v):
                c.attributes[attr] = max(0, v)
            return _set
        def _set_unspent(c, v):
            c.unspent_attribute_points = max(0, v)

        def _get_attr(attr):
            return lambda c: c.attributes.get(attr, 0)

        getter_map = {
            "hp": lambda c: c.current_hit_points,
            "current_hp": lambda c: c.current_hit_points,
            "max_hp": lambda c: c.max_hit_points,
            "mana": lambda c: c.current_mana,
            "current_mana": lambda c: c.current_mana,
            "max_mana": lambda c: c.max_mana,
            "stamina": lambda c: c.current_stamina,
            "current_stamina": lambda c: c.current_stamina,
            "max_stamina": lambda c: c.max_stamina,
            "xp": lambda c: c.experience_points,
            "experience": lambda c: c.experience_points,
            "experience_points": lambda c: c.experience_points,
            "str": _get_attr(CharacterAttributes.STRENGTH),
            "strength": _get_attr(CharacterAttributes.STRENGTH),
            "dex": _get_attr(CharacterAttributes.DEXTERITY),
            "dexterity": _get_attr(CharacterAttributes.DEXTERITY),
            "con": _get_attr(CharacterAttributes.CONSTITUTION),
            "constitution": _get_attr(CharacterAttributes.CONSTITUTION),
            "int": _get_attr(CharacterAttributes.INTELLIGENCE),
            "intelligence": _get_attr(CharacterAttributes.INTELLIGENCE),
            "wis": _get_attr(CharacterAttributes.WISDOM),
            "wisdom": _get_attr(CharacterAttributes.WISDOM),
            "cha": _get_attr(CharacterAttributes.CHARISMA),
            "charisma": _get_attr(CharacterAttributes.CHARISMA),
            "unspent_attribute_points": lambda c: c.unspent_attribute_points,
        }

        stat_map = {
            "hp": ("hp", _set_hp, False),
            "current_hp": ("hp", _set_hp, False),
            "max_hp": ("max_hp", _set_max_hp, False),
            "mana": ("mana", _set_mana, False),
            "current_mana": ("mana", _set_mana, False),
            "max_mana": ("max_mana", _set_max_mana, False),
            "stamina": ("stamina", _set_stamina, False),
            "current_stamina": ("stamina", _set_stamina, False),
            "max_stamina": ("max_stamina", _set_max_stamina, False),
            "xp": ("xp", _set_xp, False),
            "experience": ("xp", _set_xp, False),
            "experience_points": ("xp", _set_xp, False),
            "str": ("strength", _set_attr(CharacterAttributes.STRENGTH), True),
            "strength": ("strength", _set_attr(CharacterAttributes.STRENGTH), True),
            "dex": ("dexterity", _set_attr(CharacterAttributes.DEXTERITY), True),
            "dexterity": ("dexterity", _set_attr(CharacterAttributes.DEXTERITY), True),
            "con": ("constitution", _set_attr(CharacterAttributes.CONSTITUTION), True),
            "constitution": ("constitution", _set_attr(CharacterAttributes.CONSTITUTION), True),
            "int": ("intelligence", _set_attr(CharacterAttributes.INTELLIGENCE), True),
            "intelligence": ("intelligence", _set_attr(CharacterAttributes.INTELLIGENCE), True),
            "wis": ("wisdom", _set_attr(CharacterAttributes.WISDOM), True),
            "wisdom": ("wisdom", _set_attr(CharacterAttributes.WISDOM), True),
            "cha": ("charisma", _set_attr(CharacterAttributes.CHARISMA), True),
            "charisma": ("charisma", _set_attr(CharacterAttributes.CHARISMA), True),
            "unspent_attribute_points": ("unspent_attribute_points", _set_unspent, False),
        }

        if stat_name not in stat_map:
            valid = "hp, max_hp, mana, max_mana, stamina, max_stamina, xp, str, dex, con, int, wis, cha, unspent_attribute_points"
            await actor.send_text(CommTypes.DYNAMIC, f"Unknown stat: {stat_name}. Valid: {valid}")
            return

        display_name, setter, is_attribute = stat_map[stat_name]
        effective_value = amount
        if relative_mode == '+':
            effective_value = getter_map[stat_name](target) + amount
        elif relative_mode == '-':
            effective_value = getter_map[stat_name](target) - amount

        setter(target, effective_value)
        if is_attribute:
            target.calculate_combat_bonuses()

        actual_value = getter_map[stat_name](target)
        if relative_mode == '+':
            msg = f"{target.id} {display_name} +{amount} -> {actual_value}"
        elif relative_mode == '-':
            msg = f"{target.id} {display_name} -{amount} -> {actual_value}"
        else:
            msg = f"{target.id} {display_name} set to {actual_value}"
        await actor.send_text(CommTypes.DYNAMIC, msg)
        if target.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await target.send_status_update()
        logger.debug3(f"Set {target.name} {display_name} to {actual_value}")

    async def cmd_getstat(cls, actor: Actor, input: str):
        """
        Show a numeric stat for a character (admin-only, in-room only, instant).
        Same targeting and stat names as setstat.

        Usage: getstat <target> <stat>

        Reply: "<target_id> <stat> = <value>" e.g. "city_guard max_hp = 20"
        """
        logger = StructuredLogger(__name__, prefix="cmd_getstat()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")

        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: getstat <target> <stat>")
            return

        target_name = pieces[0]
        stat_name = pieces[1].strip().lower()

        target = cls._game_state.find_target_character(actor, target_name, search_world=False)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return

        if not isinstance(target, Character):
            await actor.send_text(CommTypes.DYNAMIC, "Target is not a character.")
            return

        # Stat name -> (display_name, getter)  (display_name matches setstat for consistency)
        def _get_attr(attr):
            return lambda c: c.attributes.get(attr, 0)

        stat_map = {
            "hp": ("hp", lambda c: c.current_hit_points),
            "current_hp": ("hp", lambda c: c.current_hit_points),
            "max_hp": ("max_hp", lambda c: c.max_hit_points),
            "mana": ("mana", lambda c: c.current_mana),
            "current_mana": ("mana", lambda c: c.current_mana),
            "max_mana": ("max_mana", lambda c: c.max_mana),
            "stamina": ("stamina", lambda c: c.current_stamina),
            "current_stamina": ("stamina", lambda c: c.current_stamina),
            "max_stamina": ("max_stamina", lambda c: c.max_stamina),
            "xp": ("xp", lambda c: c.experience_points),
            "experience": ("xp", lambda c: c.experience_points),
            "experience_points": ("xp", lambda c: c.experience_points),
            "str": ("strength", _get_attr(CharacterAttributes.STRENGTH)),
            "strength": ("strength", _get_attr(CharacterAttributes.STRENGTH)),
            "dex": ("dexterity", _get_attr(CharacterAttributes.DEXTERITY)),
            "dexterity": ("dexterity", _get_attr(CharacterAttributes.DEXTERITY)),
            "con": ("constitution", _get_attr(CharacterAttributes.CONSTITUTION)),
            "constitution": ("constitution", _get_attr(CharacterAttributes.CONSTITUTION)),
            "int": ("intelligence", _get_attr(CharacterAttributes.INTELLIGENCE)),
            "intelligence": ("intelligence", _get_attr(CharacterAttributes.INTELLIGENCE)),
            "wis": ("wisdom", _get_attr(CharacterAttributes.WISDOM)),
            "wisdom": ("wisdom", _get_attr(CharacterAttributes.WISDOM)),
            "cha": ("charisma", _get_attr(CharacterAttributes.CHARISMA)),
            "charisma": ("charisma", _get_attr(CharacterAttributes.CHARISMA)),
            "unspent_attribute_points": ("unspent_attribute_points", lambda c: c.unspent_attribute_points),
        }

        if stat_name not in stat_map:
            valid = "hp, max_hp, mana, max_mana, stamina, max_stamina, xp, str, dex, con, int, wis, cha, unspent_attribute_points"
            await actor.send_text(CommTypes.DYNAMIC, f"Unknown stat: {stat_name}. Valid: {valid}")
            return

        display_name, getter = stat_map[stat_name]
        value = getter(target)
        await actor.send_text(CommTypes.DYNAMIC, f"{target.id} {display_name} = {value}")
        logger.debug3(f"Get {target.name} {display_name} = {value}")

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
            vars = set_vars(actor, actor, target, msg)
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
        
        # Run ON_TELL triggers on the target (directed speech: tell/whisper)
        room = actor.location_room
        from .llm_npc_conversation import NPCConversationHandler
        any_trigger_fired = False
        if room and target in room.get_characters():
            if target != actor and TriggerType.ON_TELL in target.triggers_by_type:
                for trig in target.triggers_by_type[TriggerType.ON_TELL]:
                    if await trig.run(target, text, vars, cls._game_state):
                        any_trigger_fired = True

            # If no trigger fired but NPC has LLM, call LLM directly
            if not any_trigger_fired:
                if target.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is not None:
                    await cls._handle_llm_conversation(actor, target, text, room)


    async def cmd_emote(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_emote()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        await actor.send_text(CommTypes.DYNAMIC, f"You emote, \"{text}\"")
        room = actor.location_room
        if room:
            if actor.actor_type == ActorType.CHARACTER:
                if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    await room.echo(CommTypes.DYNAMIC, f"... {actor.name} {text}", vars, exceptions=[actor], game_state=cls._game_state)
                else:
                    await room.echo(CommTypes.DYNAMIC, f"{actor.art_name_cap} {text}", vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor], game_state=cls._game_state)
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")


    @classmethod
    async def cmd_commands(cls, actor: Actor, input: str):
        """List commands the user can execute: privileged (if admin), regular, and emotes."""
        all_cmd_names = set(cls.command_handlers.keys())
        emote_names = set(cls.EMOTE_MESSAGES.keys())
        regular_names = all_cmd_names - cls.privileged_commands - emote_names

        lines = []
        can_privileged = hasattr(actor, 'has_game_flags') and actor.has_game_flags(GamePermissionFlags.IS_ADMIN)
        if can_privileged:
            priv = sorted(cls.privileged_commands)
            lines.append("privileged commands: " + ", ".join(priv))
        lines.append("regular commands: " + ", ".join(sorted(regular_names)))
        lines.append("emotes: " + ", ".join(sorted(emote_names)))
        await actor.send_text(CommTypes.STATIC, "\n".join(lines))


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
        room = actor.location_room
        if room:
            if actor.actor_type == ActorType.CHARACTER:
                await room.echo(CommTypes.DYNAMIC, "... " 
                               + room_msg, vars, 
                               exceptions=([actor] if target == None else [actor, target]), 
                               game_state=cls._game_state)
            elif actor.actor_type == ActorType.OBJECT:
                await room.echo(CommTypes.DYNAMIC, room_msg, vars, 
                               exceptions=([actor] if target == None else [actor, target]), 
                               game_state=cls._game_state)
            elif actor.actor_type == ActorType.ROOM:
                await room.echo(CommTypes.DYNAMIC, room_msg, vars, 
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
            logger.warning(f"({pieces}) Set {target_name} var on what kind of target?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var on what kind of target?")
            return
        if pieces[0].lower() != "char":
            logger.warning(f"({pieces}) Only character targets allowed at the moment.")
            await actor.send_text(CommTypes.DYNAMIC, "Only character targets allowed at the moment.")
            return
        if len(pieces) < 2:
            logger.warning(f"({pieces}) Set {target_name} var on whom?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var on whom?")
            return
        if len(pieces) < 3:
            logger.warning(f"({pieces}) Set which {target_name} var?")
            await actor.send_text(CommTypes.DYNAMIC, "Set which temp var?")
            return
        if len(pieces) < 4:
            logger.warning(f"({pieces}) Set {target_name} var to what?")
            await actor.send_text(CommTypes.DYNAMIC, "Set temp var to what?")
            return
        target = cls._game_state.find_target_character(actor, pieces[1], search_world=True)
        if target == None:
            logger.warning(f"({pieces}) Could not find target.")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
            return
        var_value = ' '.join(pieces[3:])
        vars = set_vars(actor, actor, target, var_value)
        logger.debug3(f"target.name: {target.name}, {target_name} var: {pieces[2]}, var_value: {var_value}")
        var_value = replace_vars(var_value, vars)
        var_value = normalize_var_value(var_value)
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
        debug_setquestvar = cls._game_state.is_debug_enabled("setquestvar")
        if debug_setquestvar:
            logger.debug(f"[setquestvar] entry: actor={getattr(actor, 'id', None)} ({getattr(actor, 'rid', None)}), actor_type={getattr(actor, 'actor_type', None)}, input={input!r}")
        
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
            if debug_setquestvar:
                logger.debug(f"[setquestvar] target from 'me' -> actor: id={getattr(target, 'id', None)}, rid={getattr(target, 'rid', None)}, type={getattr(target, 'actor_type', None)}")
        else:
            target = cls._game_state.find_target_character(actor, target_str, search_world=True)
            if debug_setquestvar:
                logger.debug(f"[setquestvar] find_target_character(actor, {target_str!r}) -> {target}; target id={getattr(target, 'id', None) if target else None}, rid={getattr(target, 'rid', None) if target else None}, type={getattr(target, 'actor_type', None) if target else None}")
        
        if target is None:
            if debug_setquestvar:
                logger.debug(f"[setquestvar] abort: target not found for {target_str!r}")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_str}'.")
            return
        
        var_id = pieces[1]
        value_str = ' '.join(pieces[2:])
        value = normalize_var_value(value_str)

        if debug_setquestvar:
            perm_before = dict(getattr(target, "perm_variables", None) or {})
            logger.debug(f"[setquestvar] target: id={getattr(target, 'id', None)}, name={getattr(target, 'name', None)}, has perm_variables={hasattr(target, 'perm_variables')}, perm_variables is None={getattr(target, 'perm_variables', None) is None}, perm_variables keys before: {list(perm_before.keys())}")
        
        # Use the quest schema system (invoking_actor = who ran the command, so zone prefix comes from script's zone)
        from .nondb_models.quests import set_quest_var
        set_quest_var(target, var_id, value, game_state=cls._game_state, debug_setquestvar=debug_setquestvar, invoking_actor=actor)
        
        if debug_setquestvar:
            perm_after = getattr(target, "perm_variables", None) or {}
            logger.debug(f"[setquestvar] after set_quest_var: perm_variables keys: {list(perm_after.keys())}; murder_mystery/found_body related: {[k for k in perm_after if 'murder_mystery' in k or 'found_body' in k]}")
        
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

        from .nondb_models.quests import get_quest_var
        value = get_quest_var(target, var_id, invoking_actor=actor)
        
        await actor.send_text(CommTypes.DYNAMIC, f"Quest var '{var_id}' for {target.name} = {value}")

    async def cmd_quests(cls, actor: Actor, input: str):
        """
        Lists the player's current active quests.
        Uses GameState.quest_index: only checks quests that reference variables the player has.
        """
        if not getattr(actor, 'perm_variables', None) or not actor.perm_variables:
            await actor.send_text(CommTypes.DYNAMIC, "You have no active quests.\n")
            return

        candidate_quests = set()
        for var_name in actor.perm_variables.keys():
            linked_quests = cls._game_state.quest_index.get(var_name, [])
            candidate_quests.update(linked_quests)

        if not candidate_quests:
            await actor.send_text(CommTypes.DYNAMIC, "You have no active quests.\n")
            return

        active_quests_output = []
        for quest in candidate_quests:
            active_stage = quest.get_active_stage(actor)
            if active_stage:
                active_quests_output.append(
                    f"|G{quest.title}|n: {active_stage.description}"
                )

        if not active_quests_output:
            await actor.send_text(CommTypes.DYNAMIC, "You have no active quests.\n")
        else:
            header = "|W=== Current Quests ===|n\n\n"
            await actor.send_text(CommTypes.STATIC, header + "\n".join(active_quests_output) + "\n")

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
            target = cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)
        
        if target is None:
            room = actor.location_room
            if TriggerType.CATCH_LOOK in room.triggers_by_type:
                vars = set_vars(room, actor, room, keyword)
                for trigger in room.triggers_by_type[TriggerType.CATCH_LOOK]:
                    if await trigger.run(room, keyword, vars, cls._game_state):
                        return
            await actor.send_text(CommTypes.DYNAMIC, "Look at what?")
            return
        
        if isinstance(target, Character):
            await CoreActionsInterface.get_instance().do_look_character(actor, target)
        elif isinstance(target, Object):
            await CoreActionsInterface.get_instance().do_look_object(actor, target)
            if TriggerType.CATCH_LOOK in target.triggers_by_type:
                vars = set_vars(target, actor, target, keyword)
                for trigger in target.triggers_by_type[TriggerType.CATCH_LOOK]:
                    await trigger.run(target, keyword, vars, cls._game_state)
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Look at what?")


    async def cmd_spawn(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_spawn()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
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
        Spawn an object into a target (character inventory, room, or container).
        
        Usage: spawnobj <target> <object_id>
        
        Target can be:
        - character (e.g. me, %S%, guard) - object goes into that character's inventory
        - room (e.g. here, zone.room_id) - object is spawned in the room
        - object that is a container - object is put inside the container; non-containers fail with "couldn't figure out where to put it"
        
        Examples:
            spawnobj here rusty_sword
            spawnobj me savant_scroll_of_learning
            spawnobj me master_zone.savant_scroll_of_learning
            spawnobj gloomy_graveyard.manor_house_entrance key
        """
        logger = StructuredLogger(__name__, prefix="cmd_spawnobj()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: spawnobj <target> <object_id>")
            return
        
        target_name = pieces[0].strip()
        obj_id = pieces[1].strip()
        
        # Resolve target: character, room, or object
        target = None
        start_room = getattr(actor, 'location_room', None)
        start_zone = getattr(start_room, 'zone', None) if start_room else None
        
        if target_name.lower() in ("me", "self"):
            target = actor
        elif target_name.startswith(Constants.REFERENCE_SYMBOL):
            ref_key = cls._game_state._normalize_reference_key(target_name[len(Constants.REFERENCE_SYMBOL):])
            target = Actor.get_reference(ref_key) if ref_key else None
        if target is None and target_name.lower() == "here" and start_room:
            target = start_room
        if target is None:
            target = cls._game_state.find_target_character(actor, target_name, search_world=True)
        if target is None and start_room:
            target = cls._game_state.find_target_object(target_name, actor=actor, start_room=start_room)
        if target is None and start_zone:
            target = cls._game_state.find_target_room(actor, target_name, start_zone)
        
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Cannot find target: {target_name}")
            return
        
        # Normalize object ID (zone.object_id if no dot)
        if "." not in obj_id:
            zone_id = getattr(start_room, 'zone', None) and getattr(start_room.zone, 'id', None) or (start_zone.id if start_zone else None)
            if zone_id:
                obj_id = f"{zone_id}.{obj_id}"
            else:
                await actor.send_text(CommTypes.DYNAMIC, "Could not determine zone for object id.")
                return
        
        obj_template = cls._game_state.world_definition.objects.get(obj_id)
        if not obj_template:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find object template '{obj_id}'")
            return
        
        new_obj = Object.create_from_definition(obj_template)
        if not new_obj:
            await actor.send_text(CommTypes.DYNAMIC, "Failed to create object")
            return
        
        if isinstance(target, Character):
            target.add_to_inventory(new_obj)
            if target is actor:
                await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} into your inventory.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} into {target.art_name}'s inventory.")
        elif isinstance(target, Room):
            target.add_object(new_obj)
            await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} in {target.name}.")
        elif isinstance(target, Object):
            if target.object_flags.are_flags_set(ObjectFlags.IS_CONTAINER):
                target.add_object(new_obj)
                await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_obj.art_name} into {target.art_name}.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, "Couldn't figure out where to put it.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Couldn't figure out where to put it.")


    async def cmd_give(cls, actor: Actor, input: str):
        """
        Give an item from inventory to another character.
        
        Usage: give <item> <target>
        
        Examples:
            give sword guard
            give "rusty key" old_tom
        """
        logger = StructuredLogger(__name__, prefix="cmd_give()> ")
        debug_give = cls._game_state.is_debug_enabled("give")
        if debug_give:
            logger.debug(f"[give] entry: actor.rid={actor.rid}, actor.id={getattr(actor, 'id', None)}, actor_type={getattr(actor, 'actor_type', None)}, input={input!r}")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            if debug_give:
                logger.debug("[give] early return: no input")
            await actor.send_text(CommTypes.DYNAMIC, "Give what to whom?")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            if debug_give:
                logger.debug(f"[give] early return: need 2 pieces, got {len(pieces)}: {pieces}")
            await actor.send_text(CommTypes.DYNAMIC, "Give what to whom? Usage: give <item> <target>")
            return
        
        # Last piece is the target (supports "give savant scroll of learning |C641")
        target_name = pieces[-1]
        item_name = " ".join(pieces[:-1]) if len(pieces) > 2 else pieces[0]
        if debug_give:
            logger.debug(f"[give] parsed: item_name={item_name!r}, target_name={target_name!r}")
        
        # When actor is a Room or Object (e.g. trigger script): room-only targeting unless reference; room_id valid
        if actor.actor_type != ActorType.CHARACTER:
            if debug_give:
                logger.debug(f"[give] non-CHARACTER path: actor_type={actor.actor_type}")
            start_room = actor if isinstance(actor, Room) else getattr(actor, 'location_room', None)
            start_zone = getattr(start_room, 'zone', None) if start_room else None
            target = None
            target_room = None
            use_reference = target_name and target_name.strip().startswith(Constants.REFERENCE_SYMBOL)
            if use_reference:
                ref_key = cls._game_state._normalize_reference_key(target_name.strip()[1:])
                resolved = Actor.get_reference(ref_key)
                if isinstance(resolved, Character):
                    target = resolved
                elif isinstance(resolved, Room):
                    target_room = resolved
            if target is None and target_room is None:
                target = cls._game_state.find_target_character(actor, target_name, search_world=False)
                if not target and target_name and target_name.strip().lower() == 'here' and start_room:
                    target_room = start_room
                if not target and not target_room and start_zone:
                    target_room = cls._game_state.find_target_room(actor, target_name, start_zone)
            if not target and not target_room:
                if hasattr(actor, 'send_text'):
                    await actor.send_text(CommTypes.DYNAMIC, f"Could not find '{target_name}'.")
                return
            # Find existing item (including in containers) or spawn from zone
            item = None
            parent = None
            if isinstance(actor, Object) and (item_name.strip().lower() in ('me', 'self') or actor.matches_keyword(item_name.strip().lower())):
                item = actor
                parent = getattr(actor, 'in_actor', None)
            else:
                item, parent = cls._game_state.find_target_object_with_parent(item_name, actor=actor, start_room=start_room)
            if item and parent:
                parent.remove_object(item)
                if target_room:
                    target_room.add_object(item)
                    if debug_give:
                        logger.debug("[give] non-CHARACTER: gave existing item to room")
                    return
                if target:
                    target.add_to_inventory(item)
                    await target.send_text(CommTypes.DYNAMIC, f"You receive {item.art_name}.")
                    if debug_give:
                        logger.debug("[give] non-CHARACTER: gave existing item to character")
                    return
            zone = getattr(actor, 'zone', None) or (getattr(actor, 'location_room', None) and getattr(actor.location_room, 'zone', None))
            if not zone:
                if hasattr(actor, 'send_text'):
                    await actor.send_text(CommTypes.DYNAMIC, "No zone context for give.")
                return
            obj_id = f"{zone.id}.{item_name}" if "." not in item_name else item_name
            obj_template = cls._game_state.world_definition.objects.get(obj_id)
            if not obj_template:
                if hasattr(actor, 'send_text'):
                    await actor.send_text(CommTypes.DYNAMIC, f"Could not find object '{item_name}'.")
                return
            new_obj = Object.create_from_definition(obj_template)
            if not new_obj:
                if hasattr(actor, 'send_text'):
                    await actor.send_text(CommTypes.DYNAMIC, "Failed to create object.")
                return
            if target_room:
                target_room.add_object(new_obj)
                if debug_give:
                    logger.debug("[give] non-CHARACTER: spawned and added to room")
                return
            target.add_to_inventory(new_obj)
            await target.send_text(CommTypes.DYNAMIC, f"You receive {new_obj.art_name}.")
            if debug_give:
                logger.debug("[give] non-CHARACTER path done (spawn-and-give success)")
            return

        # CHARACTER path: find item (including in containers; auto-remove from container)
        if debug_give:
            logger.debug("[give] CHARACTER path: looking up item (including containers)")
        item, parent = cls._game_state.find_target_object_with_parent(item_name, actor=actor, start_room=actor.location_room)
        if debug_give:
            logger.debug(f"[give] find_target_object_with_parent({item_name!r}) => item={item!r}, parent={parent!r}")
        if not item:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{item_name}'.")
            return
        if parent:
            parent.remove_object(item)
        # Resolve target: reference overrides room-only (search_world); else room-only; room_id (e.g. "here") valid
        start_room = actor.location_room
        start_zone = getattr(start_room, 'zone', None) if start_room else None
        target = None
        target_room = None
        use_reference = target_name and target_name.strip().startswith(Constants.REFERENCE_SYMBOL)
        if use_reference:
            ref_key = cls._game_state._normalize_reference_key(target_name.strip()[1:])
            resolved = Actor.get_reference(ref_key)
            if isinstance(resolved, Character):
                target = resolved
            elif isinstance(resolved, Room):
                target_room = resolved
        if target is None and target_room is None:
            target = cls._game_state.find_target_character(actor, target_name, search_world=False)
            if not target and target_name and target_name.strip().lower() == 'here' and start_room:
                target_room = start_room
            if not target and not target_room and start_zone:
                target_room = cls._game_state.find_target_room(actor, target_name, start_zone)
        if not target and not target_room:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find '{target_name}'.")
            return
        if target == actor:
            await actor.send_text(CommTypes.DYNAMIC, "You can't give something to yourself.")
            return
        # Transfer the item
        if target_room:
            target_room.add_object(item)
            await actor.send_text(CommTypes.DYNAMIC, f"You drop {item.art_name}.")
            msg = f"{actor.art_name_cap} drops {item.art_name}."
            vars = set_vars(actor.location_room, actor, actor, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            if debug_give:
                logger.debug("[give] CHARACTER path: gave to room")
            return
        target.add_to_inventory(item)
        if debug_give:
            logger.debug("[give] CHARACTER path: transfer done")
        
        # Messages
        await actor.send_text(CommTypes.DYNAMIC, f"You give {item.art_name} to {target.name}.")
        await target.send_text(CommTypes.DYNAMIC, f"{actor.name} gives you {item.art_name}.")
        
        msg = f"{actor.art_name_cap} gives {item.art_name} to {target.name}."
        vars = set_vars(actor, actor, target, msg)
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls._game_state)
        
        # Fire ON_RECEIVE triggers on the target (for NPC quest reactions)
        # Convention: actor (a/A) = trigger owner (receiver), subject (s/S) = giver, target (t/T) = receiver, object (o/O) = item
        trigger_ran = False
        if TriggerType.ON_RECEIVE in target.triggers_by_type:
            receive_vars = set_vars(target, actor, target, msg)
            receive_vars.update({
                'item': item.name,
                'item_id': item.id,
                'item_name': item.name,
                'giver': actor.name,
                'giver_id': actor.id,
                'o': item.id,
                'O': (Constants.REFERENCE_SYMBOL + item.reference_number) if getattr(item, 'reference_number', None) else '',
            })
            for trigger in target.triggers_by_type[TriggerType.ON_RECEIVE]:
                ran = await trigger.run(target, item.id, receive_vars, cls._game_state)
                if ran:
                    trigger_ran = True
                    break

        # If recipient is humanoid and no trigger handled the give, give it back with default message
        if not trigger_ran and hasattr(target, 'has_perm_flags') and target.has_perm_flags(PermanentCharacterFlags.HUMANOID):
            target.remove_from_inventory(item)
            actor.add_to_inventory(item)
            await actor.send_text(CommTypes.DYNAMIC, f'{target.name} says, "I don\'t know what to do with that."')
            await actor.send_text(CommTypes.DYNAMIC, f"{target.name} gives you {item.art_name}.")
            give_back_msg = f"{target.art_name_cap} gives {item.art_name} to {actor.name}."
            give_back_vars = set_vars(target, actor, actor, give_back_msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, give_back_msg, give_back_vars, exceptions=[actor, target], game_state=cls._game_state)
        if debug_give:
            logger.debug("[give] CHARACTER path done")

    async def cmd_signal(cls, actor: Actor, input: str):
        """
        Send a signal to on_signal receivers in the given scope.
        Usage: signal <scope> <signal_name> <target> <message...>
        scope: room | subzone | zone | world
        target: any actor (e.g. @C123) or the word none for no target
        message: fourth and later words, available as %text% in on_signal scripts
        """
        logger = StructuredLogger(__name__, prefix="cmd_signal()> ")
        if not input or not input.strip():
            await actor.send_text(CommTypes.DYNAMIC, "Usage: signal <room|subzone|zone|world> <signal_name> <target> <message...>")
            return
        pieces = split_preserving_quotes(input)
        if len(pieces) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: signal <room|subzone|zone|world> <signal_name> <target> <message...>")
            return
        scope = pieces[0].strip().lower()
        if scope not in ("room", "subzone", "zone", "world"):
            await actor.send_text(CommTypes.DYNAMIC, "Scope must be room, subzone, zone, or world.")
            return
        signal_name = pieces[1].strip()
        target_arg = pieces[2].strip()
        message = " ".join(pieces[3:]).strip() if len(pieces) > 3 else ""
        signaler_room = actor if isinstance(actor, Room) else getattr(actor, "location_room", None)
        if not signaler_room:
            await actor.send_text(CommTypes.DYNAMIC, "You must be in a room to send a signal.")
            return
        target_actor = None
        if target_arg.lower() != "none":
            if target_arg.startswith(Constants.REFERENCE_SYMBOL):
                ref_key = cls._game_state._normalize_reference_key(target_arg[1:])
                target_actor = Actor.get_reference(ref_key)
            else:
                target_actor = cls._game_state.find_target_character(actor, target_arg, search_world=True)
        receivers = TriggerOnSignal.get_receivers_for_scope(signaler_room, scope)
        signal_vars = {
            "signal": signal_name,
            "target_actor": target_actor,
            "text": message,
        }
        for trigger in receivers:
            if trigger.disabled_:
                continue
            run_vars = {**signal_vars}
            ran = await trigger.run(actor, message, run_vars, cls._game_state)
            if ran:
                pass  # can run multiple receivers
        logger.debug3(f"signal {scope} {signal_name} -> {len(receivers)} receivers")

    async def cmd_deregistersignals(cls, actor: Actor, input: str):
        """
        Remove all on_signal triggers for the target from the signal registry (and disable them).
        Usage: deregistersignals [target]
        target: me (default), self, or a reference (e.g. @C123). Used from catch_zerohp to stop receiving signals on death.
        """
        logger = StructuredLogger(__name__, prefix="cmd_deregistersignals()> ")
        target_str = (input or "").strip()
        if not target_str or target_str.lower() in ("me", "self"):
            target = actor
        elif target_str.startswith(Constants.REFERENCE_SYMBOL):
            ref_key = cls._game_state._normalize_reference_key(target_str[1:])
            target = Actor.get_reference(ref_key)
        else:
            target = cls._game_state.find_target_character(actor, target_str, search_world=True)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target '{target_str}'.")
            return
        triggers = list(getattr(target, "triggers_by_type", {}).get(TriggerType.ON_SIGNAL, []))
        for trigger in triggers:
            if isinstance(trigger, TriggerOnSignal):
                trigger.disable()
        logger.debug3(f"deregistersignals: {len(triggers)} on_signal trigger(s) disabled for {getattr(target, 'name', target)}")

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


    async def cmd_trigger_start(cls, actor: Actor, input: str):
        """
        Begin a trigger context for tracking script command results.
        This is an internal privileged command inserted automatically by trigger execution.
        
        Usage: _trigger_start <trigger_type>|<trigger_id>|<trigger_criteria>|<initiator_ref>
        
        The parameters are pipe-separated to allow spaces in criteria.
        """
        from .command_handler_interface import TriggerContext, TriggerResult
        logger = StructuredLogger(__name__, prefix="cmd_trigger_start()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Parse pipe-separated parameters
        parts = input.split('|')
        if len(parts) < 4:
            logger.warning(f"Invalid _trigger_start format: {input}")
            return True
        
        trigger_type = parts[0].strip()
        trigger_id = parts[1].strip()
        trigger_criteria = parts[2].strip()
        initiator_ref = parts[3].strip()
        
        # Create or update trigger context
        if actor.trigger_context is None:
            actor.trigger_context = TriggerContext(
                initiator_ref=initiator_ref,
                trigger_results=[],
                nesting_level=0
            )
        
        # Create new trigger result for this trigger
        new_trigger_result = TriggerResult(
            trigger_type=trigger_type,
            trigger_id=trigger_id,
            trigger_criteria=trigger_criteria,
            command_results=[]
        )
        
        # Set as current trigger and add to results
        actor.trigger_context.current_trigger = new_trigger_result
        actor.trigger_context.trigger_results.append(new_trigger_result)
        actor.trigger_context.nesting_level += 1
        
        logger.debug3(f"Started trigger context: {trigger_type}/{trigger_id}, nesting={actor.trigger_context.nesting_level}")
        return True


    async def cmd_trigger_end(cls, actor: Actor, input: str):
        """
        End a trigger context and optionally send results to LLM.
        This is an internal privileged command inserted automatically by trigger execution.
        
        Usage: _trigger_end
        
        When nesting level returns to 0, sends accumulated results to LLM if actor is LLM-enabled.
        """
        from .llm_npc_conversation import NPCConversationHandler, get_conversation_handler
        logger = StructuredLogger(__name__, prefix="cmd_trigger_end()> ")
        logger.debug3(f"actor.rid: {actor.rid}")
        
        if actor.trigger_context is None:
            logger.warning(f"_trigger_end called but no trigger context exists for {actor.rid}")
            return True
        
        # Decrement nesting level
        actor.trigger_context.nesting_level -= 1
        actor.trigger_context.current_trigger = None
        
        logger.debug3(f"Ended trigger, nesting now={actor.trigger_context.nesting_level}")
        
        # Only send to LLM when nesting returns to 0
        if actor.trigger_context.nesting_level > 0:
            return True
        
        # When an on_tell trigger fired, do not send to LLM for this statement
        from .nondb_models.trigger_interface import TriggerType
        if any(
            (r.trigger_type or "").upper() == TriggerType.ON_TELL.name
            for r in actor.trigger_context.trigger_results
        ):
            logger.debug3(f"Actor {actor.rid} had ON_TELL trigger(s), skipping LLM response")
            actor.trigger_context = None
            return True
        
        # Check if actor is LLM-enabled
        if actor.get_perm_var(NPCConversationHandler.VAR_CONTEXT, None) is None:
            logger.debug3(f"Actor {actor.rid} not LLM-enabled, skipping LLM response")
            actor.trigger_context = None
            return True
        
        # Send trigger results to LLM
        await cls._send_trigger_results_to_llm(actor)
        
        # Clear the trigger context
        actor.trigger_context = None
        return True


    async def _send_trigger_results_to_llm(cls, actor: Actor):
        """
        Send accumulated trigger results to the LLM for a natural response.
        """
        from .llm_npc_conversation import get_conversation_handler
        logger = StructuredLogger(__name__, prefix="_send_trigger_results_to_llm()> ")
        
        if actor.trigger_context is None or not actor.trigger_context.trigger_results:
            return
        
        context = actor.trigger_context
        
        # Find the initiator (player/character who triggered this)
        initiator = None
        if context.initiator_ref:
            initiator = Actor.get_reference(context.initiator_ref.lstrip('@'))
        
        room = actor.location_room if hasattr(actor, 'location_room') else None
        
        # Format trigger results for LLM
        trigger_actions = []
        for trigger_result in context.trigger_results:
            # Format: "ON_SAY trigger (matched 'gold'): say 'Here!' (succeeded), give gold player (failed)"
            trigger_desc = f"{trigger_result.trigger_type} trigger"
            if trigger_result.trigger_criteria:
                trigger_desc += f" ({trigger_result.trigger_criteria})"
            trigger_desc += ":"
            
            if trigger_result.command_results:
                cmd_descs = []
                for cmd_result in trigger_result.command_results:
                    status = "succeeded" if cmd_result.succeeded else "failed"
                    cmd_descs.append(f"{cmd_result.command} ({status})")
                trigger_desc += " " + ", ".join(cmd_descs)
            else:
                trigger_desc += " (no commands executed)"
            
            trigger_actions.append(trigger_desc)
        
        if not trigger_actions:
            return
        
        try:
            handler = get_conversation_handler()
            
            # Build a context speech that describes what triggered this
            # The LLM will respond to the trigger actions
            result = await handler.process_speech(
                player=initiator if initiator else actor,
                npc=actor,
                speech="[trigger event - respond to your actions]",
                game_state=cls._game_state,
                trigger_actions=trigger_actions
            )
            
            if result.error:
                if cls._is_transient_llm_error(result.error):
                    logger.debug(f"LLM trigger response error (transient): {result.error}")
                else:
                    logger.error(f"LLM trigger response error: {result.error}")
                return
            
            # Show any emotes extracted from the response (displayed as actions, not speech)
            if room:
                for emote in result.emotes:
                    await room.echo(
                        CommTypes.DYNAMIC,
                        f'{actor.art_name_cap} {emote}',
                        game_state=cls._game_state
                    )
            
            if result.dialogue and room:
                # Show NPC's response to everyone in the room
                await room.echo(
                    CommTypes.DYNAMIC,
                    f'{actor.art_name_cap} says, "{result.dialogue}"',
                    game_state=cls._game_state
                )
            
            # Handle any state changes or commands from the LLM response
            if result.state_change.npc_action:
                await cls._handle_llm_npc_action(
                    initiator if initiator else actor, actor, result.state_change.npc_action, room
                )
                
        except Exception as e:
            logger.error(f"Exception sending trigger results to LLM: {e}")
            import traceback
            traceback.print_exc()


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
        item = cls._game_state.find_target_object(item_name, search_list=target.contents)
        
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
            transfer me master_zone.starting_room
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


    async def cmd_teleport(cls, actor: Actor, input: str):
        """
        Teleport a character/NPC to a target location.
        
        This is a privileged/script command. The target can be a room, NPC, or object.
        If the target is an NPC or object, teleports to their location.
        
        When executed by an NPC, no text output is produced - the NPC script should
        handle any messaging if desired.
        
        Usage: teleport <who> <target>
        
        Arguments:
            who: "me" or NPC name/reference to teleport
            target: destination - can be:
                - A room reference (@R123) or zone.room_id
                - An NPC name/reference (teleports to their location)
                - An object name/reference (teleports to its location)
        
        Examples:
            teleport me master_zone.starting_room
            teleport me @R42
            teleport me guard
            teleport @C15 merchant
            teleport goblin me
        """
        logger = StructuredLogger(__name__, prefix="cmd_teleport()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        # Check if actor is a player (PC) - NPCs get no text output
        is_player = hasattr(actor, 'has_perm_flags') and actor.has_perm_flags(PermanentCharacterFlags.IS_PC)
        
        if not input:
            if is_player:
                await actor.send_text(CommTypes.DYNAMIC, "Usage: teleport <who> <target>")
            return
        
        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            if is_player:
                await actor.send_text(CommTypes.DYNAMIC, "Usage: teleport <who> <target>")
            return
        
        who_name = pieces[0]
        target_name = pieces[1]
        
        # Find who to teleport
        if who_name.lower() == "me":
            who = actor
        else:
            who = cls._game_state.find_target_character(actor, who_name, search_world=True)
        
        if who is None:
            if is_player:
                await actor.send_text(CommTypes.DYNAMIC, f"Could not find '{who_name}' to teleport.")
            return
        
        # Find destination - try multiple target types
        destination_room = None
        destination_description = None
        
        # Try as a character reference first
        target_char = cls._game_state.find_target_character(actor, target_name, search_world=True, exclude_initiator=False)
        if target_char and hasattr(target_char, 'location_room') and target_char.location_room:
            destination_room = target_char.location_room
            destination_description = f"{target_char.art_name}'s location"
        
        # Try as an object
        if not destination_room:
            target_obj = cls._game_state.find_target_object(target_name, actor, search_world=True)
            if target_obj:
                if hasattr(target_obj, 'location_room') and target_obj.location_room:
                    destination_room = target_obj.location_room
                    destination_description = f"where {target_obj.art_name} is"
        
        # Try as a room
        if not destination_room:
            start_zone = actor.location_room.zone if hasattr(actor, 'location_room') and actor.location_room else None
            if start_zone:
                destination_room = cls._game_state.find_target_room(actor, target_name, start_zone)
            else:
                # Try parsing as zone.room format directly
                if "." in target_name:
                    zone_id, room_id = target_name.split(".", 1)
                    zone = cls._game_state.zones.get(zone_id)
                    if zone and room_id in zone.rooms:
                        destination_room = zone.rooms[room_id]
            if destination_room:
                destination_description = destination_room.name
        
        if not destination_room:
            if is_player:
                await actor.send_text(CommTypes.DYNAMIC, f"Could not find destination '{target_name}'.")
            return
        
        # Don't teleport to same room
        if hasattr(who, 'location_room') and who.location_room == destination_room:
            if is_player:
                await actor.send_text(CommTypes.DYNAMIC, f"{who.art_name_cap} is already there.")
            return
        
        # Remove from current room (silently for NPC-initiated teleports)
        if hasattr(who, 'location_room') and who.location_room:
            who.location_room.remove_character(who)
            who.location_room = None
        
        # Arrive at destination
        await CoreActionsInterface.get_instance().arrive_room(who, destination_room)
        
        # Only show feedback to player actors
        if is_player:
            await actor.send_text(CommTypes.DYNAMIC, f"Teleported {who.art_name} to {destination_description}.")


    async def cmd_reload(cls, actor: Actor, input: str):
        """
        Reload zone or rooms from YAML (admin only).
        reload zone [zone_name] - full zone reload; current zone if zone_name omitted.
        reload rooms [zone_name] - reload room definitions only, keep occupants.
        """
        logger = StructuredLogger(__name__, prefix="cmd_reload()> ")
        pieces = split_preserving_quotes((input or "").strip())
        if not pieces:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: reload zone [zone_name]  or  reload rooms [zone_name]")
            return
        sub = pieces[0].lower()
        zone_name = pieces[1].strip() if len(pieces) > 1 else None
        if zone_name is None and hasattr(actor, 'location_room') and actor.location_room:
            zone_name = getattr(actor.location_room.zone, 'id', None)
        if zone_name is None:
            await actor.send_text(CommTypes.DYNAMIC, "No zone specified and you are not in a room. Usage: reload zone <zone_name>  or  reload rooms <zone_name>")
            return
        game_state = cls._game_state
        if zone_name not in game_state.zones:
            await actor.send_text(CommTypes.DYNAMIC, f"Zone '{zone_name}' not found.")
            return
        try:
            if sub == "zone":
                result = await game_state.reload_zone(zone_name)
            elif sub == "rooms":
                result = await game_state.reload_rooms(zone_name)
            else:
                await actor.send_text(CommTypes.DYNAMIC, "Usage: reload zone [zone_name]  or  reload rooms [zone_name]")
                return
            await actor.send_text(CommTypes.DYNAMIC, result)
        except Exception as e:
            logger.exception("reload failed")
            await actor.send_text(CommTypes.DYNAMIC, f"Reload failed: {e}")


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
        target = cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)
        
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
        
        target = cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)
        
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
        
        target = cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)
        
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
                has_key = cls._game_state.find_target_object(key_id, actor=actor) is not None
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
                has_key = cls._game_state.find_target_object(key_id, actor=actor) is not None
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
        
        target = cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)
        
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
                has_key = cls._game_state.find_target_object(key_id, actor=actor) is not None
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
                has_key = cls._game_state.find_target_object(key_id, actor=actor) is not None
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


    async def _fire_on_use(cls, actor: Actor, item: Object, target: Actor, use_type: str) -> bool:
        """
        Build vars and fire ON_USE triggers on an item.
        use_type is one of 'use', 'drink', 'read' (available to scripts as %use_type%).
        Var semantics: actor = trigger owner (item), subject = initiator (actor), target = thing acted upon
        (item when use/read without "on X", else the specified target).
        Returns True if at least one trigger ran successfully.
        """
        use_vars = set_vars(item, actor, target if target else item, item.name)
        use_vars['use_type'] = use_type
        if target:
            use_vars['target'] = target.name
            use_vars['target_id'] = target.id
        triggered = False
        for trigger in item.triggers_by_type[TriggerType.ON_USE]:
            result = await trigger.run(item, item.id, use_vars, cls._game_state)
            if result:
                triggered = True
        return triggered

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
        item = cls._game_state.find_target_object(item_name, actor=actor, start_room=actor.location_room)
        
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{item_name}'.")
            return
        
        # Find target if specified
        target = None
        if target_name:
            target = cls._game_state.find_target_object(target_name, actor=actor, start_room=actor.location_room)
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
        
        triggered = await cls._fire_on_use(actor, item, target, 'use')
        if not triggered:
            if target:
                await actor.send_text(CommTypes.DYNAMIC, f"Using {item.art_name} on {target.art_name} has no effect.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"Using {item.art_name} has no effect.")


    async def _consume_item(cls, actor: Actor, item: Object) -> None:
        """Remove item from inventory and delete it (single use) or decrement charges."""
        if getattr(item, 'charges', -1) == -1:
            if getattr(item, 'in_actor', None):
                item.in_actor.contents.remove(item)
            item.delete()
        elif getattr(item, 'charges', 0) > 0:
            item.charges -= 1
            if item.charges == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"{firstcap(item.art_name)} is now empty.")

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
            actual_heal = heal_target.increase_hp(heal_amount)
            if actual_heal > 0:
                effects_applied.append(f"healed {actual_heal} HP")
        
        # Mana restoration
        if item.mana_restore > 0 and heal_target.max_mana > 0:
            actual_restore = heal_target.increase_mana(item.mana_restore)
            if actual_restore > 0:
                effects_applied.append(f"restored {actual_restore} mana")
        
        # Stamina restoration
        if item.stamina_restore > 0 and heal_target.max_stamina > 0:
            actual_restore = heal_target.increase_stamina(item.stamina_restore)
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

        await cls._consume_item(actor, item)


    async def cmd_quaff(cls, actor: Actor, input: str, drink_verb: str = "quaff"):
        """Drink a potion or other drinkable (checks ON_USE first; potions without trigger use consumable logic)."""
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Quaff what?" if drink_verb == "quaff" else "Drink what?")
            return
        
        item = cls._game_state.find_target_object(input, actor=actor)
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{input}'.")
            return
        
        if TriggerType.ON_USE in item.triggers_by_type:
            await actor.send_text(CommTypes.DYNAMIC, f"You {drink_verb} {item.art_name}.")
            await cls._fire_on_use(actor, item, None, 'drink')
            # Consume potion/consumable even when ON_USE fired (e.g. god potion)
            if item.object_flags.are_flags_set(ObjectFlags.IS_POTION) or item.object_flags.are_flags_set(ObjectFlags.IS_CONSUMABLE):
                await cls._consume_item(actor, item)
            return
        if item.object_flags.are_flags_set(ObjectFlags.IS_POTION):
            await cls._use_consumable(actor, item)
            return
        await actor.send_text(CommTypes.DYNAMIC, f"You can't {drink_verb} {item.art_name}.")


    async def cmd_drink(cls, actor: Actor, input: str):
        """Alias for quaff; emits 'You drink X.' then runs ON_USE or consumable logic."""
        await cls.cmd_quaff(actor, input, drink_verb="drink")

    async def cmd_read(cls, actor: Actor, input: str):
        """Read a scroll or other readable; emits 'You read X.' then fires ON_USE (use_type=read)."""
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Read what?")
            return
        item = cls._game_state.find_target_object(input, actor=actor, start_room=actor.location_room)
        if item is None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have '{input}'.")
            return
        if TriggerType.ON_USE in item.triggers_by_type:
            await actor.send_text(CommTypes.DYNAMIC, f"You read {item.art_name}.")
            await cls._fire_on_use(actor, item, None, 'read')
            # Consume scroll/consumable after reading (same as drink)
            if item.object_flags.are_flags_set(ObjectFlags.IS_CONSUMABLE):
                await cls._consume_item(actor, item)
            return
        await actor.send_text(CommTypes.DYNAMIC, f"There's nothing of interest to read on {item.art_name}.")

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
        item = cls._game_state.find_target_object(item_name, actor=actor)
        
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
        item = cls._game_state.find_target_object(input, actor=actor)
        
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
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Make whom admin?")
            return
            
        # Find the target character
        target = cls._game_state.find_target_character(actor, input)
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Could not find that character.")
            return
            
        # Replace target's game permission flags with admin (set, not add)
        target.game_permission_flags = GamePermissionFlags.IS_ADMIN

        # Notify the player
        await actor.send_text(CommTypes.DYNAMIC, f"Made {target.art_name} an admin.")
        await target.send_text(CommTypes.DYNAMIC, "You have been granted admin privileges.")

    async def cmd_possess(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_possess()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
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
        # Resolve target room (use current zone if actor is in a room, else search world)
        start_zone = actor.location_room.zone if getattr(actor, 'location_room', None) and actor.location_room else None
        target = cls._game_state.find_target_room(actor, pieces[0], start_zone)
        if target is None:
            await actor.send_text(CommTypes.DYNAMIC, "Go to where?")
            return
        # If already in a room, remove from it first so arrive_room can place the actor
        old_room = getattr(actor, 'location_room', None)
        if old_room:
            old_room.remove_character(actor)
            actor.location_room = None
        await CoreActionsInterface.get_instance().arrive_room(actor, target, old_room)


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
        
        # Privileged "force" argument: auto-succeed flee (only for non-PCs, e.g. NPCs/scripts)
        tokens = (input or "").strip().lower().split()
        force_flee = "force" in tokens and not actor.has_perm_flags(PermanentCharacterFlags.IS_PC)
        
        if not force_flee:
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
            target = cls._game_state.find_target_object(pieces[0], actor=actor)
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

        # Send to DYNAMIC only so the response appears in the console under "> i"
        await actor.send_text(CommTypes.DYNAMIC, msg)
        
        if not target.contents:
            await actor.send_text(CommTypes.DYNAMIC, "    Nothing.")
            return
            
        # Recursive helper function to display container contents
        async def display_container_contents(container, indent_level=0):
            indent = "    " * indent_level
            
            for item in container.contents:
                # Check if item is a container with contents
                if hasattr(item, "contents") and item.contents:
                    await actor.send_text(CommTypes.DYNAMIC, f"{indent}{item.art_name}, containing:")
                    await display_container_contents(item, indent_level + 1)
                else:
                    await actor.send_text(CommTypes.DYNAMIC, f"{indent}{item.art_name}")
        
        # Display top-level inventory
        await display_container_contents(target, 1)


    async def cmd_at(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_at()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_room(actor, pieces[0], actor.location_room.zone)
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        await CoreActionsInterface.get_instance().arrive_room(actor, target)

    async def cmd_get(cls, actor: Actor, input: str):
        """
        Get an item from the room or from a container.
        
        Usage:
            get <item>              - Get item from room floor
            get all                 - Get all takeable items from room
            get all from <container> - Get all takeable items from a container
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
            # "get sword from chest" or "get all from chest"
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
        
        if item_keyword.lower() == "all":
            # Get all takeable items (from room or container)
            from .nondb_models.objects import Corpse
            if container:
                if not container.has_flags(ObjectFlags.IS_CONTAINER):
                    await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is not a container.")
                    return
                if container.has_flags(ObjectFlags.IS_CLOSED):
                    await actor.send_text(CommTypes.DYNAMIC, f"{container.art_name_cap} is closed.")
                    return
                if isinstance(container, Corpse) and not container.can_be_looted_by(actor):
                    await actor.send_text(CommTypes.DYNAMIC, f"You cannot loot {container.art_name}.")
                    return
                source_list = list(container.contents)
            else:
                source_list = list(actor.location_room.contents)
            takeable = [
                obj for obj in source_list
                if not (hasattr(obj, 'has_flags') and obj.has_flags(ObjectFlags.NO_TAKE))
            ]
            if not takeable:
                if container:
                    await actor.send_text(CommTypes.DYNAMIC, f"There's nothing to take in {container.art_name}.")
                else:
                    await actor.send_text(CommTypes.DYNAMIC, "There's nothing here to take.")
                return
            names = []
            for target in takeable:
                if TriggerType.ON_GET in target.triggers_by_type:
                    get_vars = set_vars(target, actor, actor, target.name)
                    for trigger in target.triggers_by_type[TriggerType.ON_GET]:
                        await trigger.run(target, target.id, get_vars, cls._game_state)
                if container:
                    container.contents.remove(target)
                else:
                    target.location_room.remove_object(target)
                actor.add_to_inventory(target)
                names.append(article_plus_name(getattr(target, 'article', None), target.name))
            name_list = ", ".join(names)
            if container:
                await actor.send_text(CommTypes.DYNAMIC, f"You get {name_list} from {container.art_name}.")
                msg = f"{actor.art_name_cap} gets {name_list} from {container.art_name}."
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"You get {name_list}.")
                msg = f"{actor.art_name_cap} gets {name_list}."
            vars = set_vars(actor, actor, None, msg)
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls._game_state)
            return
        
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
            target = cls._game_state.find_target_object(item_keyword, search_list=container.contents)
            
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
        return cls._game_state.find_target_object(keyword, actor=actor, start_room=actor.location_room)


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
        item = cls._game_state.find_target_object(item_keyword, actor=actor)
        
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
        container.add_object(item)
        
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
        target = cls._game_state.find_target_object(pieces[0], actor=actor)
        
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
        target = cls._game_state.find_target_object(pieces[0], actor=actor)
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
        target = cls._game_state.find_target_object(pieces[0], actor=actor)
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
        """Privileged: set or show log level. Usage: setloglevel [debug|info|warn|warning|error|crit|critical]. No arg = show current."""
        logger = StructuredLogger(__name__, prefix="cmd_setloglevel()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        loglevels = {
            "debug": logging.DEBUG,
            "debug1": logging.DEBUG,
            "debug2": logging.DEBUG,
            "debug3": logging.DEBUG,
            "info": logging.INFO,
            "warn": logging.WARNING,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "crit": logging.CRITICAL,
            "critical": logging.CRITICAL,
        }
        arg = (input or "").strip().lower()
        if not arg:
            current = logging.getLogger().getEffectiveLevel()
            level_name = logging.getLevelName(current)
            await actor.send_text(CommTypes.DYNAMIC, f"Log level is {level_name}.")
            return
        word = arg.split()[0]
        if word not in loglevels:
            await actor.send_text(CommTypes.DYNAMIC, "Use: debug, info, warn, error, or crit (or setloglevel with no arg to see current).")
            return
        logger.info(f"set log level to {word}")
        logger.setLevel(loglevels[word])
        await actor.send_text(CommTypes.DYNAMIC, f"Log level set to {word}.")


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
            logger.warning(f"({pieces}) Delete {target_name} var on what kind of target?")
            await actor.send_text(CommTypes.DYNAMIC, f"Delete {target_name} var on what kind of target?")
            return
        if pieces[0].lower() != "char":
            logger.warning(f"({pieces}) Only character targets allowed at the moment.")
            await actor.send_text(CommTypes.DYNAMIC, "Only character targets allowed at the moment.")
            return
        if len(pieces) < 2:
            logger.warning(f"({pieces}) Delete {target_name} var on whom?")
            await actor.send_text(CommTypes.DYNAMIC, f"Delete {target_name} var on whom?")
            return
        if len(pieces) < 3:
            logger.warning(f"({pieces}) Delete which {target_name} var?")
            await actor.send_text(CommTypes.DYNAMIC, "Delete which temp var?")
            return
        target = cls._game_state.find_target_character(actor, pieces[1], search_world=True)
        if target == None:
            logger.warning(f"({pieces}) Could not find target.")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
            return
        logger.debug3(f"target.name: {target.name}, {target_name} delete var: {pieces[2]}")
        del target_dict_fn(target)[pieces[2]]
        await actor.send_text(CommTypes.DYNAMIC, f"Deleted {target_name} var {pieces[2]} on {target.name}")


    async def cmd_deltempvar(cls, actor: Actor, input: str):
        await cls.cmd_delvar_helper(actor, input, lambda d : d.temp_variables, "temp")

    async def cmd_delpermvar(cls, actor: Actor, input: str):
        await cls.cmd_delvar_helper(actor, input, lambda d : d.perm_variables, "perm")

    async def cmd_showvars(cls, actor: Actor, input: str):
        """
        Show permanent and temporary variables on a character or object.
        Usage: showvars [target]
        If target is omitted, shows variables on yourself. Target can be a character or object name.
        """
        logger = StructuredLogger(__name__, prefix="cmd_showvars()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input!r}")
        target_name = (input or "").strip()
        if not target_name or target_name.lower() == "me":
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, target_name, search_world=True)
            if not target:
                target = cls._game_state.find_target_object(target_name, actor, search_world=True)
            if not target:
                await actor.send_text(CommTypes.DYNAMIC, "Target not found.")
                return
        perm = getattr(target, "perm_variables", None) or {}
        temp = getattr(target, "temp_variables", None) or {}
        await actor.send_text(CommTypes.DYNAMIC, "permanent vars:")
        for k, v in sorted(perm.items()):
            await actor.send_text(CommTypes.DYNAMIC, f"  {k} = {v!r}")
        await actor.send_text(CommTypes.DYNAMIC, "temporary vars:")
        for k, v in sorted(temp.items()):
            await actor.send_text(CommTypes.DYNAMIC, f"  {k} = {v!r}")

    async def cmd_debug(cls, actor: Actor, input: str):
        """
        Toggle or list debug sections. Usage: debug [name] | debug -name
        With no args: show active debugs (with player who toggled), then all available sections.
        With name: turn that section ON. With -name: turn it OFF.
        """
        arg = (input or "").strip()
        valid_names = {s["name"] for s in cls.DEBUG_SECTIONS}
        if not arg:
            # Show currently active (name -> playername), then all available
            active = cls._game_state.active_debug
            if active:
                parts = [f"{name} ({player})" for name, player in sorted(active.items())]
                await actor.send_text(CommTypes.DYNAMIC, "Currently active debug sections: " + ", ".join(parts))
            else:
                await actor.send_text(CommTypes.DYNAMIC, "Currently active debug sections: none")
            await actor.send_text(CommTypes.DYNAMIC, "Available debug sections:")
            for s in cls.DEBUG_SECTIONS:
                await actor.send_text(CommTypes.DYNAMIC, f"  {s['name']}: {s['description']}")
            return
        turn_off = arg.startswith("-")
        name = arg[1:].strip() if turn_off else arg
        if name not in valid_names:
            await actor.send_text(CommTypes.DYNAMIC, f"Unknown debug section: {name}. Use 'debug' with no args to see available sections.")
            return
        if turn_off:
            cls._game_state.active_debug.pop(name, None)
            await actor.send_text(CommTypes.DYNAMIC, f"Debug {name} turned OFF.")
        else:
            if name in cls._game_state.active_debug:
                existing_player = cls._game_state.active_debug[name]
                await actor.send_text(CommTypes.DYNAMIC, f"{existing_player} is already debugging {name}.")
            else:
                cls._game_state.active_debug[name] = actor.name
                await actor.send_text(CommTypes.DYNAMIC, f"Debug {name} turned ON.")

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
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
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
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)
        actor.set_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        

    async def cmd_rest(cls, actor: Actor, input: str):
        """Rest (currently same as sit; separate command for future rest-specific logic)."""
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can rest.")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            await actor.send_text(CommTypes.DYNAMIC, "You're already resting.")
            return
        if any(actor.get_character_states_by_type(CharacterStateForcedSleeping)):
            msg = f"You can't rest right now."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), game_state=cls._game_state)
            return
        if actor.fighting_whom is not None:
            await actor.send_text(CommTypes.DYNAMIC, "You can't rest while fighting!")
            return

        actor.is_meditating = False

        await actor.send_text(CommTypes.DYNAMIC, "You rest.")
        msg = f"{firstcap(actor.name)} rests."
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
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
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
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
        await actor.location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)


    @classmethod
    def _leaverandom_resolve_destination_room(cls, actor: Actor, direction: str):
        """Resolve an exit direction to the destination Room, or None if invalid."""
        room = actor.location_room
        if not room or direction not in room.exits:
            return None
        dest = room.exits[direction].destination
        if "." in dest:
            zone_id, room_id = dest.split(".", 1)
        else:
            zone_id = room.zone.id if room.zone else None
            room_id = dest
        if not zone_id or not room_id:
            return None
        try:
            zone = cls._game_state.get_zone_by_id(zone_id)
            return zone.rooms.get(room_id)
        except (KeyError, AttributeError):
            return None

    @classmethod
    def _leaverandom_room_matches_spec(cls, room, spec, current_zone_id: str) -> bool:
        """Return True if room matches the filter spec. spec is (zone_id,) or (zone_id, subzone_id) or (zone_id, subzone_id, room_id)."""
        if not room or not room.zone:
            return False
        if spec[0] == "stayinzone":
            spec = (current_zone_id,)
        if len(spec) == 1:
            return room.zone.id == spec[0]
        if len(spec) == 2:
            return room.zone.id == spec[0] and getattr(room, "subzone_id", None) == spec[1]
        if len(spec) == 3:
            return (
                room.zone.id == spec[0]
                and getattr(room, "subzone_id", None) == spec[1]
                and room.id == spec[2]
            )
        return False

    async def cmd_leaverandom(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_leaverandom()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if (actor.fighting_whom != None):
            await actor.send_text(CommTypes.DYNAMIC, "You can't leave while fighting!")
            return
        
        if actor.location_room is None:
            await actor.send_text(CommTypes.DYNAMIC, "You are not in a room.")
            return

        valid_directions = list(actor.location_room.exits.keys())
        current_zone_id = actor.location_room.zone.id if actor.location_room.zone else None

        # Optional: comma-separated list of selectors (each type may be repeated).
        # Three selector types: zone_id (any room in zone); zone_id.subzone_id (any room in that subzone);
        # zone_id.subzone_id.room_id (that specific room). Acceptable exits match any selector.
        if input and input.strip():
            raw = [s.strip() for s in input.split(",") if s.strip()]
            specs = []
            for s in raw:
                if s.lower() == "stayinzone":
                    specs.append(("stayinzone",))
                else:
                    parts = s.split(".")
                    if 1 <= len(parts) <= 3:
                        specs.append(tuple(parts))
            if specs:
                filtered = []
                for direction in valid_directions:
                    dest_room = cls._leaverandom_resolve_destination_room(actor, direction)
                    if dest_room and any(
                        cls._leaverandom_room_matches_spec(dest_room, spec, current_zone_id)
                        for spec in specs
                    ):
                        filtered.append(direction)
                valid_directions = filtered

        logger.debug3("valid_exits: " + str(valid_directions))
        num_exits = len(valid_directions)
        if num_exits == 0:
            await actor.send_text(
                CommTypes.DYNAMIC,
                "There are no exits here that match your criteria."
                if input and input.strip() else "There are no exits here."
            )
            return
            
        exit_num = random.randint(0, num_exits - 1)
        chosen = valid_directions[exit_num]
        msg = f"You randomly decide to go {chosen}."
        logger.debug3("msg: " + msg)
        vars = set_vars(actor, actor, None, msg)
        await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        await CoreActionsInterface.get_instance().world_move(actor, chosen)
        
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
            await CoreActionsInterface.get_instance().do_look_room(actor, actor.location_room)
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
        """
        Command a creature to do something. Non-admins can only command followers (charmed by you).
        Admins can command any character. Privileged commands are never allowed via command.

        Usage: command <target> <action>

        Examples:
            command zombie kill orc
            command zombie follow me
        """
        logger = StructuredLogger(__name__, prefix="cmd_command()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")

        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: command <target> <action>")
            return

        pieces = split_preserving_quotes(input)
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: command <target> <action>")
            return

        target_name = pieces[0]
        command = ' '.join(pieces[1:])

        target = cls._game_state.find_target_character(actor, target_name)
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find '{target_name}'.")
            return

        # Non-admins can only command creatures that are charmed by them
        is_admin = hasattr(actor, 'has_game_flags') and actor.has_game_flags(GamePermissionFlags.IS_ADMIN)
        if not is_admin:
            if not hasattr(target, 'charmed_by') or target.charmed_by != actor:
                await actor.send_text(CommTypes.DYNAMIC, f"{target.art_name_cap} is not under your control!")
                return

        # Privileged commands are never allowed via command (check all semicolon-separated sub-commands)
        sub_commands = [c.strip() for c in command.split(';') if c.strip()]
        for sub in sub_commands:
            cmd_name = sub.split(None, 1)[0].lower() if sub else ""
            if cmd_name and cmd_name in cls.privileged_commands:
                await actor.send_text(CommTypes.DYNAMIC, f"You cannot command {target.art_name} to do that!")
                logger.debug(f"Blocked privileged command '{cmd_name}' via command")
                return

        # Notify the actor and room
        if is_admin and (not hasattr(target, 'charmed_by') or target.charmed_by != actor):
            await actor.send_text(CommTypes.DYNAMIC, f"Forcing {target.art_name} to: {command}")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"You command {target.art_name} to '{command}'.")
            msg = f"{actor.art_name_cap} commands {target.art_name}."
            await actor.location_room.echo(CommTypes.DYNAMIC, msg, vars=None, exceptions=[actor], game_state=cls._game_state)

        await cls.process_command(target, command, {})

    async def cmd_stop(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_stop()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.command_queue:
            num_commands = len(actor.command_queue)
            actor.command_queue.clear()
            await actor.send_text(CommTypes.DYNAMIC, f"Stopped {num_commands} queued command(s).")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "You have no queued commands to stop.")

    # Direction abbreviation mapping for route output
    DIRECTION_ABBREV = {
        'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W',
        'up': 'U', 'down': 'D', 'in': 'IN', 'out': 'OUT',
        'n': 'N', 's': 'S', 'e': 'E', 'w': 'W', 'u': 'U', 'd': 'D'
    }

    def find_path(cls, start_room: Room, target_room: Room) -> List[str]:
        """Find the shortest path between two rooms using breadth-first search."""
        if start_room == target_room:
            return []
            
        # Keep track of visited rooms and the direction taken to reach them
        # visited[room] = (parent_room, direction_from_parent)
        visited = {start_room: (None, None)}
        queue = [start_room]
        
        while queue:
            current = queue.pop(0)
            
            # Check all exits from current room
            for direction, exit_obj in current.exits.items():
                dest_id = exit_obj.destination
                if "." in dest_id:
                    zone_id, room_id = dest_id.split(".", 1)
                else:
                    zone_id = current.zone.id
                    room_id = dest_id
                
                zone = cls._game_state.get_zone_by_id(zone_id)
                if not zone or room_id not in zone.rooms:
                    continue  # Skip invalid destinations
                    
                next_room = zone.rooms[room_id]
                
                if next_room == target_room:
                    # Found the target, reconstruct the path
                    path = [direction]
                    while visited[current][0] is not None:
                        parent, dir_from_parent = visited[current]
                        path.append(dir_from_parent)
                        current = parent
                    return list(reversed(path))
                    
                if next_room not in visited:
                    visited[next_room] = (current, direction)
                    queue.append(next_room)
        
        return None  # No path found
    
    def get_route_string(cls, path: List[str]) -> str:
        """Convert a path list to abbreviated direction string like 'E E S D E N U'."""
        if not path:
            return ""
        abbrevs = []
        for direction in path:
            abbrev = cls.DIRECTION_ABBREV.get(direction.lower(), direction.upper())
            abbrevs.append(abbrev)
        return " ".join(abbrevs)

    async def cmd_route(cls, actor: Actor, input: str):
        """
        Find and display the route to a target.
        
        This is a privileged/NPC command.
        
        Usage: route <target>
        
        Target can be:
        - An NPC name
        - An object name (in any room)
        - A room name or ID
        
        Output is a string of abbreviated directions like "E E S D E N U"
        """
        logger = StructuredLogger(__name__, prefix="cmd_route()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Route to what?")
            return
            
        # Try to find target in order: characters, objects, rooms
        target = cls._game_state.find_target_character(actor, input, search_world=True)
        if not target:
            target = cls._game_state.find_target_object(input, actor, search_world=True)
        if not target and actor.location_room and actor.location_room.zone:
            target = cls._game_state.find_target_room(actor, input, actor.location_room.zone)
            
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Target can't be found.")
            return
            
        # Get the target's room
        target_room = target.location_room if hasattr(target, 'location_room') else target
        
        if target_room == actor.location_room:
            await actor.send_text(CommTypes.DYNAMIC, "You are already there.")
            return
        
        # Find path to target
        path = cls.find_path(actor.location_room, target_room)
        if path is None:
            await actor.send_text(CommTypes.DYNAMIC, "No route exists.")
            return
            
        # Output abbreviated route
        route_str = cls.get_route_string(path)
        await actor.send_text(CommTypes.DYNAMIC, route_str)

    async def cmd_walkto(cls, actor: Actor, input: str):
        """
        Find a path to a target and queue movement commands to walk there.
        
        This is a privileged/NPC command.
        
        Usage: walkto <target>
        
        Target can be:
        - An NPC name
        - An object name (in any room)
        - A room name or ID
        """
        logger = StructuredLogger(__name__, prefix="cmd_walkto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Walk to what?")
            return
            
        # Try to find target in order: characters, objects, rooms
        target = cls._game_state.find_target_character(actor, input, search_world=True)
        if not target:
            target = cls._game_state.find_target_object(input, actor, search_world=True)
        if not target and actor.location_room and actor.location_room.zone:
            target = cls._game_state.find_target_room(actor, input, actor.location_room.zone)
            
        if not target:
            await actor.send_text(CommTypes.DYNAMIC, "Target can't be found.")
            return
            
        # Get the target's room
        target_room = target.location_room if hasattr(target, 'location_room') else target
        
        if target_room == actor.location_room:
            await actor.send_text(CommTypes.DYNAMIC, "You are already there.")
            return
        
        # Find path to target
        path = cls.find_path(actor.location_room, target_room)
        if path is None:
            await actor.send_text(CommTypes.DYNAMIC, "No route exists.")
            return
            
        # Queue the movement commands
        for direction in path:
            actor.command_queue.append(direction)
        
        route_str = cls.get_route_string(path)
        await actor.send_text(CommTypes.DYNAMIC, f"Walking: {route_str}")

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
        delay_cooldown.start(cls._game_state.get_current_tick(), 0, 
                           cls._game_state.get_current_tick() + delay_ticks)
        
        if rounded_ms != delay_ms:
            await actor.send_text(CommTypes.DYNAMIC, f"Delaying for {rounded_ms} milliseconds (rounded from {delay_ms}ms).")
        else:
            await actor.send_text(CommTypes.DYNAMIC, f"Delaying for {delay_ms} milliseconds.")

    async def cmd_skills(cls, actor: Actor, input: str):
        """Show skills for the character, organized by class with level progression."""
        from .skills_core import SkillsRegistry, Skills
        logger = StructuredLogger(__name__, prefix="cmd_skills()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters have skills.")
            return
        
        target = actor
        lines = []
        
        # Header
        lines.append("=== Your Skills ===")
        lines.append(f"Skill Points Available: {target.skill_points_available}")
        lines.append(f"Skill caps increase as you level up (shown as current/cap)")
        lines.append("")
        
        # Show skills by class
        has_skills = False
        for role in target.class_priority:
            class_name = target.get_display_class_name(role)
            class_level = target.levels_by_role.get(role, 0)
            lines.append(f"--- {class_name.title()} (Level {class_level}) ---")
            
            # Get all skills from the registry for this class
            role_name = role.name.lower()
            all_class_skills = SkillsRegistry.get_class_skills(role_name)
            
            if not all_class_skills:
                lines.append("  No skills defined for this class.")
                lines.append("")
                continue
            
            has_skills = True
            
            # Get skill class for level requirements
            skill_class = target._get_skill_class_for_role(role)
            
            # Build list of (skill_name, display_name, level_req, current_points)
            skill_info = []
            for skill_key, skill in all_class_skills.items():
                normalized_name = skill_key.lower().replace(' ', '_').replace('-', '_')
                
                # Get level requirement
                level_req = 1
                if skill_class is not None:
                    try:
                        level_req = skill_class.get_level_requirement(skill_class, skill_key)
                    except Exception:
                        pass
                
                # Get current points (0 if not unlocked or not trained)
                current_points = 0
                if role in target.skill_levels_by_role and normalized_name in target.skill_levels_by_role[role]:
                    current_points = target.skill_levels_by_role[role][normalized_name]
                
                # Use original skill name for display
                display_name = skill.name if hasattr(skill, 'name') else normalized_name.replace('_', ' ').title()
                
                skill_info.append((normalized_name, display_name, level_req, current_points))
            
            # Sort by level requirement (low to high), then by current points (high to low), then alphabetically
            skill_info.sort(key=lambda x: (x[2], -x[3], x[1].lower()))
            
            # Group skills by tier for cleaner display
            current_tier = None
            tier_names = {
                Skills.TIER1_MIN_LEVEL: "Tier 1 (Level 1-9)",
                Skills.TIER2_MIN_LEVEL: "Tier 2 (Level 10-19)",
                Skills.TIER3_MIN_LEVEL: "Tier 3 (Level 20-29)",
                Skills.TIER4_MIN_LEVEL: "Tier 4 (Level 30-39)",
                Skills.TIER5_MIN_LEVEL: "Tier 5 (Level 40-49)",
                Skills.TIER6_MIN_LEVEL: "Tier 6 (Level 50-59)",
                Skills.TIER7_MIN_LEVEL: "Tier 7 (Level 60)",
            }
            
            def get_tier(level_req):
                if level_req >= Skills.TIER7_MIN_LEVEL:
                    return Skills.TIER7_MIN_LEVEL
                elif level_req >= Skills.TIER6_MIN_LEVEL:
                    return Skills.TIER6_MIN_LEVEL
                elif level_req >= Skills.TIER5_MIN_LEVEL:
                    return Skills.TIER5_MIN_LEVEL
                elif level_req >= Skills.TIER4_MIN_LEVEL:
                    return Skills.TIER4_MIN_LEVEL
                elif level_req >= Skills.TIER3_MIN_LEVEL:
                    return Skills.TIER3_MIN_LEVEL
                elif level_req >= Skills.TIER2_MIN_LEVEL:
                    return Skills.TIER2_MIN_LEVEL
                else:
                    return Skills.TIER1_MIN_LEVEL
            
            for normalized_name, display_name, level_req, current_points in skill_info:
                tier = get_tier(level_req)
                if tier != current_tier:
                    current_tier = tier
                    lines.append(f"  [{tier_names.get(tier, f'Level {tier}+')}]")
                
                # Calculate current skill cap for this skill
                skill_cap = target.get_skill_cap(normalized_name, role)
                
                # Determine status/display
                is_locked = class_level < level_req
                if is_locked:
                    status = f"[Locked - Lvl {level_req}]"
                elif current_points == 0:
                    status = f"0/{skill_cap}"
                elif current_points >= Constants.MAX_SKILL_LEVEL:
                    status = f"{current_points} pts [MASTERED]"
                elif current_points >= skill_cap:
                    status = f"{current_points}/{skill_cap} [CAPPED]"
                else:
                    status = f"{current_points}/{skill_cap}"
                
                lines.append(f"    {display_name:28} {status:>18}")
            
            lines.append("")
        
        if not has_skills:
            lines.append("You have no class with skills yet.")
        
        # Footer with usage hint
        if target.skill_points_available > 0:
            lines.append("Use 'skillup <skill> [points]' to improve a skill.")
        
        await actor.send_text(CommTypes.STATIC, "\n".join(lines))

    async def cmd_level(cls, actor: Actor, input: str):
        """Show level and XP status."""
        from .constants import Constants, CharacterClassRole
        from .handlers.level_up_handler import LevelUpHandler
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters have levels.")
            return
        
        target = actor
        total_level = target.total_levels()
        
        lines = [
            "=== Character Level Status ===",
            f"Total Level: {total_level} / {Constants.MAX_LEVEL}",
            f"Experience: {target.experience_points:,} XP"
        ]
        
        # Show XP needed for next level
        if total_level < Constants.MAX_LEVEL:
            next_level_xp = Constants.XP_PROGRESSION[total_level]
            xp_needed = next_level_xp - target.experience_points
            if xp_needed > 0:
                lines.append(f"XP to next level: {xp_needed:,}")
            else:
                lines.append("Ready to level up!")
        else:
            lines.append("Maximum level reached!")
        
        lines.append("")
        
        # Add class breakdown
        lines.append("Class Levels:")
        for role in target.class_priority:
            class_name = target.get_display_class_name(role)
            level = target.levels_by_role[role]
            lines.append(f"  {class_name.title()}: Level {level}")
        
        # Show multiclass option
        if len(target.class_priority) < target.max_class_count:
            available_classes = []
            for base_class in CharacterClassRole.get_base_classes():
                if base_class not in target.class_priority:
                    available_classes.append(CharacterClassRole.field_name(base_class).title())
            if available_classes:
                lines.append("")
                lines.append(f"Multiclass available ({target.max_class_count - len(target.class_priority)} slot(s)):")
                lines.append(f"  Available: {', '.join(available_classes)}")
        
        # Show combat stats
        lines.append("")
        lines.append("Combat Stats:")
        lines.append(f"  Hit Chance: {target.hit_modifier}%")
        lines.append(f"  Dodge: +{target.dodge_modifier}")
        if target.spell_power > 0:
            lines.append(f"  Spell Power: {target.spell_power}")
        
        # Show saving throws (class-based system)
        lines.append("")
        lines.append("Saving Throws (Base + Attribute):")
        fort_base = target.get_class_base_save("fortitude")
        ref_base = target.get_class_base_save("reflex")
        will_base = target.get_class_base_save("will")
        fort_attr = target.get_save_attribute("fortitude")
        ref_attr = target.get_save_attribute("reflex")
        will_attr = target.get_save_attribute("will")
        lines.append(f"  Fortitude: {fort_base}% base (CON: {fort_attr})")
        lines.append(f"  Reflex: {ref_base}% base (DEX: {ref_attr})")
        lines.append(f"  Will: {will_base}% base (WIS: {will_attr})")
        
        lines.append("")
        lines.append(f"Skill Points Available: {target.skill_points_available}")
        
        # Show attribute points if any
        if target.unspent_attribute_points > 0:
            lines.append(f"Attribute Points Available: {target.unspent_attribute_points}")
            lines.append("Use 'improvestat <attribute>' to spend them.")
        
        # Check for available level-ups
        if target.can_level():
            if target.has_unspent_skill_points():
                lines.append("")
                lines.append(f"You have {target.skill_points_available} unspent skill points!")
                lines.append("Use 'skillup <skill> <points>' to spend them before leveling up.")
            else:
                lines.append("")
                lines.append("You have enough experience to advance a level!")
                lines.append("Use 'levelup <class>' to level up.")
        
        # Check for available specializations
        available_specs = LevelUpHandler.get_available_specializations(target)
        if available_specs:
            lines.append("")
            lines.append("Specialization available for:")
            for base_class, specializations in available_specs.items():
                from .constants import CharacterClassRole
                base_name = CharacterClassRole.field_name(base_class)
                spec_names = [CharacterClassRole.field_name(spec).title() for spec in specializations]
                lines.append(f"  {base_name.title()}: {', '.join(spec_names)}")
            lines.append("Use 'specialize <class> <specialization>' to choose.")
        
        await actor.send_text(CommTypes.STATIC, "\n".join(lines))

    async def cmd_levelup(cls, actor: Actor, input: str):
        """Level up a class."""
        from .constants import CharacterClassRole
        from .handlers.level_up_handler import LevelUpHandler
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can level up.")
            return
        
        args = split_preserving_quotes(input) if input else []
        
        if not args:
            # If only one class, level that one automatically
            if len(actor.class_priority) == 1:
                role = actor.class_priority[0]
            else:
                class_names = [CharacterClassRole.field_name(r).title() for r in actor.class_priority]
                await actor.send_text(CommTypes.DYNAMIC, f"Usage: levelup <class>")
                await actor.send_text(CommTypes.DYNAMIC, f"Your classes: {', '.join(class_names)}")
                return
        else:
            class_name = args[0].upper()
            try:
                role = CharacterClassRole[class_name]
            except KeyError:
                await actor.send_text(CommTypes.DYNAMIC, f"Unknown class: {args[0]}")
                return
        
        success, message = LevelUpHandler.handle_level_up(actor, role)
        await actor.send_text(CommTypes.DYNAMIC, message)
        
        # Send status update if successful
        if success:
            await actor.send_status_update()

    async def cmd_skillup(cls, actor: Actor, input: str):
        """Spend skill points to improve a skill."""
        from .handlers.level_up_handler import LevelUpHandler
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can improve skills.")
            return
        
        args = split_preserving_quotes(input) if input else []
        
        if len(args) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: skillup <skill> [points]")
            await actor.send_text(CommTypes.DYNAMIC, f"You have {actor.skill_points_available} skill points available.")
            await actor.send_text(CommTypes.DYNAMIC, "Use 'skills' to see your available skills.")
            return
        
        # Parse skill name and points
        # Last argument might be a number (points to spend)
        points = 1  # Default to 1 point
        skill_parts = args[:]
        
        if len(args) >= 2 and args[-1].isdigit():
            points = int(args[-1])
            skill_parts = args[:-1]
        
        skill_name = ' '.join(skill_parts)
        
        success, message = LevelUpHandler.handle_skill_up(actor, skill_name, points)
        await actor.send_text(CommTypes.DYNAMIC, message)

    async def cmd_improvestat(cls, actor: Actor, input: str):
        """Spend attribute points to improve a stat (STR, DEX, CON, INT, WIS, CHA)."""
        from .nondb_models.character_interface import CharacterAttributes
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can improve stats.")
            return
        
        if actor.unspent_attribute_points <= 0:
            await actor.send_text(CommTypes.DYNAMIC, "You have no attribute points to spend.")
            await actor.send_text(CommTypes.DYNAMIC, "Attribute points are gained every 10 character levels.")
            return
        
        args = split_preserving_quotes(input) if input else []
        
        if len(args) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: improvestat <attribute>")
            await actor.send_text(CommTypes.DYNAMIC, f"You have {actor.unspent_attribute_points} attribute point(s) available.")
            await actor.send_text(CommTypes.DYNAMIC, "")
            await actor.send_text(CommTypes.DYNAMIC, "Available attributes:")
            await actor.send_text(CommTypes.DYNAMIC, "  STR (Strength)     - Melee damage, carrying capacity")
            await actor.send_text(CommTypes.DYNAMIC, "  DEX (Dexterity)    - Reflex saves, hit chance")
            await actor.send_text(CommTypes.DYNAMIC, "  CON (Constitution) - Fortitude saves, hit points")
            await actor.send_text(CommTypes.DYNAMIC, "  INT (Intelligence) - Spell power (mage)")
            await actor.send_text(CommTypes.DYNAMIC, "  WIS (Wisdom)       - Will saves, healing power")
            await actor.send_text(CommTypes.DYNAMIC, "  CHA (Charisma)     - Social interactions, leadership")
            await actor.send_text(CommTypes.DYNAMIC, "")
            await actor.send_text(CommTypes.DYNAMIC, "Current attributes:")
            for attr in CharacterAttributes:
                value = actor.attributes.get(attr, 10)
                await actor.send_text(CommTypes.DYNAMIC, f"  {attr.name}: {value}")
            return
        
        # Map short names to attributes
        attr_map = {
            "str": CharacterAttributes.STRENGTH,
            "strength": CharacterAttributes.STRENGTH,
            "dex": CharacterAttributes.DEXTERITY,
            "dexterity": CharacterAttributes.DEXTERITY,
            "con": CharacterAttributes.CONSTITUTION,
            "constitution": CharacterAttributes.CONSTITUTION,
            "int": CharacterAttributes.INTELLIGENCE,
            "intelligence": CharacterAttributes.INTELLIGENCE,
            "wis": CharacterAttributes.WISDOM,
            "wisdom": CharacterAttributes.WISDOM,
            "cha": CharacterAttributes.CHARISMA,
            "charisma": CharacterAttributes.CHARISMA,
        }
        
        attr_name = args[0].lower()
        if attr_name not in attr_map:
            await actor.send_text(CommTypes.DYNAMIC, f"Unknown attribute: {args[0]}")
            await actor.send_text(CommTypes.DYNAMIC, "Valid attributes: STR, DEX, CON, INT, WIS, CHA")
            return
        
        attr = attr_map[attr_name]
        old_value = actor.attributes.get(attr, 10)
        new_value = old_value + 1
        
        actor.attributes[attr] = new_value
        actor.unspent_attribute_points -= 1
        
        await actor.send_text(CommTypes.DYNAMIC, f"Your {attr.name} has increased from {old_value} to {new_value}!")
        
        if actor.unspent_attribute_points > 0:
            await actor.send_text(CommTypes.DYNAMIC, f"You have {actor.unspent_attribute_points} attribute point(s) remaining.")
        
        # Recalculate combat bonuses which may be affected by attribute changes
        actor.calculate_combat_bonuses()
        await actor.send_status_update()

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
        
        # XP: total / next level (N more)
        total_level = target.total_levels()
        if total_level < Constants.MAX_LEVEL:
            next_level_xp = Constants.XP_PROGRESSION[total_level]
            xp_more = max(0, next_level_xp - target.experience_points)
            await actor.send_text(CommTypes.STATIC, f"XP: {target.experience_points:,} / {next_level_xp:,} ({xp_more:,} more)")
        else:
            await actor.send_text(CommTypes.STATIC, f"XP: {target.experience_points:,} (max level)")
        if target is actor and target.can_level():
            await actor.send_text(CommTypes.STATIC, 'Type "levelup" to level up.')
        
        # Display equipped items
        await actor.send_text(CommTypes.STATIC, "\n--- Equipment ---")
        has_equipment = False
        for loc in EquipLocation:
            if target.equipped[loc]:
                has_equipment = True
                await actor.send_text(CommTypes.STATIC, f"{loc.name}: {target.equipped[loc].art_name}")
        if not has_equipment:
            await actor.send_text(CommTypes.STATIC, "Nothing equipped")
        
        # Display skills by class
        await actor.send_text(CommTypes.STATIC, "\n--- Skills ---")
        await actor.send_text(CommTypes.STATIC, f"Skill Points: {target.skill_points_available}")
        has_skills = False
        for role in target.class_priority:
            if role not in target.skill_levels_by_role:
                continue
            class_skills = target.skill_levels_by_role[role]
            trained_skills = {k: v for k, v in class_skills.items() if v > 0}
            if trained_skills:
                has_skills = True
                class_name = target.get_display_class_name(role)
                await actor.send_text(CommTypes.STATIC, f"  {class_name.title()}:")
                for skill_name, skill_level in sorted(trained_skills.items()):
                    display_name = skill_name.replace('_', ' ').title()
                    await actor.send_text(CommTypes.STATIC, f"    {display_name:28}: {skill_level:>2}/{Constants.MAX_SKILL_LEVEL}")
        if not has_skills:
            await actor.send_text(CommTypes.STATIC, "  No trained skills")
        
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


    async def cmd_where(cls, actor: Actor, input: str):
        """where <room|subzone|zone|world> <target name> — list matching characters and objects in scope (privileged).
        Output: article name (id): location_room name (location_room id) [for objects in container/inventory: in article name (id)].
        Always checks both characters and objects; a reference (e.g. guard#4) returns at most one combined result or 'not found'."""
        logger = StructuredLogger(__name__, prefix="cmd_where()> ")
        pieces = split_preserving_quotes((input or "").strip())
        if len(pieces) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: where <room|subzone|zone|world> <target name>")
            return
        scope = pieces[0].lower()
        if scope not in ("room", "subzone", "zone", "world"):
            await actor.send_text(CommTypes.DYNAMIC, "Scope must be room, subzone, zone, or world.")
            return
        target_name = " ".join(pieces[1:])
        if not target_name:
            await actor.send_text(CommTypes.DYNAMIC, "Usage: where <room|subzone|zone|world> <target name>")
            return
        # Parse # for reference (e.g. guard#4 -> first=4, last=4); no # means first=1, last=0 (all)
        first_match, last_match = 1, 0
        if "#" in target_name:
            parts = target_name.split("#", 1)
            try:
                first_match = max(1, int(parts[1]))
                last_match = first_match
            except (ValueError, IndexError):
                pass
        # Always check both characters and objects; get all in scope (no # parsing inside find — we slice after)
        search_name = target_name.split("#")[0] if "#" in target_name else target_name
        chars = cls._game_state.find_target_characters(actor, search_name, first_match=1, last_match=0, search_scope=scope, exclude_initiator=True)
        objs = cls._game_state.find_target_objects(search_name, actor=actor, start_room=getattr(actor, "location_room", None), first_match=1, last_match=0, search_scope=scope)
        # Combined list: characters first, then objects (reference = single index into this list)
        combined = [("char", c, None) for c in chars] + [("obj", o, None) for o in objs]
        if last_match >= 1:
            combined = combined[first_match - 1:last_match] if first_match <= len(combined) else []
        else:
            combined = combined[first_match - 1:] if first_match <= len(combined) else []
        if not combined:
            if first_match > 1 or last_match >= 1:
                await actor.send_text(CommTypes.DYNAMIC, "Not found.")
            else:
                await actor.send_text(CommTypes.DYNAMIC, f"No matches for '{target_name}' in {scope}.")
            return
        lines = []
        for kind, entity, _ in combined:
            if kind == "char":
                c = entity
                room = getattr(c, "location_room", None)
                if room:
                    rname = getattr(room, "name", "?")
                    rid = getattr(room, "room_full_id", None) or getattr(room, "id", "?")
                    line = f"{c.art_name_cap} ({c.id}): {rname} ({rid})"
                else:
                    line = f"{c.art_name_cap} ({c.id}): (no location)"
                lines.append(line)
            else:
                o = entity
                room = getattr(o, "location_room", None)
                if room:
                    rname = getattr(room, "name", "?")
                    rid = getattr(room, "room_full_id", None) or getattr(room, "id", "?")
                    line = f"{o.art_name_cap} ({o.id}): {rname} ({rid})"
                else:
                    line = f"{o.art_name_cap} ({o.id}): (no location)"
                parent = getattr(o, "in_actor", None)
                if parent is not None and parent != room:
                    parent_art = getattr(parent, "art_name", None) or getattr(parent, "name", "?")
                    parent_id = getattr(parent, "id", None) or getattr(parent, "room_full_id", "?")
                    line += f" in {parent_art} ({parent_id})"
                lines.append(line)
        for line in lines:
            await actor.send_text(CommTypes.DYNAMIC, line)

    async def cmd_status(cls, actor: Actor, input: str):
        """List active character states; emit get_my_status_message() for each, one per line."""
        logger = StructuredLogger(__name__, prefix="cmd_status()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        states = getattr(actor, "states", [])
        messages = []
        for state in states:
            getter = getattr(state, "get_my_status_message", None)
            if callable(getter):
                line = getter()
                if line:
                    messages.append(line)
        if not messages:
            await actor.send_text(CommTypes.DYNAMIC, "You have no active status effects.")
            return
        for line in messages:
            await actor.send_text(CommTypes.DYNAMIC, line)

    async def cmd_self(cls, actor: Actor, input: str):
        """Show detailed information about your character: classes, attributes, resources, and skills."""
        from .nondb_models.character_interface import CharacterAttributes
        
        logger = StructuredLogger(__name__, prefix="cmd_self()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can use this command.")
            return
        
        target = actor
        lines = []
        
        # Header with name
        lines.append(f"===== {target.art_name_cap} =====")
        lines.append("")
        
        # --- Classes Section ---
        lines.append("--- Classes ---")
        total_level = target.total_levels()
        for role in target.class_priority:
            class_name = target.get_display_class_name(role)
            class_level = target.levels_by_role.get(role, 0)
            lines.append(f"  {class_name.title():20} Level {class_level}")
        lines.append(f"  {'Total Level:':20} {total_level}")
        lines.append("")
        
        # --- Attributes Section ---
        lines.append("--- Attributes ---")
        # Define attribute short names for compact display
        attr_display = [
            (CharacterAttributes.STRENGTH, "STR"),
            (CharacterAttributes.DEXTERITY, "DEX"),
            (CharacterAttributes.CONSTITUTION, "CON"),
            (CharacterAttributes.INTELLIGENCE, "INT"),
            (CharacterAttributes.WISDOM, "WIS"),
            (CharacterAttributes.CHARISMA, "CHA"),
        ]
        # Display as two rows for readability
        row1_parts = []
        row2_parts = []
        for attr, abbrev in attr_display:
            value = target.attributes.get(attr, 10)
            modifier = (value - 10) // 2
            sign = "+" if modifier >= 0 else ""
            row1_parts.append(f"{abbrev}: {value:2}")
            row2_parts.append(f"    ({sign}{modifier})")
        
        lines.append("  " + "   ".join(row1_parts))
        lines.append("  " + "   ".join(row2_parts))
        lines.append("")
        
        # --- Resources Section ---
        lines.append("--- Resources ---")
        hp_percent = int((target.current_hit_points / target.max_hit_points) * 100) if target.max_hit_points > 0 else 0
        lines.append(f"  HP:      {target.current_hit_points:4}/{target.max_hit_points:<4} ({hp_percent}%)")
        
        if target.max_mana > 0:
            mana_percent = int((target.current_mana / target.max_mana) * 100) if target.max_mana > 0 else 0
            lines.append(f"  Mana:    {int(target.current_mana):4}/{target.max_mana:<4} ({mana_percent}%)")
        
        if target.max_stamina > 0:
            stamina_percent = int((target.current_stamina / target.max_stamina) * 100) if target.max_stamina > 0 else 0
            lines.append(f"  Stamina: {int(target.current_stamina):4}/{target.max_stamina:<4} ({stamina_percent}%)")
        
        if total_level < Constants.MAX_LEVEL:
            next_level_xp = Constants.XP_PROGRESSION[total_level]
            xp_more = next_level_xp - target.experience_points
            lines.append(f"  XP:      {target.experience_points:,} / {next_level_xp:,} ({xp_more:,} more)")
        else:
            lines.append(f"  XP:      {target.experience_points:,} (max level)")
        lines.append("")
        
        # --- Skills Section ---
        lines.append("--- Known Skills ---")
        lines.append(f"  Skill Points Available: {target.skill_points_available}")
        lines.append("")
        
        has_skills = False
        for role in target.class_priority:
            if role not in target.skill_levels_by_role:
                continue
            class_skills = target.skill_levels_by_role[role]
            # Show all known skills (level > 0 means trained)
            known_skills = {k: v for k, v in class_skills.items() if v > 0}
            
            if known_skills:
                has_skills = True
                class_name = target.get_display_class_name(role)
                class_level = target.levels_by_role.get(role, 0)
                lines.append(f"  [{class_name.title()} - Level {class_level}]")
                
                # Sort skills alphabetically
                for skill_name, skill_level in sorted(known_skills.items()):
                    display_name = skill_name.replace('_', ' ').title()
                    lines.append(f"    {display_name:25} {skill_level:>2}/{Constants.MAX_SKILL_LEVEL}")
                lines.append("")
        
        if not has_skills:
            lines.append("  No trained skills yet.")
            lines.append("  Use 'skillup <skill> <points>' to train skills.")
            lines.append("")
        
        # Send all lines
        for line in lines:
            await actor.send_text(CommTypes.STATIC, line)

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
                target = cls._game_state.find_target_room(actor, target_name, actor.location_room.zone)
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Room '{target_name}' not found.")
                return
        elif target_type in ["obj", "object"]:
            target = cls._game_state.find_target_object(target_name, actor=actor, search_world=True)  # Search world for objects too
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

    async def cmd_showscripts(cls, actor: Actor, input: str):
        """
        Show all scripts attached to a target (room, character, or object).
        Privileged (admin only).
        Usage: showscripts [target_type] [target_name]
        Target: me | here | char <name> | room <name> | obj <name>
        """
        if not actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
            await actor.send_text(CommTypes.DYNAMIC, "What?")
            return
        pieces = split_preserving_quotes(input)
        if not pieces:
            await actor.send_text(CommTypes.STATIC, "Usage: showscripts [target_type] [target_name]")
            await actor.send_text(CommTypes.STATIC, "  Examples: showscripts me | showscripts here | showscripts char Bob | showscripts room tavern | showscripts room zone.room | showscripts room here | showscripts obj chest | showscripts body")
            return
        target_type = pieces[0].lower()
        target_name = pieces[1] if len(pieces) > 1 else None
        # Single-word form: resolve like "look" (character or object in room/world)
        target = None
        if target_type not in ["character", "char", "me", "self", "room", "here", "obj", "object"]:
            if target_name is not None:
                await actor.send_text(CommTypes.STATIC, "Invalid target type. Use: me, here, character/char, room, obj/object")
                return
            # One word that isn't a type: try to resolve as character then object
            target = cls._game_state.find_target_character(actor, target_type)
            if target is None:
                target = cls._game_state.find_target_object(target_type, actor=actor, search_world=True)
            if target is None:
                await actor.send_text(CommTypes.STATIC, f"'{target_type}' not found (try: showscripts obj {target_type} or showscripts char {target_type}).")
                return
            # resolved; fall through to script listing
        else:
            if target_type not in ["me", "self", "here"] and not target_name:
                await actor.send_text(CommTypes.STATIC, "Usage: showscripts <target_type> <target_name>")
                return
        if target is None and target_type in ["character", "char", "me", "self"]:
            if target_type in ["me", "self"]:
                target = actor
            else:
                target = cls._game_state.find_target_character(actor, target_name)
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Character '{target_name or 'me'}' not found.")
                return
        elif target_type in ["room", "here"]:
            if target_type == "here":
                target = actor.location_room
            elif target_name and target_name.strip().lower() == "here":
                target = actor.location_room
            else:
                start_zone = getattr(actor.location_room, "zone", None) if actor.location_room else None
                if start_zone is None and getattr(cls._game_state, "zones", None):
                    start_zone = next(iter(cls._game_state.zones.values()), None)
                target = cls._game_state.find_target_room(actor, target_name, start_zone) if start_zone else None
            if not target:
                await actor.send_text(CommTypes.STATIC, "You are not in a room." if target_type == "here" or (target_name and target_name.strip().lower() == "here") else f"Room '{target_name}' not found.")
                return
        elif target_type in ["obj", "object"]:
            target = cls._game_state.find_target_object(target_name, actor=actor, search_world=True)
            if not target:
                await actor.send_text(CommTypes.STATIC, f"Object '{target_name}' not found.")
                return
        target_triggers = list(itertools.chain.from_iterable(target.triggers_by_type.values()))
        if actor == target:
            await actor.send_text(CommTypes.STATIC, "Scripts on you:")
        else:
            await actor.send_text(CommTypes.STATIC, f"Scripts on {target.art_name_cap}:")
        if not target_triggers:
            await actor.send_text(CommTypes.STATIC, "  None.")
            return
        for trigger in target_triggers:
            state = " (disabled)" if trigger.disabled_ else ""
            await actor.send_text(CommTypes.STATIC, f"  --- {trigger.id} ({trigger.trigger_type_}){state} ---")
            script_lines = (trigger.script_ or "").split("\n")
            if not script_lines or (len(script_lines) == 1 and not script_lines[0].strip()):
                await actor.send_text(CommTypes.STATIC, "    (empty)")
            else:
                for line in script_lines:
                    await actor.send_text(CommTypes.STATIC, f"    {line}")
