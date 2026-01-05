from .structured_logger import StructuredLogger
from enum import IntFlag
import re
import random
from typing import Dict, List
from .constants import Constants


def to_int(v) -> int:
    try:
        if type(v) is int:
            return v
        if type(v) is str:
            if v == "":
                return 0
            else:
                return int(float(v))
        return int(v)
    except:
        return -1

# Module-level variable for the compiled regex
# variable_replacement_regex = re.compile(r"%(?!\d)[A-Za-z*#$]+%(?<!\d)")
variable_replacement_regex = re.compile(r"%[A-Za-z_*#$][A-Za-z_*#$0-9]*%")

def replace_match(match, vars):
    # Extract the variable name and replace with the corresponding value from vars
    var_name = match.group()[1:-1]  # Remove the surrounding % signs
    return str(vars.get(var_name, match.group()))  # Replace with value from vars, or keep original if not found

def replace_vars(script, vars: dict) -> str:
    logger = StructuredLogger(__name__, prefix="replace_vars()> ")
    logger.debug3("starting, script:")
    
    if not isinstance(script, str):
        logger.debug3("not str")
        return script

    logger.debug3("is str")
    logger.debug3(f"vars: {vars}")   
    logger.debug3(f"script in : {script}")

    # Use the compiled regex for replacement
    script = variable_replacement_regex.sub(lambda match: replace_match(match, vars), script)

    logger.debug3(f"script out : {script}")
    return script


IF_CONDITIONS = {
    "eq": lambda a,b,c: a == b,
    "neq": lambda a,b,c: a != b,
    "!=": lambda a,b,c: a != b,
    "numeq": lambda a,b,c: to_int(a) == to_int(b),
    "numneq": lambda a,b,c: to_int(a) != to_int(b),
    "numgt": lambda a,b,c: to_int(a) > to_int(b),
    "numlt": lambda a,b,c: to_int(a) < to_int(b),
    "numgte": lambda a,b,c: to_int(a) >= to_int(b),
    "numlte": lambda a,b,c: to_int(a) <= to_int(b),
    "between": lambda a,b,c: to_int(a) <= to_int(b) <= to_int(c),
    "contains": lambda a,b,c: b.lower() in a.lower(),
    "matches": lambda a,b,c: re.match(b, a),
    "true": lambda a,b,c: True,
    "false": lambda a,b,c: False,

}

def evaluate_if_condition(if_subject: str, if_operator: str, if_predicate: str) -> bool:
    logger = StructuredLogger(__name__, prefix="evaluate_if_condition()> ")
    logger.debug3(f"if_subject: {if_subject}, if_operator: {if_operator}, if_predicate: {if_predicate}")

    if if_operator in IF_CONDITIONS:
        try:
            return IF_CONDITIONS[if_operator](if_subject, if_predicate, None)
        except Exception as e:
            logger.warning(f"Exception: {e} when evaluating condition: {if_subject} {if_operator} {if_predicate}")
            return False
    else:
        raise NotImplementedError(f"evaluate_condition() does not support operator {if_operator}")


def find_matching_parenthesis(line, start_index):
    stack = []
    for i in range(start_index, len(line)):
        if line[i] == '(':
            stack.append(i)
        elif line[i] == ')' and stack:
            stack.pop()
            if not stack:
                return i
    return -1  # indicates no matching parenthesis found


def parse_blocks(text):
    stack = []
    true_block = []
    false_block = []
    remainder = []
    current_block = true_block
    capturing = False
    encountered_else = False

    i = 0
    while i < len(text):
        char = text[i]

        if char == '{':
            stack.append(char)
            if capturing:
                current_block.append(char)
            capturing = True
        elif char == '}':
            if stack:
                stack.pop()
                if capturing and stack:
                    current_block.append(char)
                if not stack and not encountered_else:
                    capturing = False
                    current_block = remainder
                elif not stack and encountered_else:
                    capturing = False
                    current_block = remainder
                    encountered_else = False
            else:
                raise ValueError("Unbalanced curly braces")
        else:
            if capturing or not stack:
                current_block.append(char)

            if not stack and not encountered_else and ''.join(remainder).endswith('else'):
                encountered_else = True
                current_block = false_block
                remainder = remainder[:-4]  # Remove 'else' from the remainder

        i += 1

    return {
        'true_block': ''.join(true_block).strip(),
        'false_block': ''.join(false_block).strip(),
        'remainder': ''.join(remainder).strip()
    }


def split_string_honoring_parentheses(s):
    parts = []
    current_part = []
    parentheses_stack = []

    for char in s:
        if char == '(':
            parentheses_stack.append(char)
        elif char == ')':
            if parentheses_stack:
                parentheses_stack.pop()
            else:
                # This handles the case of unbalanced parentheses
                raise ValueError("Unbalanced parentheses in string")
        
        if char == ',' and not parentheses_stack:
            parts.append(''.join(current_part).strip())
            current_part = []
        else:
            current_part.append(char)

    # Add the last part
    parts.append(''.join(current_part).strip())

    return parts


