from .utility import replace_vars, firstcap
from .core_actions import CoreActions
from .communication import CommTypes
from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .nondb_models.actors import Actor, ActorType, Character, CharacterFlags, Object, ObjectFlags, Room, EquipLocation, GamePermissionFlags
from .nondb_models import world
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
import re
from typing import Callable, List
from yaml_dumper import YamlDumper
import yaml
from .utility import set_vars, split_preserving_quotes, article_plus_name
from num2words import num2words
import itertools
import logging

class CommandHandler():
    game_state: ComprehensiveGameState = live_game_state
    executing_actors = {}

    command_handlers = {
        # privileged commands
        "show": lambda command, char, input: CommandHandler.cmd_show(char, input),
        "echo": lambda command, char, input: CommandHandler.cmd_echo(char, input),
        "echoto": lambda command, char, input: CommandHandler.cmd_echoto(char, input),
        "echoexcept": lambda command, char, input: CommandHandler.cmd_echoexcept(char, input),
        "settempvar": lambda command, char, input: CommandHandler.cmd_settempvar(char, input),
        "setpermvar": lambda command, char, input: CommandHandler.cmd_setpermvar(char, input),
        "spawn": lambda command, char, input: CommandHandler.cmd_spawn(char,input),
        "goto": lambda command, char, input: CommandHandler.cmd_goto(char, input),
        "list": lambda command, char, input: CommandHandler.cmd_list(char, input),
        "at": lambda command, char, input: CommandHandler.cmd_at(char, input),
        "setloglevel": lambda command, char, input: CommandHandler.cmd_setloglevel(char, input),
        "setlogfilter": lambda command, char, input: CommandHandler.cmd_setlogfilter(char, input),
        "getlogfilter": lambda command, char, input: CommandHandler.cmd_getlogfilter(char, input),

        # normal commands
        "north": lambda command, char, input: CoreActions.world_move(char, "north"),
        "n": lambda command, char, input: CoreActions.world_move(char, "north"),
        "south": lambda command, char, input: CoreActions.world_move(char, "south"),
        "s": lambda command, char, input: CoreActions.world_move(char, "south"),
        "east": lambda command, char, input: CoreActions.world_move(char, "east"),
        "e": lambda command, char, input: CoreActions.world_move(char, "east"),
        "west": lambda command, char, input: CoreActions.world_move(char, "west"),
        "w": lambda command, char, input: CoreActions.world_move(char, "west"),
        "say": lambda command, char, input: CommandHandler.cmd_say(char, input),
        "tell": lambda command, char, input: CommandHandler.cmd_tell(char, input),
        "emote": lambda command, char,input: CommandHandler.cmd_emote(char, input),
        "look": lambda command, char, input: CommandHandler.cmd_look(char, input),
        "attack": lambda command, char, input: CommandHandler.cmd_attack(command, char, input),
        "kill": lambda command, char, input: CommandHandler.cmd_attack(command, char, input),
        "inv": lambda command, char, input: CommandHandler.cmd_inventory(char, input),
        "inventory": lambda command, char, input: CommandHandler.cmd_inventory(char, input),
        "get": lambda command, char, input: CommandHandler.cmd_get(char, input),
        "drop": lambda command, char, input: CommandHandler.cmd_drop(char, input),
        "inspect": lambda command, char, input: CommandHandler.cmd_inspect(char, input),
        "equip": lambda command, char, input: CommandHandler.cmd_equip(char, input),
        "unequip": lambda command, char, input: CommandHandler.cmd_unequip(char, input),

        # various emotes
        "kick": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "kiss": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "lick": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "congratulate": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "bow": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "thank": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "sing": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "dance": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
        "touch": lambda command, char, input: CommandHandler.cmd_specific_emote(command, char, input),
    }


    @classmethod
    async def process_command(cls, actor: Actor, input: str, vars: dict = None):
        logger = CustomDetailLogger(__name__, prefix="process_command()> ")
        logger.critical(f"processing input for actor {actor.id_}: {input}")
        if actor.reference_number_ is None:
            raise Exception(f"Actor {actor.id_} has no reference number.")
        if actor.rid in cls.executing_actors:
            logger.Error(f"Actor {actor.id_} is already executing a command.")
        cls.executing_actors[actor.rid] = input
        msg = None
        try:
            if input.split() == "":
                msg = "Did you want to do something?"
            elif actor.actor_type_ == ActorType.CHARACTER and actor.is_dead():
                msg = "You are dead.  You can't do anything."
            else:
                parts = split_preserving_quotes(input)
                command = parts[0]
                if not command in cls.command_handlers:
                    logger.debug3(f"Unknown command: {command}")
                    msg = "Unknown command"
                else:
                    try:
                        logger.critical(f"Evaluating command: {command}")
                        await cls.command_handlers[command](command, actor, ' '.join(parts[1:]))
                    except KeyError:
                        logger.error(f"KeyError processing command {command}")
                        msg = "Command failure."
        except:
            logger.exception(f"exception handling input '{input}' for actor {actor.rid}")
            raise
        if msg:
            await actor.send_text(CommTypes.DYNAMIC, msg)
        del cls.executing_actors[actor.rid]


    @classmethod
    async def cmd_say(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        await actor.send_text(CommTypes.DYNAMIC, f"You say, \"{text}\"")
        room = actor.location_room_ if actor.location_room_ else actor.in_actor_.location_room_
        if room:
            if actor.actor_type_ == ActorType.CHARACTER:
                await room.echo(CommTypes.DYNAMIC, f"f{article_plus_name(actor.article_, actor.name_, cap=True)} says, \"{text}\"", vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.OBJECT:
                await room.echo(CommTypes.DYNAMIC, f"{article_plus_name(actor.article_, actor.name_, cap=True)} says, \"{text}\"", vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.ROOM:
                await room.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
        else:
            actor.send_text(CommTypes.DYNAMIC, "You have no location room.")
            logger.error(f"Actor {actor.rid} has no location room.")


    @classmethod
    async def cmd_echo(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_echo()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        if actor.location_room_:
            if actor.actor_type_ == ActorType.CHARACTER:
                await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.OBJECT:
                await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.ROOM:
                # print("***")
                # print(text)
                # print("***")
                await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
        await actor.send_text(CommTypes.DYNAMIC, text)


    @classmethod
    async def cmd_echoto(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_echoto()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        if len(input) < 2:
            await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
        if len(input) < 3:
            await actor.send_text(CommTypes.DYNAMIC, "Echo what?")
        pieces = split_preserving_quotes(input)
        logger.debug3(f"finding target: {pieces[0]}")
        target = cls.game_state.find_target_character(actor, pieces[0])
        logger.debug3(f"target: {target}")
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
            return
        text = ' '.join(pieces[1:])
        vars = set_vars(actor, actor, target, text)
        msg = f"You echo '{text}' to {target.name_}."
        await target.echo(CommTypes.DYNAMIC, text, vars)
        await actor.send_text(CommTypes.DYNAMIC, msg)


    @classmethod
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
        excludee = cls.game_state.find_target_character(actor, pieces[1])
        logger.debug3(f"excludee: {excludee}")
        if excludee == None:
            await actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
            return
        exclude = [ excludee ]
        text = ' '.join(pieces[1:])
        msg = f"To everyone except {exclude[0].name_} you echo '{text}'."
        vars = set_vars(actor, actor, exclude[0], msg)
        await actor.echo(CommTypes.DYNAMIC, text, vars, exceptions=exclude)
        await actor.send_text(CommTypes.DYNAMIC, msg)


    @classmethod
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
        target = cls.game_state.find_target_character(actor, pieces[0], search_world=True)
        logger.debug3(f"target: {target}")
        if target == None:
            # actor.send_text(CommTypes.DYNAMIC, "Tell who?")
            # return
            raise Exception("Tell who?")
        text = ' '.join(pieces[1:])
        msg = f"{firstcap(actor.name_)} tells you '{text}'."
        vars = set_vars(actor, actor, target, msg)
        logger.debug3("sending message to actor")
        await target.echo(CommTypes.DYNAMIC, msg)
        await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name_} '{text}'.")


    @classmethod
    async def cmd_emote(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
        logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
        text = input
        vars = set_vars(actor, actor, actor, text)
        await actor.send_text(CommTypes.DYNAMIC, f"You emote, \"{text}\"")
        if actor.location_room_:
            if actor.actor_type_ == ActorType.CHARACTER:
                await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {text}", vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.OBJECT:
                await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            elif actor.actor_type_ == ActorType.ROOM:
                await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


    EMOTE_MESSAGES = {
        "kick": { 'notarget' : { 'actor': "You let loose with a wild kick.", 'room': "%a% lets loose with a wild kick." },
                'target' : { 'actor': "You kick %t%.", 'room': "%a% kicks %t%." , 'target': "%a% kicks you."} },
        "kiss": { 'notarget' : { 'actor': 'You kiss the air.', 'room': '%a% kisses the air.'},
                'target': {'actor': "You kiss %t%.", 'room': "%a% kisses %t%.", 'target': "%a% kisses you." }},
        "lick": { 'notarget': { 'actor': 'You lick the air.', 'room': '%a% licks the air.'},
                'target': {'actor': "You lick %t%.", 'room': "%s% licks %t%.", 'target': "%s% licks you." }},
        "congratulate": { 'notarget' : { 'actor' : 'You congratulate yourself.', 'room' : '%a% congratulates %{P}self.'},
                        'target' : { 'actor': "You congratulate %t%.", 'room': "%a% congratulates %t%." , 'target': "%a% congratulates you."}},
        "bow": { 'notarget': { 'actor': 'You take a bow.', 'room': 'Makes a sweeping bow.'}, 
                'target' : {'actor': "You bow to %t%.", 'room': "%a% bows to %t%.", 'target': "%a% bows to you." }},
        "thank": { 'notarget': { 'actor' : 'You thank everyone.', 'room' : '%a% thanks everyone.' },
                'target' : {'actor': "You thank %t%.", 'room': "%a% thanks %t%.", 'target': "%a% thanks you." }},
        "sing": { 'notarget' : {'actor': 'You sing your heart out.', 'room' : '%a% sings %P% heart out.' },
                'target': {'actor': "You sing to %t%.", 'room': "%a% sings to %t%.", 'target': "%a% sings to you." }},
        "dance": { 'notarget' : {'actor': 'You dance a jig.', 'room' : '%a% dances a jig.' },
                    'target': {'actor': "You dance with %t%.", 'room': "%a% dances with %t%.", 'target': "%a% dances with you." }},
                    "touch": { 'notarget' : {'actor': 'You touch yourself.', 'room' : '%a% touches %P%self.' },
                    'target': {'actor': "You touch %t%.", 'room': "%a% touches %t%.", 'target': "%a% touches you." }}
        }

    @classmethod
    async def cmd_specific_emote(cls, command: str, actor: Actor, input: str):
        # TODO:L: add additional logic for no args, for "me", for objects
        logger = CustomDetailLogger(__name__, prefix="cmd_specific_emote()> ")
        logger.critical(f"command: {command}, actor.rid: {actor.rid}, input: {input}")
        pieces = split_preserving_quotes(input)
        if len(pieces) < 1:
            logger.critical("no pieces")
            actor_msg = cls.EMOTE_MESSAGES[command]["notarget"]['actor']
            room_msg = cls.EMOTE_MESSAGES[command]["notarget"]['room']
            target_msg = None
            target = None
        else:
            logger.critical(f"finding target: actor={actor.rid} target={pieces[0]}")
            target = cls.game_state.find_target_character(actor, pieces[0])
            if target == None:
                logger.critical("can't find target")
                await actor.send_text(CommTypes.DYNAMIC, f"{command} whom?")
                return
            actor_msg = cls.EMOTE_MESSAGES[command]['target']['actor']
            room_msg = cls.EMOTE_MESSAGES[command]['target']['room']
            target_msg = cls.EMOTE_MESSAGES[command]['target']['target']
            logger.critical(f"actor_msg: {actor_msg}, room_msg: {room_msg}, target_msg: {target_msg}")

        if target:
            vars = set_vars(actor, actor, target, actor_msg)
            await actor.echo(CommTypes.DYNAMIC, actor_msg, vars)
            await target.echo(CommTypes.DYNAMIC, target_msg, vars)
        else:
            target = actor
            vars = set_vars(actor, actor, actor, actor_msg)
            await actor.echo(CommTypes.DYNAMIC, actor_msg, vars)
        if actor.location_room_:
            if actor.actor_type_ == ActorType.CHARACTER:
                await actor.location_room_.echo(CommTypes.DYNAMIC, "... " + room_msg, vars, exceptions=([actor] if target == None else [actor, target]))
            elif actor.actor_type_ == ActorType.OBJECT:
                await actor.location_room_.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=([actor] if target == None else [actor, target]))
            elif actor.actor_type_ == ActorType.ROOM:
                await actor.location_room_.echo(CommTypes.DYNAMIC, room_msg, vars, exceptions=([actor] if target == None else [actor, target]))
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


    @classmethod
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
        target = cls.game_state.find_target_character(actor, pieces[1], search_world=True)
        if target == None:
            logger.warn(f"({pieces}) Could not find target.")
            await actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
            return
        var_value = ' '.join(pieces[3:])
        vars = set_vars(actor, actor, target, var_value)
        logger.debug3(f"target.name_: {target.name_}, {target_name} var: {pieces[2]}, var_value: {var_value}")
        var_value = replace_vars(var_value, vars)
        target_dict_fn(target)[pieces[2]] = var_value
        await actor.send_text(CommTypes.DYNAMIC, f"Set {target_name} var {pieces[2]} on {target.name_} to {var_value}.")

    @classmethod
    async def cmd_settempvar(cls, actor: Actor, input: str):
        await cls.cmd_setvar_helper(actor, input, lambda d : d.temp_variables_, "temp")

    @classmethod
    async def cmd_setpermvar(cls, actor: Actor, input: str):
        await cls.cmd_setvar_helper(actor, input, lambda d: d.perm_variables_, "perm")


    @classmethod
    async def cmd_show(cls, actor: Actor, input: str):
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Show what?")
            return
        answer = {}
        if pieces[0].lower() == "zones":
            answer["ZONES"] = {
                zone.id_: {"id": zone.id_, "name": zone.name_, "description": zone.description_} 
                for zone in cls.game_state.zones_.values()
            }
        elif pieces[0].lower() == "zone":
            try:
                zone = cls.game_state.zones_[pieces[1]]
            except KeyError:
                await actor.send_text(CommTypes.DYNAMIC, f"zone {pieces[1]} not found.")
                return
            answer["ZONE"] = {}
            answer["ZONE"][zone.id_] = {"id": zone.id_, "name": zone.name_, "description": zone.description_}
            answer["ZONE"][zone.id_]["rooms"] = {
                room.id_: {
                    "id": room.id_,
                    "name": room.name_,
    #                "description": room.description_,
                    "characters": [character.id_ for character in room.characters_],
                    "objects": [object.id_ for object in room.contents_],
                    "triggers": {
                        trigger_type.name: [  # Using trigger_type here, assuming it's an Enum
                            {
                                "criteria": [
                                    f"{criterion.subject_}, {criterion.operator_}, {criterion.predicate_}"
                                    for criterion in trigger.criteria_
                                ]
                            }
                            for trigger in triggers  # Make sure this is the correct variable from room.triggers_by_type_.items()
                        ] 
                        for trigger_type, triggers in room.triggers_by_type_.items()  # Correctly extracting trigger_type and triggers
                    }
                }
                for room in zone.rooms_.values()
            }
        elif pieces[0].lower() == "characters":
            answer["CHARACTERS"] = {
                a.id_ : {
                    "id": a.id_,
                    "name": a.name_,
                    "description": a.description_,
                    "location": a.location_room_.id_ if a.location_room_ else None,
                    "temp_variables": a.temp_variables_,
                    "perm_variables": a.perm_variables_,
                } for a in Actor.references_.values() if a.actor_type_ == ActorType.CHARACTER
            }
        elif pieces[0].lower() == "objects":
            answer["OBJECTS"] = {
                a.id_ : {
                    "id": a.id_,
                    "name": a.name_,
                    "description": a.description_,
                    "location": a.location_room_.id_ if a.location_room_ else None,
                    "temp_variables": a.temp_variables_,
                    "perm_variables": a.perm_variables_,
                } for a in Actor.references_.values() if a.actor_type_ == ActorType.OBJECT and a.location_room_ is not None
            }
        elif pieces[0].lower() == "carried":
            answer["OBJECTS"] = {
                a.id_ : {
                    "id": a.id_,
                    "name": a.name_,
                    "description": a.description_,
                    "inside": f"{article_plus_name(a.article_, a.in_actor_.name_)} ({a.in_actor_.rid})" if a.in_actor_ else None,
                    "temp_variables": a.temp_variables_,
                    "perm_variables": a.perm_variables_,
                } for a in Actor.references_.values() if a.actor_type_ == ActorType.OBJECT and a.in_actor_ is not None
            }
        elif pieces[0].lower() == "room":
            try:
                room = cls.game_state.find_target_room(actor, ' '.join(pieces[1:]), actor.location_room_.zone_)
            except KeyError:
                await actor.send_text(CommTypes.DYNAMIC, f"room '{' '.join(pieces[1])} not found.")
                return
            answer["ROOMS"] = {
                room.id_: {
                    "id": room.id_,
                    "name": room.name_,
                    "description": room.description_,
                    "characters": [character.id_ for character in room.characters_],
                    "objects": [object.id_ for object in room.contents_],
                    "triggers": {
                        trigger_type.name: [  # Using trigger_type here, assuming it's an Enum
                            trigger.to_dict() for trigger in triggers  # Make sure this is the correct variable from room.triggers_by_type_.items()
                        ] 
                        for trigger_type, triggers in room.triggers_by_type_.items()  # Correctly extracting trigger_type and triggers
                    }
                }
            }
        yaml_answer = yaml.dump(answer)
        # yaml_answer = YamlDumper.to_yaml_compatible_str(answer)

        # yaml_answer = YamlDumper.to_yaml_compatible_str(answer["ROOMS"]["starting_room_2"]["triggers"])
        # yaml_answer = yaml_answer + "\n\n" + yaml.dump(answer["ROOMS"]["starting_room_2"]["triggers"])

        await actor.send_text(CommTypes.STATIC, yaml_answer)


    @classmethod
    async def cmd_look(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_look()> ")
        from .nondb_models.triggers import TriggerType, Trigger
        # TODO:M: add various look permutations
        room = actor.location_room_
        pieces = input.split(' ')
        if input.strip() == "":
            await actor.send_text(CommTypes.DYNAMIC, "You look around.")
            await CoreActions.do_look_room(actor, room)
            return
        found = False

        # character?
        logger.debug("looking for characters")
        target = cls.game_state.find_target_character(actor, input, search_zone=False, search_world=False)
        if target:
            logger.debug("found character")
            await CoreActions.do_look_character(actor, target)
            return
        # object?
        logger.debug("looking for objects")
        target = cls.game_state.find_target_object(target_name=input, actor=None, equipped=None,
                                            start_room=actor.location_room_, start_zone=None, search_world=False)

        if target:
            logger.debug("found object")
            await CoreActions.do_look_object(actor, target)
            return

        try:
            logger.debug3(f"target: {input}")
            logger.debug3("Blah Looking for CATCH_LOOK triggers")
            # print(yaml.dump(room.triggers_by_type_))
            # print("**** should have dumped ****")
            logger.debug3(f"Still looking for CATCH_LOOK triggers {room.id_}")
            logger.debug3(f"heh 2 {room.triggers_by_type_.keys()}")
            for trig in room.triggers_by_type_[TriggerType.CATCH_LOOK]:
                logger.debug3(f"checking trigger for: {trig.criteria_[0].subject_}")
                logger.debug3("before trig.run")
                vars = set_vars(actor, actor, actor, input)
                if await trig.run(actor, input, vars):
                    found = True
                logger.debug3("after trig.run")
            logger.debug3(f"done looking for CATCH_LOOK triggers {room.id_}")
        except Exception as ex:
            logger.debug3(f"excepted looking for CATCH_LOOK triggers: {ex}")
            pass
        if not found:
            await actor.send_text(CommTypes.DYNAMIC, "You don't see that.")


    @classmethod
    async def cmd_spawn(cls, actor: Actor, input: str):
        # TODO:L: what if an object in a container spawns something?
        logger = CustomDetailLogger(__name__, prefix="cmd_spawn()> ")
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn char or obj?")
            return
        if pieces[0].lower() == "char":
            character_def = cls.game_state.world_definition_.find_character_definition(' '.join(pieces[1:]))
            if not character_def:
                await actor.send_text(CommTypes.DYNAMIC, f"Couldn't find a character definition for {pieces[1:]}.")
                return
            new_character = Character.create_from_definition(character_def)
            cls.game_state.characters_.append(new_character)
            new_character.location_room_ = actor.location_room_
            new_character.location_room_.add_character(new_character)
            logger.debug(f"new_character: {new_character} added to room {new_character.location_room_.rid}")
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {article_plus_name(new_character.article_, new_character.name_)}.")
            await CoreActions.do_look_room(actor, actor.location_room_)
        elif pieces[0].lower() == "obj":
            object_def = cls.game_state.world_definition_.find_object_definition(' '.join(pieces[1:]))
            if not object_def:
                await actor.send_text(CommTypes.DYNAMIC, f"Couldn't find an object definition for {pieces[1:]}.")
                return
            new_object = Object.create_from_definition(object_def)
            logger.debug(f"new_object: {new_object}")
            if actor.actor_type_ == ActorType.CHARACTER:
                logger.debug("adding to character")
                actor.add_object(new_object, True)
                logger.debug(f"new_object: {new_object} added to character {actor}")
                logger.debug(f"actor.contents_ length: {len(actor.contents_)}")
                # print(Object.collapse_name_multiples(actor.contents_, ","))
            elif actor.actor_type_ == ActorType.OBJECT:
                if actor.object_flags_.are_flags_set(ObjectFlags.IS_CONTAINER):
                    logger.debug("adding to container")
                    actor.add_object(new_object, True)
                    logger.debug(f"new_object: {new_object} added to container {actor}")
                    # print(Object.collapse_name_multiples(actor.contents_, ","))
                else:
                    logger.debug("adding to room")
                    actor.location_room_.add_object(new_object)
                    logger.debug(f"new_object: {new_object} added to room {actor.location_room_}")
                    # print(Object.collapse_name_multiples(actor.location_room_.contents_, ","))
            elif actor.actor_type_ == ActorType.ROOM:
                    logger.debug("adding to room")
                    actor.add_object(new_object)
                    logger.debug(f"new_object: {new_object} added to room {actor}")
                    # print(Object.collapse_name_multiples(actor.contents_, ","))
            else:
                raise NotImplementedError(f"ActorType {actor.actor_type_} for object not implemented.")
            await actor.send_text(CommTypes.DYNAMIC, f"You spawn {article_plus_name(new_object.article_, new_object.name_)}.")
        else:
            await actor.send_text(CommTypes.DYNAMIC, "Spawn what?")
            return
    

    @classmethod
    async def cmd_goto(cls, actor: Actor, input: str):
        pieces = input.lower().split(' ')
        if pieces[0] == "char":
            target = cls.game_state.find_target_character(actor, ' '.join(pieces[1:]), search_world=True)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that character?")
                return
            actor.location_room_.remove_character(actor)
            target.location_room_.add_character(actor)
            await actor.send_text(CommTypes.DYNAMIC, f"You go to {target.rid}.")
        elif pieces[0] == "room":
            target_room = cls.game_state.find_target_room(actor, ' '.join(pieces[1:]), actor.location_room_.zone_)
            if target_room == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that room?")
                return
            actor.location_room_.remove_character(actor)
            target_room.add_character(actor)
        else:
            await actor.send_text(CommTypes.DYNAMIC, "goto where?")


    @classmethod
    async def cmd_list(cls, actor: Actor, input: str):
        await actor.send_text(CommTypes.DYNAMIC, "list not yet implemented")


    @classmethod
    async def cmd_attack(cls, command: str, actor: Actor, input: str):
        target = cls.game_state.find_target_character(actor, input)
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, "{command} whom?")
            return
        await CoreActions.start_fighting(actor, target)
        # TODO:L: maybe some situations where target doesn't retaliate?
        await CoreActions.start_fighting(target, actor)


    @classmethod
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
            target = cls.game_state.find_target_character(actor, input)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "inspect what?")
                return
            msg_parts.append(f"You inspect {target.name_}.")
        if target.actor_type_ == ActorType.CHARACTER:
            if actor.game_permission_flags_.are_flags_set(GamePermissionFlags.IS_ADMIN):
                msg_parts.append( 
    # IS_ADMIN
    f"""
    ID: {actor.id_} ({actor.reference_number_})""")
            msg_parts.append(
    # ALWAYS
    f"""
    Name: {actor.name_}
    Description: {actor.description_}
    Health: {actor.get_status_description()}""")
            if actor.game_permission_flags_.are_flags_set(GamePermissionFlags.IS_ADMIN):
                msg_parts.append(
    # IS_ADMIN
    f"""
    Hit Points: {actor.current_hit_points_} / {actor.max_hit_points_}""")
                if not target.permanent_character_flags_.are_flags_set(CharacterFlags.IS_PC):
                    msg_parts.append(f" ({target.hit_dice_}d{target.hit_dice_size_}+{target.hit_modifier_})\n")
                else: # PC
                    msg_parts.append("\n")
                msg_parts.append(
    # IS_ADMIN
    f"""
    Location: {target.location_room_.name_} ({target.location_room_.id_})""")
            else:
                msg_parts.append(
    # NOT IS_ADMIN
    f"""
    Location: {target.location_room_.name_}""")

            msg_parts.append(
    # ALWAYS
    f"""
    Hit Modifier: {target.hit_modifier_}  /  Critical Hit: {target.critical_chance_}% (Critical Damage: {target.critical_multiplier_}x)
    Dodge Chance: {target.dodge_dice_number_}d{target.dodge_dice_size_}+{target.dodge_modifier_}""")

            if actor.game_permission_flags_.are_flags_set(GamePermissionFlags.IS_ADMIN):
                msg_parts.append(
    # IS_ADMIN
    f"""
    Character Flags: {target.permanent_character_flags_.to_comma_separated()}
    Triggers ({sum(len(lst) for lst in target.triggers_by_type_.values())}): 
    {"\n".join([f"{key}:\n{',\n'.join([ v.shortdesc() for v in values])}" for key, values in target.triggers_by_type_.items()])}
    Temp variables:
    {"\n".join([f"{key}: {value}" for key, value in target.temp_variables_.items()])}
    Permanent variables:
    {"\n".join([f"{key}: {value}" for key, value in target.perm_variables_.items()])}""")

        await actor.send_text(CommTypes.STATIC, "".join(msg_parts))        


    @classmethod
    async def cmd_inventory(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_inventory()> ")
        msg_parts = [ "You are carrying:\n"]
        if actor.actor_type_ == ActorType.CHARACTER:
            logger.debug(f"char: {actor.rid}")
            if len(actor.contents_) == 0:
                msg_parts.append(" nothing.")
            else:
                msg_parts.append(Object.collapse_name_multiples(actor.contents_, "\n"))
            await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        elif actor.actor_type_ == ActorType.OBJECT:
            logger.debug(f"obj: {actor.rid}")
            if not actor.object_flags_.are_flags_set(ObjectFlags.IS_CONTAINER):
                msg_parts.append(" nothing (you're not a container).")
            else:
                if len(actor.contents_) == 0:
                    msg_parts.append(" nothing.")
                else:
                    msg_parts.append(Object.collapse_name_multiples(actor.contents_, "\n"))
                await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        elif actor.actor_type_ == ActorType.ROOM:
            logger.debug(f"room: {actor.rid}")
            room: Room = actor
            if len(room.contents_) == 0:
                msg_parts.append(" nothing.")
            else:
                msg_parts.append(Object.collapse_name_multiples(room.contents_, "\n"))
            await actor.send_text(CommTypes.STATIC, "".join(msg_parts))
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


    @classmethod
    async def cmd_at(cls, actor: Actor, input: str):
        pieces = input.split(' ')
        if len(pieces) < 1:
            await actor.send_text(CommTypes.DYNAMIC, "At what?")
            return
        cmd = ' '.join(pieces[2:])
        if pieces[0].lower() == "char":
            target = cls.game_state.find_target_character(actor, pieces[1], search_world=True)
            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that character?")
                return
            target_room = target.location_room_
        elif pieces[0].lower() == "room":
            target_room = cls.game_state.find_target_room(actor, pieces[1], actor.location_room_.zone_)
        elif pieces[0].lower() == "obj":
            target = cls.game_state.find_target_object(target_name=pieces[1], actor=None, equipped=None,
                                            start_room=None, start_zone=actor.location_room_.zone_, search_world=False)

            if target == None:
                await actor.send_text(CommTypes.DYNAMIC, "couldn't find that object?")
                return
            # TODO:L: what to do if in a container or corpse?
            target_room = target.location_room_
        await actor.send_text(CommTypes.DYNAMIC, f"Doing '{cmd}' at {target.rid} (room {target_room.rid})")
        original_room = actor.location_room_
        actor.location_room_.remove_character(actor)
        target_room.add_character(actor)
        await cls.process_command(actor, cmd)
        target_room.remove_character(actor)
        original_room.add_character(actor)


    @classmethod
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
        if actor.actor_type_ == ActorType.CHARACTER:
            room = actor.location_room_
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            num_got = 0
            for i in range(qty):
                item = cls.game_state.find_target_object(target_name=item_name, actor=None, equipped=None,
                                                         start_room=room, start_zone=None, search_world=False)
                if item == None:
                    break
                num_got += 1
                room.remove_object(item)
                actor.add_object(item)
                apn = article_plus_name(item.article_, item.name_)
            if num_got == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't see any {item_name} here.")
                return
            if num_got > 1:
                apn = num2words(num_got) + " " + item.name_
            msg = f"You get {apn}."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
            msg = f"{firstcap(actor.name_)} gets you."
            await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
            msg = f"{firstcap(article_plus_name(actor.article_,actor.name_))} gets {apn}."
            await actor.location_room_.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor, item])
            await CoreActions.do_look_room(actor, room)


    @classmethod
    async def cmd_drop(cls, actor: Actor, input: str):
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "Drop what?")
            return
        if actor.actor_type_ == ActorType.CHARACTER:
            room = actor.location_room_
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            item = cls.game_state.find_target_object(input, actor)
            if item == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
                return
            actor.remove_object(item)
            room.add_object(item)
            msg = f"You drop {item.name_}."
            await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
            await CoreActions.do_look_room(actor, room)
            msg = f"{firstcap(actor.name_)} drops you."
            await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
            msg = f"{firstcap(article_plus_name(actor.article_,actor.name_))} drops {article_plus_name(item.article_, item.name_)}."
            await actor.location_room_.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor])
            await CoreActions.do_look_room(actor, room)
        elif actor.actor_type_ == ActorType.OBJECT:
            # TODO:L: what if in a container? to floor?
            # TODO:L: want to drop from container to inv?
            room = actor.location_room_
            if room == None:
                await actor.send_text(CommTypes.DYNAMIC, "You're not in a room.")
                return
            obj: Object = actor
            if not obj.object_flags_.are_flags_set(ObjectFlags.IS_CONTAINER):
                await actor.send_text(CommTypes.DYNAMIC, "You're not a container, so you can't drop anything.")
                return
            item = cls.game_state.find_target_object(input, actor)
            if item == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
                return
            actor.remove_object(item)
            room.add_object(item)
            await actor.send_text(CommTypes.DYNAMIC, f"You drop {item.name_}.")


    @classmethod
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
                    target_object = cls.game_state.find_target_object(item_name, actor)
                    if target_object:
                        return specified_location, target_object

            # If no match found and a location was specified, try including the location in the search
            if specified_location:
                for i in range(1, len(original_words) + 1):
                    for combo in itertools.combinations(original_words, i):
                        item_name = ' '.join(combo)
                        target_object = cls.game_state.find_target_object(item_name, actor)
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

        if actor.actor_type_ != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
        if input == "":
            # await actor.send_text(CommTypes.DYNAMIC, "Equip what?")
            await cls.cmd_equip_list(actor, input)
            return
        # equip_location = EquipLocation.string_to_enum(equip_location_name)
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
            if target_object.equip_locations_ == None or len(target_object.equip_locations_) == 0:
                await actor.send_text(CommTypes.DYNAMIC, f"You can't equip that.")
                return
            for loc in target_object.equip_locations_:
                if actor.equipped_[loc] == None:
                    equip_location = loc
                    break
            if equip_location == None:
                await actor.send_text(CommTypes.DYNAMIC, "There's not an open spot for it.")
                return
        if target_object == None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have any {input}.")
            return
        if actor.equipped_[equip_location] != None:
            await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped there.")
            return
        if target_object.object_flags_.are_flags_set(ObjectFlags.IS_WEAPON):
            if equip_location not in [EquipLocation.MAIN_HAND, EquipLocation.OFF_HAND, EquipLocation.BOTH_HANDS]:
                await actor.send_text(CommTypes.DYNAMIC, "You can't equip that there.")
                return
        if target_object.object_flags_.are_flags_set(ObjectFlags.IS_ARMOR):
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
            if actor.equip_location_[EquipLocation.MAIN_HAND] != None:
                await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped in your main hand.")
                return
            if actor.equip_location_[EquipLocation.OFF_HAND] != None:
                await actor.send_text(CommTypes.DYNAMIC, f"You already have something equipped in your off hand.")
                return
        if equip_location == EquipLocation.OFF_HAND:
            if not actor.character_flags_.are_flags_set(CharacterFlags.CAN_DUAL_WIELD):
                await actor.send_text(CommTypes.DYNAMIC, f"You can't dual wield.")
                return
        actor.remove_object(target_object)
        actor.equip_item(equip_location, target_object)
        msg = f"You equip {target_object.name_}."
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg))
        msg = f"{firstcap(actor.name_)} equips you."
        await target_object.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg))
        msg = f"{firstcap(article_plus_name(actor.article_,actor.name_))} equips {article_plus_name(target_object.article_, target_object.name_)}."
        await actor.location_room_.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, target_object, msg), exceptions=[actor])


    @classmethod
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
                    target_object = cls.game_state.find_target_object(item_name, actor=None,equipped=actor.equipped_)
                    if target_object:
                        logger.debug("found " + item_name + "at " + target_object.equipped_location_.word())
                        return target_object.equipped_location_, target_object
            logger.debug("didn't find it equipped")

            # Try to find a matching object without considering the equip location
            for i in range(1, len(words) + 1):
                for combo in itertools.combinations(words, i):
                    item_name = ' '.join(combo)
                    target_object = cls.game_state.find_target_object(item_name, actor)
                    if target_object:
                        return specified_location, target_object

            # If no match found and a location was specified, try including the location in the search
            if specified_location:
                for i in range(1, len(original_words) + 1):
                    for combo in itertools.combinations(original_words, i):
                        item_name = ' '.join(combo)
                        target_object = cls.game_state.find_target_object(item_name, actor)
                        if target_object:
                            return specified_location, target_object

            # No matching object found
            return None

        if actor.actor_type_ != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can unequip things.")
            return
        if input == "":
            await actor.send_text(CommTypes.DYNAMIC, "Unequip what?")
            return
        if "main hand" in input.lower():
            specified_location = EquipLocation.MAIN_HAND
            target_object = actor.equipped_[EquipLocation.MAIN_HAND]
            if target_object == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
                return
        elif "off hand" in input.lower():
            specified_location = EquipLocation.OFF_HAND
            target_object = actor.equipped_[EquipLocation.OFF_HAND]
            if target_object == None:
                await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
                return
        elif "both hands" in input.lower():
            specified_location = EquipLocation.BOTH_HANDS
            target_object = actor.equipped_[EquipLocation.BOTH_HANDS]
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
        item = actor.equipped_[equip_location]
        if item == None:
            await actor.send_text(CommTypes.DYNAMIC, f"You don't have anything equipped there.")
            return
        actor.unequip_location(equip_location)
        actor.add_object(item, True)
        msg = f"You unequip {item.name_}."
        await actor.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
        msg = f"{firstcap(actor.name_)} unequips you."
        await item.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg))
        msg = f"{firstcap(article_plus_name(actor.article_,actor.name_))} unequips {article_plus_name(item.article_, item.name_)}."
        await actor.location_room_.echo(CommTypes.DYNAMIC, msg, set_vars(actor, actor, item, msg), exceptions=[actor])


    @classmethod
    async def cmd_equip_list(cls, actor: Actor, input: str):
        if actor.actor_type_ != ActorType.CHARACTER:
            await actor.send_text(CommTypes.DYNAMIC, "Only characters can equip things.")
            return
        msg_parts = [ "You are equipped with:\n"]
        for loc in EquipLocation:
            if actor.equipped_[loc] != None:
                msg_parts.append(f"{loc.name}: {article_plus_name(actor.equipped_[loc].article_, actor.equipped_[loc].name_)}\n")
            else:
                msg_parts.append(f"{loc.name}: nothing\n")
        await actor.send_text(CommTypes.STATIC, "".join(msg_parts))


    @classmethod
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


    @classmethod
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
    

    @classmethod
    async def cmd_getlogfilter(cls, actor: Actor, input: str):
        logger = CustomDetailLogger(__name__, prefix="cmd_getlogfilter()> ")
        await actor.send_text(CommTypes.DYNAMIC, f"Logfilter is {','.join(logger.get_allowed_prefixes())}.")

