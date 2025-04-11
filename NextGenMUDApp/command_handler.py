from .structured_logger import StructuredLogger
import itertools
import logging
from num2words import num2words
import random
import re
from typing import Callable, List
import yaml
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
from .nondb_models.triggers import TriggerType
from .nondb_models import world
from .utility import replace_vars, firstcap, set_vars, split_preserving_quotes, article_plus_name
from .nondb_models.rooms import Room
from .nondb_models.world import WorldDefinition, Zone
from .communication import Connection
from .comprehensive_game_state_interface import GameStateInterface, ScheduledAction
from .config import Config, default_app_config

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
        "spawn": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_spawn(char,input),
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

        # normal commands
        "north": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "north"),
        "n": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "north"),
        "south": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "south"),
        "s": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "south"),
        "east": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "east"),
        "e": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "east"),
        "west": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "west"),
        "w": lambda command, char, input: CoreActionsInterface.get_instance().world_move(char, "west"),
        "say": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_say(char, input),
        "sayto": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sayto(char, input),
        "tell": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_tell(char, input),
        "emote": lambda command, char,input: CommandHandlerInterface.get_instance().cmd_emote(char, input),
        "look": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_look(char, input),
        "attack": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "kill": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_attack(command, char, input),
        "inv": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "inventory": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inventory(char, input),
        "get": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_get(char, input),
        "drop": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_drop(char, input),
        "inspect": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_inspect(char, input),
        "equip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_equip(char, input),
        "unequip": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_unequip(char, input),
        "stand": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_stand(char, input),
        "sit": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sit(char, input),
        "sleep": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_sleep(char, input),
        "leaverandom": lambda command, char, input: CommandHandlerInterface.get_instance().cmd_leaverandom(char, input),

        # various emotes are in the EMOTE_MESSAGES dict below
    }


    async def process_command(cls, actor: Actor, input: str, vars: dict = None):
        logger = StructuredLogger(__name__, prefix="process_command()> ")
        # print(actor)
        logger.debug3(f"processing input for actor {actor.id}: {input}")
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
        try:
            if input.strip().split() == "":
                msg = "Did you want to do something?"
            elif actor.actor_type == ActorType.CHARACTER and actor.is_dead():
                msg = "You are dead.  You can't do anything."
            elif actor.actor_type == ActorType.CHARACTER \
                and actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                and not input.startswith("stand"):
                msg = "You can't do that while you're sleeping."
            elif actor.actor_type == ActorType.CHARACTER \
                and actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                and not input.startswith("stand"):
                msg = "You can't do that while you're sitting."
            elif actor.actor_type == ActorType.CHARACTER \
                and actor.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
                msg = "You are stunned!"
            else:
                parts = split_preserving_quotes(input)
                if len(parts) == 0:
                    msg = "Did you want to do something?"
                command = parts[0]
                emote_command = cls.EMOTE_MESSAGES[command] if command in cls.EMOTE_MESSAGES else None
                if not command in cls.command_handlers and emote_command == None:
                    logger.debug3(f"Unknown command: {command}")
                    msg = "Unknown command"
                else:
                    try:
                        logger.debug3(f"Evaluating command: {command}")
                        if emote_command:
                            await cls.cmd_specific_emote(command, actor, ' '.join(parts[1:]))
                        else:
                            await cls.command_handlers[command](command, actor, ' '.join(parts[1:]))
                    except KeyError:
                        logger.error(f"KeyError processing command {command}")
                        msg = "Command failure."
                        raise
        except:
            logger.exception(f"exception handling input '{input}' for actor {actor.rid}")
            raise
        # logger.critical(f"len(executing_actors) 2: {len(cls.executing_actors)}")
        # for ch in cls.executing_actors:
        #     logger.critical(f"executing_actors 2: {ch}")
        if msg and actor.connection:
            await actor.send_text(CommTypes.DYNAMIC, msg)
        else:
            set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
        if not actor.rid in cls.executing_actors:
            logger.warning(f"actor {actor.rid} not in executing_actors")
            # logger.critical(f"len(executing_actors) 3: {len(cls.executing_actors)}")
            # for ch in cls.executing_actors:
            #     logger.critical(f"executing_actors 3: {ch}")
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
            target = cls._game_state.find_target_object(actor, pieces[0])
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
        # TODO:L: what if an object in a container spawns something?
        logger = StructuredLogger(__name__, prefix="cmd_spawn()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if not input:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")
            return
        pieces = split_preserving_quotes(input)
        target = cls._game_state.find_target_character(actor, pieces[0])
        if target == None:
            target = cls._game_state.find_target_object(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")
            return
        if isinstance(target, Character):
            new_char = Character.create_from_definition(target)
            new_char.location_room = actor.location_room
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {new_char.art_name}.")
        elif isinstance(target, Object):
            new_obj = Object.create_from_definition(target)
            new_obj.location_room = actor.location_room
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {new_obj.art_name}.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")

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
            await actor.send_text(CommTypes.DYNAMIC, f"HP: {target.hp}/{target.max_hp}")
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
        if not isinstance(actor, Character):
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can have inventories.")
            return
        if not actor.contents:
            await actor.send_text(CommTypes.DYNAMIC, "You are carrying nothing.")
            return
        await actor.send_text(CommTypes.DYNAMIC, f"You are carrying: {Object.collapse_name_multiples(actor.contents, ', ')}")


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
        if actor.fighting_whom != None:
            msg = "You can't equip while fighting!"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return
        if input == "":
            await cls.cmd_equip_list(actor, input)
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


    async def cmd_equip_list(cls, actor: Actor, input: str):
        logger = StructuredLogger(__name__, prefix="cmd_equip_list()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
        msg_parts = [ "You are equipped with:\n"]
        for loc in EquipLocation:
            if actor.equipped[loc] != None:
                msg_parts.append(f"{loc.name}: {actor.equipped[loc].art_name}\n")
            else:
                msg_parts.append(f"{loc.name}: nothing\n")
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
        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can leave random.")
            return
        pieces = input.split(' ')
        stay_in_zone = (pieces[0].lower() == "stayinzone")
        valid_directions = []
        if stay_in_zone:
            logger.debug3("stayinzone")
            logger.debug3("exits: " + str(actor.location_room.exits))
            for direction, dest_room_id in actor._location_room.exits.items():
                logger.debug3("dest_room_id: " + dest_room_id)
                if "." in dest_room_id:
                    dest_zone_id, dest_room_id = dest_room_id.split(".")
                    logger.debug3("got .")
                    logger.debug3(f"dest_zone_id: {dest_zone_id}, dest_room_id: {dest_room_id}")
                else:
                    dest_zone_id = actor.location_room.zone.id
                logger.debug3("dest_zone_id: " + dest_zone_id)
                logger.debug3("actor.location_room.zone.id: " + actor.location_room.zone.id)
                if dest_zone_id == actor.location_room.zone.id:
                    valid_directions.append(direction)
        else:
            logger.debug3("not stayinzone")
            valid_directions = actor.location_room.exits.keys()
        logger.debug3("valid_exits: " + str(valid_directions))
        num_exits = len(valid_directions)
        if num_exits == 0:
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
