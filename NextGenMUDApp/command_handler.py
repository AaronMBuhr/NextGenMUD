import asyncio
from .structured_logger import StructuredLogger
import itertools
import logging
from num2words import num2words
import random
import re
from typing import Callable, List
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

        # normal commands
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
        "tell": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_tell(char, input),
        "emote": lambda command, char,input: CommandHandlerInterface.get_instance().cmd_emote(char, input),
        "look": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "l": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "attack": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "kill": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "inventory": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "inv": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "i": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "get": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_get(char, input),
        "drop": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_drop(char, input),
        "inspect": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inspect(char, input),
        "equip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "eq": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "unequip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_unequip(char, input),
        "stand": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stand(char, input),
        "sit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sit(char, input),
        "sleep": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sleep(char, input),
        "leaverandom": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_leaverandom(char, input),
        "skills": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_skills(char, input),
        "character": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "char": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_character(char, input),
        "triggers": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_triggers(char, input),
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

    async def process_command(cls, actor: Actor, input: str, vars: dict = None):
        logger = StructuredLogger(__name__, prefix="process_command()> ")
        # print(actor)
        logger.debug3(f"processing input for actor {actor.id}: {input}")
        
        # Echo the command back to the user
        await actor.send_text(CommTypes.DYNAMIC, f"> {input}")
        
        if actor.reference_number is None:
            raise Exception(f"Actor {actor.id} has no reference number.")
        if actor.rid in cls.executing_actors:
            for ch in cls.executing_actors:
                logger.critical(f"executing_actors: {ch}")
            logger.error(f"Actor {actor.id} is already executing a command, can't '{input}'.")
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
                                logger.critical(f"checking skills registry for: {first_command}")
                                skill_name, remainder = SkillsRegistry.parse_skill_name_from_input(first_command)
                                if skill_name:  
                                    logger.critical(f"found skill: {skill_name}")
                                    SkillsRegistry.invoke_skill_by_name(cls._game_state, actor, skill_name, remainder, 0)
                                else:
                                    logger.critical(f"no skill found")
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

        if msg and actor.connection:
            await actor.send_text(CommTypes.DYNAMIC, msg)
        else:
            set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
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
        await target.echo(CommTypes.DYNAMIC, msg, vars, cls._game_state)
        room = actor._location_room if actor._location_room else actor.in_actor_.location_room_
        if target != actor and TriggerType.CATCH_SAY in target.triggers_by_type:
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


    async def cmd_tell(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_tell()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Tell who?")
            return
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Tell what?")
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        target = cls._game_state.find_target_character(actor, pieces[0], search_world=True)
        logger.debug3(f"target: {target}")
        if target == None:
            # actor.send_text(CommTypes.DYNAMIC, "Tell who?")
            # return
            raise Exception("Tell who?")
        text = ' '.join(pieces[1:])
        msg = f"{firstcap(actor.name)} tells you '{text}'."
        vars = set_vars(actor, actor, target, msg)
        logger.debug3("sending message to actor")
        await target.echo(CommTypes.DYNAMIC, msg, game_state=cls._game_state)
        await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name} '{text}'.")


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
        logger.critical(f"command: {command}, actor.rid: {actor.rid}, input: {input}")
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            logger.critical("no pieces")
            actor_msg = firstcap(cls.EMOTE_MESSAGES[command]["notarget"]['actor'])
            room_msg = firstcap(cls.EMOTE_MESSAGES[command]["notarget"]['room'])
            target_msg = None
            target = None
        else:
            logger.critical(f"finding target: actor={actor.rid} target={pieces[0]}")
            target = cls._game_state.find_target_character(actor, pieces[0])
            if target == None:
                logger.critical("can't find target")
                await actor.send_text(CommTypes.DYNAMIC, f"{command} whom?")
                return
            actor_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['actor'])
            room_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['room'])
            target_msg = firstcap(cls.EMOTE_MESSAGES[command]['target']['target'])
            logger.critical(f"actor_msg: {actor_msg}, room_msg: {room_msg}, target_msg: {target_msg}")

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
        target = cls._game_state.find_target_character(actor, pieces[0])
        if target == None:
            target = cls._game_state.find_target_object(pieces[0], actor)
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Look at what?")
            return
        if isinstance(target, Character):
            await CoreActionsInterface.get_instance().do_look_character(actor, target)
        elif isinstance(target, Object):
            await CoreActionsInterface.get_instance().do_look_object(actor, target)
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
        logger.critical(f"Verifying connection is None for new NPC {new_npc.name} - connection: {new_npc.connection}")
        if new_npc.connection is not None:
            logger.critical(f"WARNING: Connection was not None for spawned NPC! Forcing to None.")
            new_npc.connection = None
            
        # Place NPC in the current room
        await CoreActionsInterface.get_instance().arrive_room(new_npc, actor.location_room)
        await actor.send_text(CommTypes.DYNAMIC, f"Spawned {new_npc.art_name}")
        await CoreActionsInterface.get_instance().do_look_room(actor, actor.location_room)

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
        await CoreActionsInterface.get_instance().start_fighting(actor, target)
        # TODO:L: maybe some situations where target doesn't retaliate?
        await CoreActionsInterface.get_instance().start_fighting(target, actor)


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
        # TODO:M: handle all kinds of cases, like get from container, get from corpse
        # TODO:M: add max carry weight
        logger = StructuredLogger(__name__, prefix="cmd_get()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Get what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Get what?")
            return
        if target.location_room != actor.location_room:
            await actor.send_text(CommTypes.DYNAMIC, "That's not here.")
            return
        target.location_room.remove_object(target)
        actor.add_object(target)
        await actor.send_text(CommTypes.DYNAMIC, f"You get {target.art_name}.")


    async def cmd_drop(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_drop()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Drop what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Drop what?")
            return
        if target.location_room != actor.location_room:
            await actor.send_text(CommTypes.DYNAMIC, "You don't have that.")
            return
        target.location_room.remove_object(target)
        actor.add_object(target)
        await actor.send_text(CommTypes.DYNAMIC, f"You drop {target.art_name}.")


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
        logger.critical(f"set log level to {pieces[0]}")
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
        logger.critical(f"set logfilter to {','.join(pieces)}")
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
            and not actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.DYNAMIC, "You're already standing.")
            return
        
        if any(actor.get_character_states_by_type(CharacterStateForcedSitting))\
               or any(actor.get_character_states_by_type(CharacterStateForcedSleeping)):
            msg = f"You can't stand up right now."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), game_state=cls._game_state)

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
            msg = f"You can't stand up right now."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), game_state=cls._game_state)

        await actor.send_text(CommTypes.DYNAMIC, "You stand up.")
        msg = f"{firstcap(actor.name)} stands up."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING | TemporaryCharacterFlags.IS_SITTING)
        

    async def cmd_sleep(cls, actor: Actor, input: str):
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can sleep.")
            return
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.DYNAMIC, "You're already sleeping.")
            return
            
        await actor.send_text(CommTypes.DYNAMIC, "You doze off.")
        msg = f"{firstcap(actor.name)} falls asleep."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, None, msg), exceptions=[actor], game_state=cls._game_state)
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        actor.set_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)


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
                destination = actor.location_room.exits[direction]
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
        
        # Status indicators
        if target.is_dead():
            await actor.send_text(CommTypes.STATIC, "Status: DEAD")
        elif target.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            await actor.send_text(CommTypes.STATIC, "Status: Sleeping")
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
