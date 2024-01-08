from .actions import world_move
from .communication import CommTypes
from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .nondb_models.actors import Actor, ActorType
from .nondb_models import world
import re

def actor_vars(actor: Actor, name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}


def replace_vars(script: str, vars: dict) -> str:
    for var, value in vars.items():
        script = script.replace("%{" + var + "}", value)
    return script


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
    "north": lambda command, char, input: world_move(char, "north"),
    "n": lambda command, char, input: world_move(char, "north"),
    "south": lambda command, char, input: world_move(char, "south"),
    "s": lambda command, char, input: world_move(char, "south"),
    "east": lambda command, char, input: world_move(char, "east"),
    "e": lambda command, char, input: world_move(char, "east"),
    "west": lambda command, char, input: world_move(char, "west"),
    "w": lambda command, char, input: world_move(char, "west"),
    "echo": lambda command, char, input: cmd_echo(char, input),
    "echoto": lambda command, char, input: cmd_echoto(char, input),
    "echoexcept": lambda command, char, input: cmd_echoexcept(char, input),
    "say": lambda command, char, input: cmd_say(char, input),
    "tell": lambda command, char, input: cmd_tell(char, input),
    "emote": lambda command, char,input: cmd_emote(char, input),
    "settempvar": lambda command, char, input: cmd_settempvar(char, input),
    "setpermvar": lambda command, char, input: cmd_setpermvar(char, input),

#   various emotes
    "kick": lambda command, char, input: cmd_specific_emote(command, char, input),
    "kiss": lambda command, char, input: cmd_specific_emote(command, char, input),
    "lick": lambda command, char, input: cmd_specific_emote(command, char, input),
    "congratulate": lambda command, char, input: cmd_specific_emote(command, char, input),
    "bow": lambda command, char, input: cmd_specific_emote(command, char, input),
    "thank": lambda command, char, input: cmd_specific_emote(command, char, input),
}


async def process_command(actor: Actor, input: str, vars: None):
    logger = CustomDetailLogger(__name__, prefix="process_command()> ")
    logger.debug(f"processing input for actor {actor.id_}: {input}")
    parts = split_preserving_quotes(input)
    command = parts[0]
    if not command in command_handlers:
        logger.debug(f"Unknown command: {command}")
        actor.send_text(CommTypes.DYNAMIC, "Unknown command")
    else:
        try:
            logger.debug(f"Evaluating command: {command}")
            await command_handlers[command](command, actor, ' '.join(parts[1:]))
        except KeyError:
            logger.error(f"KeyError processing command {command}")
            actor.send_text(CommTypes.DYNAMIC, "Command failure.")


async def cmd_say(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    text = input
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_subject_,
        'R': actor.pronoun_object_,
        '*': text }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(actor, "t")) }
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"{actor.name_} says, \"{text}\"", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"{actor.name_} says, \"{text}\"", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {text}, vars, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
    actor.send_text(CommTypes.DYNAMIC, f"You say, \"{text}\"")


async def cmd_echo(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echo()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    text = input
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_subject_,
        'R': actor.pronoun_object_,
        '*': text }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(actor, "t")) }
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, text, vars, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
    actor.send_text(CommTypes.DYNAMIC, f"You echo, \"{text}\"")


async def cmd_echoto(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echoto()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
    if len(input) < 3:
        actor.send_text(CommTypes.DYNAMIC, "Echo what?")
    pieces = split_preserving_quotes(input)
    logger.debug(f"finding target: {pieces[0]}")
    target = world.find_target_character(actor, pieces[0])
    logger.debug(f"target: {target}")
    if target == None:
        actor.send_text(CommTypes.DYNAMIC, "Echo to whom?")
        return
    text = ' '.join(pieces[1:])
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_subject_,
        'R': target.pronoun_object_,
        '*': text }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(target, "t")) }
    msg = f"You echo '{text}' to {target.name_}."
    await target.echo(CommTypes.DYNAMIC, text, vars)
    await actor.send_text(CommTypes.DYNAMIC, msg)


async def cmd_echoexcept(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echoexcept()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
        return
    if len(input) < 3:
        actor.send_text(CommTypes.DYNAMIC, "Echo what?")
    pieces = split_preserving_quotes(input)
    logger.debug(f"finding excludee: {pieces[1]}")
    excludee = world.find_target_character(actor, pieces[1])
    logger.debug(f"excludee: {excludee}")
    if excludee == None:
        actor.send_text(CommTypes.DYNAMIC, "Echo except who?")
        return
    exclude = [ excludee ]
    text = ' '.join(pieces[2:])
    msg = f"To everyone except {exclude[0].name_} you echo '{text}'."
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_,
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_,
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': exclude[0].name_, 
        'T': Constants.REFERENCE_SYMBOL + exclude[0].reference_number_, 
        'r': exclude[0].pronoun_subject_,
        'R': exclude[0].pronoun_object_,
        '*': text }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(exclude[0], "t")) }
    await actor.echo(CommTypes.DYNAMIC, text, vars, exceptions=exclude)
    await actor.send_text(CommTypes.DYNAMIC, msg)


