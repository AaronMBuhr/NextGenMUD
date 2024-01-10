from .core import replace_vars
from .actions import world_move
from .communication import CommTypes
from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .nondb_models.actors import Actor, ActorType
from .nondb_models import world
from .operating_state import operating_state, find_target_character
import re
from typing import Callable
from yaml_dumper import YamlDumper
import yaml
from .core import set_vars

def actor_vars(actor: Actor, name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}


def split_preserving_quotes(text):
    # Regular expression pattern:
    # - Match and capture anything inside quotes (single or double) without the quotes
    # - Or match sequences of non-whitespace characters
    pattern = r'"([^"]*)"|\'([^\']*)\'|(\S+)'

    # Find all matches of the pattern
    matches = re.findall(pattern, text)

    # Flatten the list of tuples, filter out empty strings
    return [item for match in matches for item in match if item]


command_handlers = {
    # privileged commands
    "show": lambda command, char, input: cmd_show(char, input),
    "echo": lambda command, char, input: cmd_echo(char, input),
    "echoto": lambda command, char, input: cmd_echoto(char, input),
    "echoexcept": lambda command, char, input: cmd_echoexcept(char, input),
    "settempvar": lambda command, char, input: cmd_settempvar(char, input),
    "setpermvar": lambda command, char, input: cmd_setpermvar(char, input),
    "spawn": lambda command, char, input: cmd_spawn(char,input),

    # normal commands
    "north": lambda command, char, input: world_move(char, "north"),
    "n": lambda command, char, input: world_move(char, "north"),
    "south": lambda command, char, input: world_move(char, "south"),
    "s": lambda command, char, input: world_move(char, "south"),
    "east": lambda command, char, input: world_move(char, "east"),
    "e": lambda command, char, input: world_move(char, "east"),
    "west": lambda command, char, input: world_move(char, "west"),
    "w": lambda command, char, input: world_move(char, "west"),
    "say": lambda command, char, input: cmd_say(char, input),
    "tell": lambda command, char, input: cmd_tell(char, input),
    "emote": lambda command, char,input: cmd_emote(char, input),
    "look": lambda command, char, input: cmd_look(char, input),

    # various emotes
    "kick": lambda command, char, input: cmd_specific_emote(command, char, input),
    "kiss": lambda command, char, input: cmd_specific_emote(command, char, input),
    "lick": lambda command, char, input: cmd_specific_emote(command, char, input),
    "congratulate": lambda command, char, input: cmd_specific_emote(command, char, input),
    "bow": lambda command, char, input: cmd_specific_emote(command, char, input),
    "thank": lambda command, char, input: cmd_specific_emote(command, char, input),
    "sing": lambda command, char, input: cmd_specific_emote(command, char, input),
    "dance": lambda command, char, input: cmd_specific_emote(command, char, input),
    "touch": lambda command, char, input: cmd_specific_emote(command, char, input),
}


async def process_command(actor: Actor, input: str, vars: dict = None):
    try:
        logger = CustomDetailLogger(__name__, prefix="process_command()> ")
        logger.debug3(f"processing input for actor {actor.id_}: {input}")
        parts = split_preserving_quotes(input)
        command = parts[0]
        if not command in command_handlers:
            logger.debug3(f"Unknown command: {command}")
            await actor.send_text(CommTypes.DYNAMIC, "Unknown command")
        else:
            try:
                logger.debug3(f"Evaluating command: {command}")
                await command_handlers[command](command, actor, ' '.join(parts[1:]))
            except KeyError:
                logger.error(f"KeyError processing command {command}")
                await actor.send_text(CommTypes.DYNAMIC, "Command failure.")
    except:
        logger.exception(f"exception handling input '{input}' for actor {actor.rid}")
        raise


