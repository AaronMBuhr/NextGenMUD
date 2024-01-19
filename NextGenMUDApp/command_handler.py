from custom_detail_logger import CustomDetailLogger
import itertools
import logging
from num2words import num2words
import random
import re
from typing import Callable, List
from yaml_dumper import YamlDumper
import yaml
from .command_handler_interface import CommandHandlerInterface
from .communication import CommTypes
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
from .constants import Constants
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actor_states import CharacterStateForcedSleeping, CharacterStateForcedSitting
from .nondb_models.actors import Actor, ActorType
from .nondb_models.character_interface import CharacterInterface, \
    EquipLocation, PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags
from .nondb_models.object_interface import ObjectInterface, ObjectFlags
from .nondb_models.objects import Object
from .nondb_models.room_interface import RoomInterface
from .nondb_models.triggers import TriggerType
from .nondb_models import world
from .utility import replace_vars, firstcap, set_vars, split_preserving_quotes, article_plus_name

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
        logger = CustomDetailLogger(__name__, prefix="process_command()> ")
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
            if input.split() == "":
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
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls._game_state)
        if not actor.rid in cls.executing_actors:
            logger.warning(f"actor {actor.rid} not in executing_actors")
            # logger.critical(f"len(executing_actors) 3: {len(cls.executing_actors)}")
            # for ch in cls.executing_actors:
            #     logger.critical(f"executing_actors 3: {ch}")
        else:
            del cls.executing_actors[actor.rid]


    async def cmd_say(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_sayto()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_echo()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_echoto()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_echoexcept()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_tell()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_specific_emote()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_setvar_helper()> ")
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
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Show what?")
            return
        answer = {}
        if pieces[0].lower() == "zones":
            answer["ZONES"] = {
                zone.id: {"id": zone.id, "name": zone.name, "description": zone.description} 
                for zone in cls._game_state.zones.values()
            }
        elif pieces[0].lower() == "zone":
            try:
                zone = cls._game_state.zones[pieces[1]]
            except KeyError:
                await actor.send_text(CommTypes.DYNAMIC, f"zone {pieces[1]} not found.")
                return
            answer["ZONE"] = {}
            answer["ZONE"][zone.id] = {"id": zone.id, "name": zone.name, "description": zone.description}
            answer["ZONE"][zone.id]["rooms"] = {
                room.id: {
                    "id": room.id,
                    "name": room.name,
    #                "description": room.description,
                    "characters": [character.id for character in room.get_characters()],
                    "objects": [object.id for object in room.contents],
                    "triggers": {
                        trigger_type.name: [  # Using trigger_type here, assuming it's an Enum
                            {
                                "criteria": [
                                    f"{criterion.subject_}, {criterion.operator_}, {criterion.predicate_}"
                                    for criterion in trigger.criteria_
                                ]
                            }
                            for trigger in triggers  # Make sure this is the correct variable from room.triggers_by_type.items()
                        ] 
                        for trigger_type, triggers in room.triggers_by_type.items()  # Correctly extracting trigger_type and triggers
                    }
                }
                for room in zone.rooms_.values()
            }
        elif pieces[0].lower() == "characters":
            answer["CHARACTERS"] = {
                a.id : {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "location": a.location_room_.id if a.location_room_ else None,
                    "temp_variables": a.temp_variables,
                    "perm_variables": a.perm_variables,
                } for a in Actor.references_.values() if a.actor_type == ActorType.CHARACTER
            }
        elif pieces[0].lower() == "objects":
            answer["OBJECTS"] = {
                a.id : {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "location": a.location_room_.id if a.location_room_ else None,
                    "temp_variables": a.temp_variables,
                    "perm_variables": a.perm_variables,
                } for a in Actor.references_.values() if a.actor_type == ActorType.OBJECT and a.location_room_ is not None
            }
        elif pieces[0].lower() == "carried":
            answer["OBJECTS"] = {
                a.id : {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "inside": f"{a.art_name} ({a.in_actor_.rid})" if a.in_actor_ else None,
                    "temp_variables": a.temp_variables,
                    "perm_variables": a.perm_variables,
                } for a in Actor.references_.values() if a.actor_type == ActorType.OBJECT and a.in_actor_ is not None
            }
        elif pieces[0].lower() == "room":
            try:
                room = cls._game_state.find_target_room(actor, ' '.join(pieces[1:]), actor._location_room.zone)
            except KeyError:
                await actor.send_text(CommTypes.DYNAMIC, f"room '{' '.join(pieces[1])} not found.")
                return
            answer["ROOMS"] = {
                room.id: {
                    "id": room.id,
                    "name": room.name,
                    "description": room.description,
                    "characters": [character.id for character in room.get_characters()],
                    "objects": [object.id for object in room.contents],
                    "triggers": {
                        trigger_type.name: [  # Using trigger_type here, assuming it's an Enum
                            trigger.to_dict() for trigger in triggers  # Make sure this is the correct variable from room.triggers_by_type.items()
                        ] 
                        for trigger_type, triggers in room.triggers_by_type.items()  # Correctly extracting trigger_type and triggers
                    }
                }
            }
        yaml_answer = yaml.dump(answer)
        # yaml_answer = YamlDumper.to_yaml_compatible_str(answer)

        # yaml_answer = YamlDumper.to_yaml_compatible_str(answer["ROOMS"]["starting_room_2"]["triggers"])
        # yaml_answer = yaml_answer + "\n\n" + yaml.dump(answer["ROOMS"]["starting_room_2"]["triggers"])

        await actor.send_text(CommTypes.STATIC, yaml_answer)


    async def cmd_look(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_look()> ")
        from .nondb_models.triggers import TriggerType, Trigger
        # TODO:M: add various look permutations
        room = actor._location_room
        pieces = input.split(' ')
        if input.strip() == "":
            await actor.send_text(CommTypes.DYNAMIC, "You look around.")
            await CoreActionsInterface.get_instance().do_look_room(actor, room)
            return
        found = False

        # character?
        logger.debug("looking for characters")
        target = cls._game_state.find_target_character(actor, input, search_zone=False, search_world=False)
        if target:
            logger.debug("found character")
            await CoreActionsInterface.get_instance().do_look_character(actor, target)
            return
        # object?
        logger.debug("looking for objects")
        target = cls._game_state.find_target_object(target_name=input, actor=None, equipped=None,
                                            start_room=actor._location_room, start_zone=None, search_world=False)

        if target:
            logger.debug("found object")
            await CoreActionsInterface.get_instance().do_look_object(actor, target)
            return

        try:
            logger.debug3(f"target: {input}")
            logger.debug3("Blah Looking for CATCH_LOOK triggers")
            # print(yaml.dump(room.triggers_by_type))
            # print("**** should have dumped ****")
            logger.debug3(f"Still looking for CATCH_LOOK triggers {room.id}")
            logger.debug3(f"heh 2 {room.triggers_by_type.keys()}")
            for trig in room.triggers_by_type[TriggerType.CATCH_LOOK]:
                logger.debug3(f"checking trigger for: {trig.criteria_[0].subject_}")
                logger.debug3("before trig.run")
                vars = set_vars(actor, actor, actor, input)
                if await trig.run(actor, input, vars, cls._game_state):
                    found = True
                logger.debug3("after trig.run")
            logger.debug3(f"done looking for CATCH_LOOK triggers {room.id}")
        except Exception as ex:
            logger.debug3(f"excepted looking for CATCH_LOOK triggers: {ex}")
            pass
        if not found:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that.")


    async def cmd_spawn(cls, actor: Actor, input: str):
        # TODO:L: what if an object in a container spawns something?
        from .nondb_models.characters import Character
        from .nondb_models.objects import Object, ObjectFlags
        logger = CustomDetailLogger(__name__, prefix="cmd_spawn()> ")
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn char or obj?")
            return
        if pieces[0].lower() == "char":
            character_def = cls._game_state.world_definition.find_character_definition(' '.join(pieces[1:]))
            if not character_def:
                await actor.send_text(CommTypes.DYNAMIC, f"Couldn't find a character definition for {pieces[1:]}.")
                return
            cls._game_state.spawn_character(character_def, actor.location_room, None)
            new_character = Character.create_from_definition(character_def)
            cls._game_state.characters.append(new_character)
            new_character.location_room_ = actor._location_room
            new_character.location_room_.add_character(new_character)
            logger.debug(f"new_character: {new_character} added to room {new_character.location_room_.rid}")
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {actor.art_name_cap}.")
            await CoreActionsInterface.get_instance().do_look_room(actor, actor._location_room)
        elif pieces[0].lower() == "obj":
            object_def = cls._game_state.world_definition.find_object_definition(' '.join(pieces[1:]))
            if not object_def:
                await actor.send_text(CommTypes.DYNAMIC, f"Couldn't find an object definition for {pieces[1:]}.")
                return
            new_object = Object.create_from_definition(object_def)
            logger.debug(f"new_object: {new_object}")
            if actor.actor_type == ActorType.CHARACTER:
                logger.debug("adding to character")
                actor.add_object(new_object, True)
                logger.debug(f"new_object: {new_object} added to character {actor}")
                logger.debug(f"actor.contents length: {len(actor.contents)}")
                # print(Object.collapse_name_multiples(actor.contents, ","))
            elif actor.actor_type == ActorType.OBJECT:
                if actor.has_flags(ObjectFlags.IS_CONTAINER):
                    logger.debug("adding to container")
                    actor.add_object(new_object, True)
                    logger.debug(f"new_object: {new_object} added to container {actor}")
                    # print(Object.collapse_name_multiples(actor.contents, ","))
                else:
                    logger.debug("adding to room")
                    actor._location_room.add_object(new_object)
                    logger.debug(f"new_object: {new_object} added to room {actor._location_room}")
                    # print(Object.collapse_name_multiples(actor.location_room_.contents, ","))
            elif actor.actor_type == ActorType.ROOM:
                    logger.debug("adding to room")
                    actor.add_object(new_object)
                    logger.debug(f"new_object: {new_object} added to room {actor}")
                    # print(Object.collapse_name_multiples(actor.contents, ","))
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type} for object not implemented.")
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {new_object.art_name}.")
            logger.critical(f"new_object: art_name: {new_object.art_name}, object: {new_object.to_dict()}")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")
            return
    

    async def cmd_goto(cls, actor: Actor, input: str):
        pieces = input.lower().split(' ')
        if pieces[0] == "char":
            target = cls._game_state.find_target_character(actor, ' '.join(pieces[1:]), search_world=True)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that character?")
                return
            actor._location_room.remove_character(actor)
            target.location_room_.add_character(actor)
            await actor.send_text(CommTypes.DYNAMIC, f"You go to {target.rid}.")
        elif pieces[0] == "room":
            target_room = cls._game_state.find_target_room(actor, ' '.join(pieces[1:]), actor._location_room.zone)
            if target_room == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that room?")
                return
            actor._location_room.remove_character(actor)
            target_room.add_character(actor)
        else:
            await actor.send_text(CommTypes.DYNAMIC, "goto where?")


    async def cmd_list(cls, actor: Actor, input: str):
        await actor.send_text(CommTypes.DYNAMIC, "list not yet implemented")


    async def cmd_attack(cls, command: str, actor: Actor, input: str):
        target = cls._game_state.find_target_character(actor, input)
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "{command} whom?")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_inspect()> ")
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "inspect what?")
            return
        msg_parts = []
        if input.strip().lower() == "me":
            msg_parts.append("You inspect yourself.")
            target = actor
        else:
            target = cls._game_state.find_target_character(actor, input)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "inspect what?")
                return
            msg_parts.append(f"You inspect {target.name}.")
        if target.actor_type == ActorType.CHARACTER:
            if actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
                msg_parts.append( 
    # IS_ADMIN
    f"""
    ID: {actor.id} ({actor.reference_number})""")
            msg_parts.append(
    # ALWAYS
    f"""
    Name: {actor.name}
    Description: {actor.description}
    Health: {actor.get_status_description()}""")
            if actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
                msg_parts.append(
    # IS_ADMIN
    f"""
    Hit Points: {actor.current_hit_points} / {actor.max_hit_points}""")
                if not target.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    msg_parts.append(f" ({target.hit_dice}d{target.hit_dice_size}+{target.hit_modifier})\n")
                else: # PC
                    msg_parts.append("\n")
                msg_parts.append(
    # IS_ADMIN
    f"""
    Location: {target._location_room.name} ({target._location_room.id})""")
            else:
                msg_parts.append(
    # NOT IS_ADMIN
    f"""
    Location: {target._location_room.name}""")

            msg_parts.append(
    # ALWAYS
    f"""
    Hit Modifier: {target.hit_modifier}  /  Critical Hit: {target.critical_chance}% (Critical Damage: {target.critical_multiplier}x)
    Dodge Chance: {target.dodge_dice_number}d{target.dodge_dice_size}+{target.dodge_modifier}""")

            if actor.has_game_flags(GamePermissionFlags.IS_ADMIN):
                msg_parts.append(
    # IS_ADMIN
    f"""
    Character Flags: {target.permanent_character_flags.to_comma_separated()}
    Triggers ({sum(len(lst) for lst in target.triggers_by_type.values())}): 
    {"\n".join([f"{key}:\n{',\n'.join([ v.shortdesc() for v in values])}" for key, values in target.triggers_by_type.items()])}
    Temp variables:
    {"\n".join([f"{key}: {value}" for key, value in target.temp_variables.items()])}
    Permanent variables:
    {"\n".join([f"{key}: {value}" for key, value in target.perm_variables.items()])}""")

        await actor.send_text(CommTypes.STATIC, "".join(msg_parts))        


    async def cmd_inventory(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_inventory()> ")
        msg_parts = [ "You are carrying:\n"]
        if actor.actor_type == ActorType.CHARACTER:
            logger.debug(f"char: {actor.rid}")
            if len(actor.contents) == 0:
                msg_parts.append(" nothing.")
            else:
                msg_parts.append(Object.collapse_name_multiples(actor.contents, "\n"))
            await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        elif actor.actor_type == ActorType.OBJECT:
            logger.debug(f"obj: {actor.rid}")
            if not actor.has_flags(ObjectFlags.IS_CONTAINER):
                msg_parts.append(" nothing (you're not a container).")
            else:
                if len(actor.contents) == 0:
                    msg_parts.append(" nothing.")
                else:
                    msg_parts.append(Object.collapse_name_multiples(actor.contents, "\n"))
                await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        elif actor.actor_type == ActorType.ROOM:
            logger.debug(f"room: {actor.rid}")
            room: 'Room' = actor
            if len(room.contents) == 0:
                msg_parts.append(" nothing.")
            else:
                msg_parts.append(Object.collapse_name_multiples(room.contents, "\n"))
            await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type} not implemented.")


    async def cmd_at(cls, actor: Actor, input: str):
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        cmd = ' '.join(pieces[2:])
        if pieces[0].lower() == "char":
            target = cls._game_state.find_target_character(actor, pieces[1], search_world=True)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that character?")
                return
            target_room = target.location_room_
        elif pieces[0].lower() == "room":
            target_room = cls._game_state.find_target_room(actor, pieces[1], actor._location_room.zone)
        elif pieces[0].lower() == "obj":
            target = cls._game_state.find_target_object(target_name=pieces[1], actor=None, equipped=None,
                                            start_room=None, start_zone=actor._location_room.zone, search_world=False)

            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that object?")
                return
            # TODO:L: what to do if in a container or corpse?
            target_room = target.location_room_
        await actor.send_text(CommTypes.DYNAMIC, f"Doing '{cmd}' at {target.rid} (room {target_room.rid})")
        original_room = actor._location_room
        actor._location_room.remove_character(actor)
        target_room.add_character(actor)
        await cls.process_command(actor, cmd)
        target_room.remove_character(actor)
        original_room.add_character(actor)


    async def cmd_get(cls, actor: Actor, input: str):
        # TODO:M: handle all kinds of cases, like get from container, get from corpse
        # TODO:M: add max carry weight
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "Get what?")
            return
        pieces = input.split(' ')
        if pieces[0].isnumeric():
            qty = int(pieces[0])
            item_name = ' '.join(pieces[1:])
        else:
            qty = 1
            item_name = input
        if actor.actor_type == ActorType.CHARACTER:
            room = actor._location_room
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            num_got = 0
            for i in range(qty):
                item = cls._game_state.find_target_object(target_name=item_name, actor=None, equipped=None,
                                                         start_room=room, start_zone=None, search_world=False)
                if item == None:
                    break
                num_got += 1
                room.remove_object(item)
                actor.add_object(item)
                apn = item.art_name
            if num_got == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't see any {item_name} here.")
                return
            if num_got > 1:
                apn = num2words(num_got) + " " + item.name
            msg = f"You get {apn}."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
            msg = f"{firstcap(actor.name)} gets you."
            await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
            msg = f"{actor.art_name_cap} gets {apn}."
            await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor, item], game_state=cls._game_state)
            await CoreActionsInterface.get_instance().do_look_room(actor, room)


    async def cmd_drop(cls, actor: Actor, input: str):
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "Drop what?")
            return
        if actor.actor_type == ActorType.CHARACTER:
            room = actor._location_room
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            item = cls._game_state.find_target_object(input, actor)
            if item == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
                return
            actor.remove_object(item)
            room.add_object(item)
            msg = f"You drop {item.name}."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
            await CoreActionsInterface.get_instance().do_look_room(actor, room)
            msg = f"{actor.art_name_cap} drops you."
            await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
            msg = f"{actor.art_name_cap} drops {item.art_name}."
            await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor], game_state=cls._game_state)
            await CoreActionsInterface.get_instance().do_look_room(actor, room)
        elif actor.actor_type == ActorType.OBJECT:
            # TODO:L: what if in a container? to floor?
            # TODO:L: want to drop from container to inv?
            room = actor._location_room
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            obj: Object = actor
            if not obj.has_flags(ObjectFlags.IS_CONTAINER):
                await actor.send_text(CommTypes.DYNAMIC, "You're not a container, so you can't drop anything.")
                return
            item = cls._game_state.find_target_object(input, actor)
            if item == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
                return
            actor.remove_object(item)
            room.add_object(item)
            await actor.send_text(CommTypes.DYNAMIC, f"You drop {item.name}.")


    async def cmd_equip(cls, actor: Actor, input: str):

        logger = CustomDetailLogger(__name__, prefix="cmd_unequip()> ")

        def parse_equip_command(command, cls, actor):
            words = command.lower().split()
            original_words = list(words)  # Keep a copy of the original words for later use

            # Identify if an equip location is specified
            specified_location = None
            for location in EquipLocation:
                if location.name.lower().replace('_', ' ') in command:
                    specified_location = location
                    for loc_word in location.name.lower().split('_'):
                        words.remove(loc_word)
                    break

            # Try to find a matching object without considering the equip location
            for i in range(1, len(words) + 1):
                for combo in itertools.combinations(words, i):
                    item_name = ' '.join(combo)
                    target_object = cls._game_state.find_target_object(item_name, actor)
                    if target_object:
                        return specified_location, target_object

            # If no match found and a location was specified, try including the location in the search
            if specified_location:
                for i in range(1, len(original_words) + 1):
                    for combo in itertools.combinations(original_words, i):
                        item_name = ' '.join(combo)
                        target_object = cls._game_state.find_target_object(item_name, actor)
                        if target_object:
                            return specified_location, target_object

            # No matching object found
            return None

            # # Example usage
            # command = "equip main hand sword"
            # result = parse_equip_command(command, cls, actor)
            # if result:
            #     equip_location, target_object = result
            #     # Equip the object, using the specified equip location
            # else:
            #     # Handle invalid command

        if actor.actor_type != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
        if actor.fighting_whom != None:
            msg = "You can't equip while fighting!"
            vars = set_vars(actor, actor, actor, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return
        if input == "":
            # await actor.send_text(CommTypes.DYNAMIC, "Equip what?")
            await cls.cmd_equip_list(actor, input)
            return
        # equip_location = EquipLocation.string_to_enum(equip_locationname)
        result = parse_equip_command(input, cls, actor)
        if result:
            equip_location, target_object = result
            # Equip the object, using the specified equip location
        else:
            # Handle invalid command
            await actor.send_text(CommTypes.DYNAMIC, f"Equip what?")
            return
        if target_object == None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
            return
        if equip_location == None:
            if target_object.equip_locations == None or len(target_object.equip_locations) == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"You can't equip that.")
                return
            for loc in target_object.equip_locations:
                if actor.equipped[loc] == None:
                    equip_location = loc
                    break
            if equip_location == None:
                await actor.send_text(CommTypes.DYNAMIC, "There's not an open spot for it.")
                return
        if target_object == None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
            return
        if actor.equipped[equip_location] != None:
            await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped there.")
            return
        if target_object.has_flags(ObjectFlags.IS_WEAPON):
            if equip_location not in [EquipLocation.MAIN_HAND, EquipLocation.OFF_HAND, EquipLocation.BOTH_HANDS]:
                await actor.send_text(CommTypes.DYNAMIC, "You can't equip that there.")
                return
        if target_object.has_flags(ObjectFlags.IS_ARMOR):
            if equip_location not in [
    EquipLocation.HEAD,
    EquipLocation.NECK,
    EquipLocation.SHOULDERS,
    EquipLocation.ARMS,
    EquipLocation.WRISTS,
    EquipLocation.HANDS,
    EquipLocation.LEFT_FINGER,
    EquipLocation.RIGHT_FINGER,
    EquipLocation.WAIST,
    EquipLocation.LEGS,
    EquipLocation.FEET,
    EquipLocation.BODY,
    EquipLocation.BACK,
    EquipLocation.EYES]:
                await actor.send_text(CommTypes.DYNAMIC, "You can't equip that there.")
                return
        if equip_location == EquipLocation.BOTH_HANDS:
            if actor.equip_location[EquipLocation.MAIN_HAND] != None:
                await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped in your main hand.")
                return
            if actor.equip_location[EquipLocation.OFF_HAND] != None:
                await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped in your off hand.")
                return
        if equip_location == EquipLocation.OFF_HAND:
            if not actor.has_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't dual wield.")
                return
        if actor.fighting_whom != None:
            await actor.send_text(CommTypes.DYNAMIC, f"You can't equip things while fighting.")
            return
        actor.remove_object(target_object)
        actor.equip_item(equip_location, target_object)
        msg = f"You equip {target_object.name}."
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg), game_state=cls._game_state)
        msg = f"{actor.art_name_cap} equips you."
        await target_object.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg), game_state=cls._game_state)
        msg = f"{actor.art_name_cap} equips {target_object.art_name}."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg), exceptions=[actor], game_state=cls._game_state)


    async def cmd_unequip(cls, actor: Actor, input: str):

        def parse_equip_command(command, cls, actor):
            logger = CustomDetailLogger(__name__, prefix="cmd_unequip.parse_equip_command()> ")
            words = command.lower().split()
            original_words = list(words)  # Keep a copy of the original words for later use

            # Identify if an equip location is specified
            specified_location = None
            
            for location in EquipLocation:
                if location.name.lower().replace('_', ' ') in command:
                    specified_location = location
                    for loc_word in location.name.lower().split('_'):
                        words.remove(loc_word)
                    break

            # see if it's equipped
            for i in range(1, len(words) + 1):
                for combo in itertools.combinations(words, i):
                    item_name = ' '.join(combo)
                    logger.debug("searching actor equipped for " + item_name)
                    target_object = cls._game_state.find_target_object(item_name, actor=None,equipped=actor.equipped)
                    if target_object:
                        logger.debug("found " + item_name + "at " + target_object.equipped_location.word())
                        return target_object.equipped_location, target_object
            logger.debug("didn't find it equipped")

            # Try to find a matching object without considering the equip location
            for i in range(1, len(words) + 1):
                for combo in itertools.combinations(words, i):
                    item_name = ' '.join(combo)
                    target_object = cls._game_state.find_target_object(item_name, actor)
                    if target_object:
                        return specified_location, target_object

            # If no match found and a location was specified, try including the location in the search
            if specified_location:
                for i in range(1, len(original_words) + 1):
                    for combo in itertools.combinations(original_words, i):
                        item_name = ' '.join(combo)
                        target_object = cls._game_state.find_target_object(item_name, actor)
                        if target_object:
                            return specified_location, target_object

            # No matching object found
            return None

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
        if "main hand" in input.lower():
            specified_location = EquipLocation.MAIN_HAND
            target_object = actor.equipped[EquipLocation.MAIN_HAND]
            if target_object == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
                return
        elif "off hand" in input.lower():
            specified_location = EquipLocation.OFF_HAND
            target_object = actor.equipped[EquipLocation.OFF_HAND]
            if target_object == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
                return
        elif "both hands" in input.lower():
            specified_location = EquipLocation.BOTH_HANDS
            target_object = actor.equipped[EquipLocation.BOTH_HANDS]
            if target_object == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
                return
        result = parse_equip_command(input, cls, actor)
        if result:
            equip_location, target_object = result
        else:
            # Handle invalid command
            await actor.send_text(CommTypes.DYNAMIC, f"Unequip what?")
            return
        if equip_location == None:
            await actor.send_text(CommTypes.DYNAMIC, f"Unequip what or where?")
            return
        item = actor.equipped[equip_location]
        if item == None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
            return
        actor.unequip_location(equip_location)
        actor.add_object(item, True)
        msg = f"You unequip {item.name}."
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
        msg = f"{actor.art_name_cap} unequips you."
        await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), game_state=cls._game_state)
        msg = f"{actor.art_name_cap} unequips {item.art_name}."
        await actor._location_room.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor], game_state=cls._game_state)


    async def cmd_equip_list(cls, actor: Actor, input: str):
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
        loglevels = {
            "debug": logging.DEBUG,
            "debug1": logging.DEBUG,
            "debug2": logging.DEBUG,
            "debug3": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,        }
        pieces = input.split(' ')
        if len(pieces) < 1 or pieces[0].lower() not in loglevels:
            await actor.send_text(CommTypes.DYNAMIC, "Set log to what?")
            return
        logger = CustomDetailLogger(__name__, prefix="cmd_setloglevel()> ")
        filter = logger.get_allowed_prefixes()
        logger.set_allowed_prefixes()
        logger.critical(f"set log level to {pieces[0]}")
        logger.setLevel(loglevels[pieces[0].lower()])
        logger.set_allowed_prefixes(filter)
        await actor.send_text(CommTypes.DYNAMIC, f"Set log level to {pieces[0]}.")


    async def cmd_setlogfilter(cls, actor: Actor, input: str):
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Set logfilter to what?")
            return
        logger = CustomDetailLogger(__name__, prefix="cmd_setlogfilter()> ")
        logger.set_allowed_prefixes()
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
        logger = CustomDetailLogger(__name__, prefix="cmd_getlogfilter()> ")
        await actor.send_text(CommTypes.DYNAMIC, f"Logfilter is {','.join(logger.get_allowed_prefixes())}.")


    async def cmd_delvar_helper(cls, actor: Actor, input: str, target_dict_fn: Callable[[Actor], dict], target_name: str):
        # TODO:M: add targeting objects and rooms
        logger = CustomDetailLogger(__name__, prefix="cmd_delvar_helper()> ")
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
        logger = CustomDetailLogger(__name__, prefix="cmd_leaverandom()> ")
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
