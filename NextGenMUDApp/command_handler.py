from .actions import world_move
from .communication import CommTypes
from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from .nondb_models.actors import Actor, ActorType
from .nondb_models import world
import re


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
    "north": lambda char, input: world_move(char, "north"),
    "n": lambda char, input: world_move(char, "north"),
    "south": lambda char, input: world_move(char, "south"),
    "s": lambda char, input: world_move(char, "south"),
    "east": lambda char, input: world_move(char, "east"),
    "e": lambda char, input: world_move(char, "east"),
    "west": lambda char, input: world_move(char, "west"),
    "w": lambda char, input: world_move(char, "west"),
    "echo": lambda char, input: cmd_echo(char, input),
    "echoto": lambda char, input: cmd_echoto(char, input),
    "echoexcept": lambda char, input: cmd_echoexcept(char, input),
    "say": lambda char, input: cmd_say(char, input),
    "tell": lambda char, input: cmd_tell(char, input),
    "emote": lambda char,input: cmd_emote(char, input)
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
            await command_handlers[command](actor, ' '.join(parts[1:]))
        except KeyError:
            logger.error(f"KeyError processing command {command}")
            actor.send_text(CommTypes.DYNAMIC, "Command failure.")


async def cmd_say(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    text = input
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_,
        '*': text }
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
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_,
        '*': text }
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
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_,
        '*': text }
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
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_,
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_,
        'q': actor.pronoun_,
        't': exclude[0].name_, 
        'T': Constants.REFERENCE_SYMBOL + exclude[0].reference_number_, 
        'r': exclude[0].pronoun_,
        '*': text }
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
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_,
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_,
        'q': actor.pronoun_,
        't': target.name_, 
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_, 
        'r': target.pronoun_,
        '*': msg }
    logger.debug("sending message to actor")
    await target.echo(CommTypes.DYNAMIC, msg)
    await actor.send_text(CommTypes.DYNAMIC, f"You tell {target.name_} '{text}'.")


async def cmd_emote(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_emote()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    text = input
    vars = { 
        'a': actor.name_, 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'p': actor.pronoun_,
        's': actor.name_, 
        'S': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'q': actor.pronoun_,
        't': actor.name_, 
        'T': Constants.REFERENCE_SYMBOL + actor.reference_number_, 
        'r': actor.pronoun_,
        '*': text }
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