async def cmd_say(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
    logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
    text = input
    vars = set_vars(actor, actor, actor, text)
    await actor.send_text(CommTypes.DYNAMIC, f"You say, \"{text}\"")
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"{actor.name_} says, \"{text}\"", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"{actor.name_} says, \"{text}\"", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {text}, vars, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


async def cmd_echo(actor: Actor, input: str):
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


async def cmd_echoto(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echoto()> ")
    logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
    if len(input) < 2:
        await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
    if len(input) < 3:
        await actor.send_text(CommTypes.DYNAMIC, "Echo what?")
    pieces = split_preserving_quotes(input)
    logger.debug3(f"finding target: {pieces[0]}")
    target = find_target_character(actor, pieces[0])
    logger.debug3(f"target: {target}")
    if target == None:
        await actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
        return
    text = ' '.join(pieces[1:])
    vars = set_vars(actor, actor, target, text)
    msg = f"You echo '{text}' to {target.name_}."
    await target.echo(CommTypes.DYNAMIC, text, vars)
    await actor.send_text(CommTypes.DYNAMIC, msg)


async def cmd_echoexcept(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echoexcept()> ")
    logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
    if len(input) < 2:
        await actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
        return
    if len(input) < 3:
        await actor.send_text(CommTypes.DYNAMIC, "Echo what?")
    pieces = split_preserving_quotes(input)
    logger.debug3(f"finding excludee: {pieces[1]}")
    excludee = find_target_character(actor, pieces[1])
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


async def cmd_tell(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_tell()> ")
    logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
    if len(input) < 2:
        await actor.send_text(CommTypes.DYNAMIC, "Tell who?")
        return
    if len(input) < 3:
        await actor.send_text(CommTypes.DYNAMIC, "Tell what?")
    pieces = split_preserving_quotes(input)
    logger.debug3(f"finding target: {pieces[0]}")
    target = find_target_character(actor, pieces[0])
    logger.debug3(f"target: {target}")
    if target == None:
        # actor.send_text(CommTypes.DYNAMIC, "Tell who?")
        # return
        raise Exception("Tell who?")
    text = ' '.join(pieces[1:])
    msg = f"{actor.name_} tells you '{text}'."
    vars = set_vars(actor, actor, target, msg)
    logger.debug3("sending message to actor")
    await target.echo(CommTypes.DYNAMIC, msg)
    await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name_} '{text}'.")


async def cmd_emote(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
    logger.debug3(f"actor.rid: {actor.rid}, input: {input}")
    text = input
    vars = set_vars(actor, actor, actor, text)
    await actor.send_text(CommTypes.DYNAMIC, f"You emote, \"{text}\"")
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {text}", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {text}", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {text}, vars, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


EMOTE_MESSAGES = {
    "kick": { 'notarget' : { 'actor': "You let loose with a wild kick.", 'room': "%a lets loose with a wild kick." },
             'target' : { 'actor': "You kick %t.", 'room': "%a kicks %t." , 'target': "%a kicks you."} },
    "kiss": { 'notarget' : { 'actor': 'You kiss the air.', 'room': '%a kisses the air.'},
             'target': {'actor': "You kiss %t.", 'room': "%a kisses %t.", 'target': "%a kisses you." }},
    "lick": { 'notarget': { 'actor': 'You lick the air.', 'room': '%a licks the air.'},
             'target': {'actor': "You lick %t.", 'room': "%a licks %t.", 'target': "%a licks you." }},
    "congratulate": { 'notarget' : { 'actor' : 'You congratulate yourself.', 'room' : '%a congratulates %Pself.'},
                     'target' : { 'actor': "You congratulate %t.", 'room': "%a congratulates %t." , 'target': "%a congratulates you."}},
    "bow": { 'notarget': { 'actor': 'You take a bow.', 'room': 'Makes a sweeping bow.'}, 
            'target' : {'actor': "You bow to %t.", 'room': "%a bows to %t.", 'target': "%a bows to you." }},
    "thank": { 'notarget': { 'actor' : 'You thank everyone.', 'room' : '%a thanks everyone.' },
              'target' : {'actor': "You thank %t.", 'room': "%a thanks %t.", 'target': "%a thanks you." }},
    "sing": { 'notarget' : {'actor': 'You sing your heart out.', 'room' : '%a sings %P heart out.' },
             'target': {'actor': "You sing to %t.", 'room': "%a sings to %t.", 'target': "%a sings to you." }},
    "dance": { 'notarget' : {'actor': 'You dance a jig.', 'room' : '%a dances a jig.' },
                'target': {'actor': "You dance with %t.", 'room': "%a dances with %t.", 'target': "%a dances with you." }},
                "touch": { 'notarget' : {'actor': 'You touch yourself.', 'room' : '%a touches %Pself.' },
                'target': {'actor': "You touch %t.", 'room': "%a touches %t.", 'target': "%a touches you." }}
    }

async def cmd_specific_emote(command: str, actor: Actor, input: str):
    # TODO:L: add additional logic for no args, for "me", for objects
    logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
    logger.debug3(f"command: {command}, actor.rid: {actor.rid}, input: {input}")
    pieces = split_preserving_quotes(input)
    if len(pieces) < 1:
        actor_msg = EMOTE_MESSAGES[command]["notarget"]['actor']
        room_msg = EMOTE_MESSAGES[command]["notarget"]['room']
        target_msg = None
        target = None
    else:
        target = find_target_character(actor, pieces[0])
        if target == None:
            await actor.send_text(CommTypes.DYNAMIC, f"{command} whom?")
            return
        actor_msg = EMOTE_MESSAGES[command]['actor']
        room_msg = EMOTE_MESSAGES[command]['room']
        target_msg = EMOTE_MESSAGES[command]['target']

    vars = set_vars(actor, actor, actor, actor_msg)
    await actor.echo(CommTypes.DYNAMIC, actor_msg, vars)

    if target:
        vars = set_vars(actor, actor, target, target_msg)
        await target.echo(CommTypes.DYNAMIC, target_msg, vars)
    if actor.location_room_:
        vars = set_vars(actor, actor, actor, room_msg)
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {room_msg}", vars, exceptions=[actor] if target == None else [actor, target])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {room_msg}", vars, exceptions=[actor] if target == None else [actor, target])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {room_msg}, vars, exceptions=[actor] if target == None else [actor, target])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")


async def cmd_setvar_helper(actor: Actor, input: str, target_dict_fn: Callable[[Actor], dict], target_name: str):
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
    target = find_target_character(actor, pieces[1])
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

async def cmd_settempvar(actor: Actor, input: str):
    await cmd_setvar_helper(actor, input, lambda d : d.temp_variables_, "temp")

async def cmd_setpermvar(actor: Actor, input: str):
    await cmd_setvar_helper(actor, input, lambda d: d.perm_variables_, "perm")


async def cmd_show(actor: Actor, input: str):
    pieces = input.split(' ')
    if len(pieces) < 1:
        await actor.send_text(CommTypes.DYNAMIC, "Show what?")
        return
    answer = {}
    if pieces[0].lower() == "zones":
        answer["ZONES"] = {
            zone.id_: {"id": zone.id_, "name": zone.name_, "description": zone.description_} 
            for zone in operating_state.zones_.values()
        }
    elif pieces[0].lower() == "zone":
        try:
            zone = operating_state.zones_[pieces[1]]
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
                "objects": [object.id_ for object in room.objects_],
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
    elif pieces[0].lower() == "room":
        try:
            room = operating_state.find_target_room(actor, ' '.join(pieces[1:]), actor.location_room_.zone_)
        except KeyError:
            await actor.send_text(CommTypes.DYNAMIC, f"room '{' '.join(pieces[1])} not found.")
            return
        answer["ROOMS"] = {
            room.id_: {
                "id": room.id_,
                "name": room.name_,
                "description": room.description_,
                "characters": [character.id_ for character in room.characters_],
                "objects": [object.id_ for object in room.objects_],
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

async def cmd_look(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_look()> ")
    from .nondb_models.triggers import TriggerType, Trigger
    # TODO:M: add various look permutations
    room = actor.location_room_
    pieces = input.split(' ')
    if input.strip() == "":
        await actor.send_text(CommTypes.DYNAMIC, "You look around.")
        await actor.send_text(CommTypes.STATIC, room.name_ + "\n" + room.description_)
        return
    found = False
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


async def cmd_spawn(actor: Actor, input: str):
    character_def = operating_state.character_defs_[input]
    new_character = Actor.create_from_definition(character_def)
    operating_state.characters_.append(new_character)
    new_character.location_room_ = actor.location_room_
    await new_character.location_room_.add_character(new_character)
    await actor.send_text(CommTypes.DYNAMIC, f"You spawn a {input}.")