async def cmd_tell(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_tell()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.send_text(CommTypes.DYNAMIC, "Tell who?")
        return
    if len(input) < 3:
        actor.send_text(CommTypes.DYNAMIC, "Tell what?")
    pieces = split_preserving_quotes(input)
    logger.debug(f"finding target: {pieces[0]}")
    target = world.find_target_character(actor, pieces[0])
    logger.debug(f"target: {target}")
    if target == None:
        # actor.send_text(CommTypes.DYNAMIC, "Tell who?")
        # return
        raise Exception("Tell who?")
    text = ' '.join(pieces[1:])
    msg = f"{actor.name_} tells you '{text}'."
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_,
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_,
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_subject_,
        'R': target.pronoun_object_,
        '*': msg }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(target, "t")) }
    logger.debug("sending message to actor")
    await target.echo(CommTypes.DYNAMIC, msg)
    await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name_} '{text}'.")


async def cmd_emote(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    text = input
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_subject_,
        'R': actor.pronoun_object_,
        '*': text }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(actor, "t")) }
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {text}", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {text}", vars, exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {text}, vars, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
    actor.send_text(CommTypes.DYNAMIC, f"You emote, \"{text}\"")


EMOTE_MESSAGES = {
    "kick": { 'actor': "You kick %t.", 'room': "%a kicks %t." , 'target': "%a kicks you."},
    "kiss": { 'actor': "You kiss %t.", 'room': "%a kisses %t.", 'target': "%a kisses you." },
    "lick": { 'actor': "You lick %t.", 'room': "%a licks %t.", 'target': "%a licks you." },
    "congratulate": { 'actor': "You congratulate %t.", 'room': "%a congratulates %t." , 'target': "%a congratulates you."},
    "bow": { 'actor': "You bow to %t.", 'room': "%a bows to %t.", 'target': "%a bows to you." },
    "thank": { 'actor': "You thank %t.", 'room': "%a thanks %t.", 'target': "%a thanks you." },
}

async def cmd_specific_emote(command: str, actor: Actor, input: str):
    # TODO:L: add additional logic for no args, for "me", for objects
    logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
    logger.debug(f"command: {command}, actor: {actor}, input: {input}")
    pieces = split_preserving_quotes(input)
    target = world.find_target_character(actor, pieces[0])
    if target == None:
        actor.send_text(CommTypes.DYNAMIC, f"{command} whom?")
        return
    actor_msg = EMOTE_MESSAGES[command]['actor']
    room_msg = EMOTE_MESSAGES[command]['room']
    target_msg = EMOTE_MESSAGES[command]['target']
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_subject_,
        'R': target.pronoun_object_,
        '*': target_msg }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(target, "t")) }
    await target.echo(CommTypes.DYNAMIC, target_msg, vars)
    vars['*'] = room_msg
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {room_msg}", vars, exceptions=[actor, target])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.echo(CommTypes.DYNAMIC, f"... {actor.name_} {room_msg}", vars, exceptions=[actor, target])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.echo(CommTypes.DYNAMIC, {room_msg}, vars, exceptions=[actor, target])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
    vars['*'] = actor_msg
    await actor.echo(CommTypes.DYNAMIC, actor_msg, vars)

async def cmd_setvar_helper(actor: Actor, input: str, target_dict: dict, target_name: str):
    # TODO:M: add targeting objects and rooms
    pieces = split_preserving_quotes(input)
    if len(pieces) < 2:
        actor.send_text(CommTypes.DYNAMIC, "Set temp var on what kind of target?")
        return
    if pieces[0].lower() != "char":
        actor.send_text(CommTypes.DYNAMIC, "Only character targets allowed at the moment.")
        return
    if len(pieces) < 3:
        actor.send_text(CommTypes.DYNAMIC, "Set temp var on whom?")
        return
    if len(pieces) < 4:
        actor.send_text(CommTypes.DYNAMIC, "Set which temp var?")
        return
    if len(pieces) < 5:
        actor.send_text(CommTypes.DYNAMIC, "Set temp var to what?")
        return
    target = world.find_target_character(actor, pieces[1])
    if target == None:
        actor.send_text(CommTypes.DYNAMIC, f"Could not find target.")
        return
    var_value = ' '.join(pieces[3:])
    vars = { **{ 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_subject_,
        'P': actor.pronoun_object_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_subject_,
        'Q': actor.pronoun_object_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_subject_,
        'R': target.pronoun_object_,
        '*': var_value }, **(actor_vars(actor, "a")), **(actor_vars(actor, "s")), **(actor_vars(target, "t")) }
    var_value = replace_vars(var_value, vars)
    target_dict[pieces[2]] = var_value
    actor.send_text(CommTypes.DYNAMIC, f"Set {target_name} var {pieces[2]} on {target.name_} to {var_value}.")

async def cmd_settempvar(actor: Actor, input: str):
    await cmd_setvar_helper(actor, input, actor.temp_variables_, "temp")

async def cmd_setpermvar(actor: Actor, input: str):
    await cmd_setvar_helper(actor, input, actor.perm_variables_, "perm")
    