def get_quest_var_wrapper(char_ref: str, var_id: str, game_state: 'GameStateInterface') -> str:
    """Wrapper for quest_schema.get_quest_var to be used in script functions."""
    from .quest_schema import get_quest_var
    from .nondb_models.actors import Actor
    if game_state is None:
        return "false"
    # Handle reference symbol lookup (e.g. |C507 or @C507)
    if char_ref and len(char_ref) > 1 and char_ref[0] in ('|', '@', Constants.REFERENCE_SYMBOL):
        char = Actor.get_reference(char_ref[1:])
    else:
        char = Actor.get_reference(char_ref) if char_ref else None
    if char is None:
        return "false"
    result = get_quest_var(char, var_id)
    if result is None:
        return "false"
    if isinstance(result, bool):
        return "true" if result else "false"
    return str(result)


SCRIPT_FUNCTIONS = {
    "cap" : lambda a,b,c,gs: firstcap(a),
    "name" : lambda a,b,c,gs: a.name_,
    "equipped" : lambda a,b,c,gs: gs.find_target_character(a).equip_location_[to_int(b)],
    "numeq" : lambda a,b,c,gs: "true" if to_int(a) == to_int(b) else "false",
    "numneq" : lambda a,b,c,gs: "true" if to_int(a) != to_int(b) else "false",
    "numgt" : lambda a,b,c,gs: "true" if to_int(a) > to_int(b) else "false",
    "numlt" : lambda a,b,c,gs: "true" if to_int(a) < to_int(b) else "false",
    "numgte" : lambda a,b,c,gs: "true" if to_int(a) >= to_int(b) else "false",
    "numlte" : lambda a,b,c,gs: "true" if to_int(a) <= to_int(b) else "false",
    "between" : lambda a,b,c,gs: "true" if to_int(a) <= to_int(b) <= to_int(c) else "false",
    "random" : lambda a,b,c,gs: str(random.randint(to_int(a), to_int(b))),
    "tempvar" : lambda a,b,c,gs: gs.get_temp_var(a, b),
    "permvar" : lambda a,b,c,gs: gs.get_perm_var(a, b),
    "questvar": lambda a,b,c,gs: get_quest_var_wrapper(a, b, gs),
    "hasiteminv": lambda a,b,c,gs: does_char_have_item_inv(a, b, gs),
    "hasitemeq": lambda a,b,c,gs: does_char_have_item_equipped(a, b, gs),
    "hasitem" : lambda a,b,c,gs: does_char_have_item_anywhere(a, b, gs),
    "locroom": lambda a,b,c,gs: gs.find_target_character(a).current_room_.name_,
    "loczone": lambda a,b,c,gs: gs.find_target_character(a).current_room_.zone_.name_,
    "olocroom": lambda a,b,c,gs: gs.find_target_object(a).current_room_.name_,
    "oloczone": lambda a,b,c,gs: gs.find_target_object(a).current_room_.zone_.name_,
}

# TODO:M: make these handle containers

def does_char_have_item_inv(char_name_or_id: str, item_name_or_id: str, game_state: 'GameStateInterface') -> bool:
    if game_state == None:
        return False
    char = game_state.find_target_character(char_name_or_id)
    return False if char == None else game_state.find_target_object(item_name_or_id, char) != None

def does_char_have_item_equipped(char_name_or_id: str, item_name_or_id: str, game_state:  'GameStateInterface') -> bool:
    if game_state == None:
        return False
    char = game_state.find_target_character(char_name_or_id)
    return False if char == None else game_state.find_target_object(item_name_or_id, None, char.equipped_) != None

def does_char_have_item_anywhere(char_name_or_id: str, item_name_or_id: str, game_state: 'GameStateInterface') -> bool:
    if game_state == None:
        return False
    return does_char_have_item_inv(char_name_or_id, item_name_or_id, game_state) \
        or does_char_have_item_equipped(char_name_or_id, item_name_or_id, game_state)

def try_get(lst: [], idx: int, default=None):
    try:
        return lst[idx]
    except IndexError:
        return default


