from .actions import worldMove
from .communication import CommTypes
from custom_detail_logger import CustomDetailLogger
from .nondb_models.actors import Actor, ActorType
from .nondb_models import world
import re



def split_preserving_quotes(text):
    # Regular expression pattern:
    # - Match and capture anything inside quotes (single or double) without the quotes
    # - Or match sequences of non-whitespace characters
    pattern = r'"(.*?)"|\'(.*?)\'|\S+'

    # Find all matches of the pattern
    matches = re.findall(pattern, text)

    # Flatten the list of tuples and filter out empty strings
    return [item for match in matches for item in match if item]





command_handlers = {
    "north": lambda char, input: worldMove(char, "north"),
    "n": lambda char, input: worldMove(char, "north"),
    "south": lambda char, input: worldMove(char, "south"),
    "s": lambda char, input: worldMove(char, "south"),
    "east": lambda char, input: worldMove(char, "east"),
    "e": lambda char, input: worldMove(char, "east"),
    "west": lambda char, input: worldMove(char, "west"),
    "w": lambda char, input: worldMove(char, "west"),
 #   "tell": lambda char, input: cmd_tell(char, input),
    "echoexcept": lambda char, input: cmd_echoexcept(char, input),
    "say": lambda char, input: cmd_say(char, input)
}

async def process_command(actor: Actor, input: str, vars: None):
    logger = CustomDetailLogger(__name__, prefix="processInput()> ")
    print(f"processing input for actor {actor.id_}: {input}")
    parts = split_preserving_quotes(input)
    command = parts[0]
    if not command in command_handlers:
        if conn := actor.connection_:
            actor.sendText(CommTypes.DYNAMIC, "Unknown command")
    else:
        try:
            await command_handlers[command](conn.character, parts)
        except KeyError:
            logger.error(f"KeyError processing command {command}")
            actor.sendText(CommTypes.DYNAMIC, "Command failure.")

#async def cmd_tell(actor: Actor, input: str):

async def cmd_say(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_say()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.sendText("dynamic", "Say what?")
        return
    text = input[1]
    if actor.location_room_:
        if actor.actor_type_ == ActorType.CHARACTER:
            await actor.location_room_.sendText("dynamic", f"{actor.name_} says, \"{text}\"", exceptions=[actor])
        elif actor.actor_type_ == ActorType.OBJECT:
            await actor.location_room_.sendText("dynamic", f"{actor.name_} says, \"{text}\"", exceptions=[actor])
        elif actor.actor_type_ == ActorType.ROOM:
            await actor.location_room_.sendText("dynamic", {text}, exceptions=[actor])
        else:
            raise NotImplementedError(f"ActorType {actor.actor_type_} not implemented.")
    actor.sendText("dynamic", f"You say, \"{text}\"")

async def cmd_echoexcept(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_echoexcept()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.sendText("dynamic", "Echo except who?")
        return
    if len(input) < 3:
        actor.sendText("dynamic", "Echo what?")
    pieces = split_preserving_quotes(input)
    exclude = [ world.find_target_character(actor, pieces[1]) ]
    text = ' '.join(pieces[2:])
    actor.echo(CommTypes.DYNAMIC, text, exceptions=exclude)
    actor.sendText("dynamic", f"To everyone except {exclude[0].name_} you echo '{text}'.")

async def cmd_tell(actor: Actor, input: str):
    logger = CustomDetailLogger(__name__, prefix="cmd_tell()> ")
    logger.debug(f"actor: {actor}, input: {input}")
    if len(input) < 2:
        actor.sendText("dynamic", "Tell who?")
        return
    if len(input) < 3:
        actor.sendText("dynamic", "Tell what?")
    pieces = split_preserving_quotes(input)
    target = world.find_target_character(actor, pieces[1])
    text = ' '.join(pieces[2:])
    target.echo(CommTypes.DYNAMIC, f"{actor.name_} tells you '{text}'.")
    actor.sendText("dynamic", f"You tell {target.name_} '{text}'.")


        