def evaluate_functions_in_line(line: str, vars: dict, game_state: 'ComprehensiveGameState') -> str:
    from .scripts import ScriptHandler
    logger = StructuredLogger(__name__, prefix="evaluate_functions_in_line()> ")
    logger.debug3(f"line: {line}")
    result_parts = []
    # Loop to find and replace all function calls in the line
    start = 0
    next = line.find('$')
    while next > -1:
        result_parts.append(line[start:next])
        logger.debug3(f"result_parts: {result_parts}")
        fn_start = next + 1
        fn_end = line.find('(', next + 1)
        func_name = line[fn_start:fn_end]
        logger.debug3("func_name: " + func_name)
        args_start = fn_end + 1
        logger.debug3(f"before find_matching_paren: {line[args_start:]}")
        args_end = find_matching_parenthesis(line, args_start - 1)
        logger.debug3(f"args_start: {args_start}, args_end: {args_end}")
        args_str = line[args_start:args_end]
        logger.debug3("args_str: " + args_str)
        arg_parts = split_string_honoring_parentheses(args_str)
        logger.debug3(f"arg_parts: {arg_parts}")
        args = [evaluate_functions_in_line(ap, vars, game_state) for ap in arg_parts]
        logger.debug3(f"func_name: {func_name}, args: {args}")
        # Evaluate the function based on its name and arguments
        if func_name in SCRIPT_FUNCTIONS:
            try:
                arg1 = args[0] if len(args) > 0 else ""
                arg2 = args[1] if len(args) > 1 else ""
                arg3 = args[2] if len(args) > 2 else ""
                result = SCRIPT_FUNCTIONS[func_name](arg1, arg2, arg3, game_state)
            except Exception as e:
                logger.warning(f"Exception: {e} when processing line: {line}")
                result = 'FUNCTION_ERROR: ' + str(e)
        else:
            logger.debug3("Unknown function: " + func_name)
            result = 'UNKNOWN_FUNCTION'

        # Replace the function call in the line with the result
        logger.debug3(f"{func_name} result: {result}")
        result_parts.append(result)
        start = args_end + 1
        next = line.find('$', start) 

    result_parts.append(line[start:])
    retval = ''.join(result_parts)
    logger.debug3("retval: " + retval)
    return retval



def set_vars(actor: 'Actor', subject: 'Actor', target: 'Actor', message: str, additional_vars: dict = {}) -> dict:
    vars = { **{
        'a': actor.art_name if actor else "", 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number if actor else "", 
        'p': actor.pronoun_subject if actor else "",
        'P': actor.pronoun_object if actor else "",
        's': subject.art_name if subject else "", 
        'S': Constants.REFERENCE_SYMBOL + subject.reference_number if subject else "", 
        'q': subject.pronoun_subject if subject else "", 
        'Q': subject.pronoun_object if subject else "", 
        't': target.art_name if target else "",  
        'T': Constants.REFERENCE_SYMBOL + target.reference_number if target else "", 
        'r': target.pronoun_subject if target else "",
        'R': target.pronoun_object if target else "",
    '*': message }, 
    **(actor.actor_vars("a")), 
    **(subject.actor_vars("s") if subject else {}), 
    **(target.actor_vars("t") if target else {}),
    **additional_vars }

    return vars

    
def get_dice_parts(dice_def: str) -> (int,int,int):
    if type(dice_def) is int:
        return (0,0,dice_def)
    parts = dice_def.split('d')
    num_dice = to_int(parts[0])
    if len(parts) != 2:
        # raise ValueError(f"Invalid dice definition: {dice_def}")
        return (0,0,num_dice)
    
    # Handle both positive (+) and negative (-) modifiers
    dice_part = parts[1]
    if '+' in dice_part:
        extra = dice_part.split('+')
        dice_size = to_int(extra[0])
        num_bonus = to_int(extra[1]) if len(extra) > 1 else 0
    elif '-' in dice_part:
        extra = dice_part.split('-')
        dice_size = to_int(extra[0])
        num_bonus = -to_int(extra[1]) if len(extra) > 1 else 0
    else:
        dice_size = to_int(dice_part)
        num_bonus = 0
    return (num_dice, dice_size, num_bonus)

def roll_dice(num_dice: int, dice_size: int, dice_bonus: int = 0) -> int:
    # print(type(num_dice))
    # print(type(dice_size))
    # print(type(dice_bonus))
    total = 0
    for i in range(num_dice):
        total += random.randint(1, dice_size)
    total += dice_bonus
    return total


def firstcap(s: str) -> str:
    return s[0].upper() + s[1:] if s else ""


def article_plus_name(article: str, name: str, cap: bool=False):
    if cap:
        return firstcap(article_plus_name(article, name)) if article != None and article != "" else firstcap(name)
    else:
        return f"{article} {name}" if article != None and article != "" else name


def split_preserving_quotes(text):
    # Regular expression pattern:
    # - Match and capture anything inside quotes (single or double) without the quotes
    # - Or match sequences of non-whitespace characters
    pattern = r'"([^"]*)"|\'([^\']*)\'|(\S+)'

    # Find all matches of the pattern
    matches = re.findall(pattern, text)

    # Flatten the list of tuples, filter out empty strings
    return [item for match in matches for item in match if item]


def seconds_from_ticks(ticks: int) -> int:
    return ticks * Constants.GAME_TICK_SEC

def ticks_from_rounds(rounds: int) -> int:
    return rounds * Constants.TICKS_PER_ROUND

def ticks_from_seconds(seconds: int) -> int:
    return seconds / Constants.GAME_TICK_SEC

def rounds_from_ticks(ticks: int) -> int:
    return ticks / Constants.TICKS_PER_ROUND

