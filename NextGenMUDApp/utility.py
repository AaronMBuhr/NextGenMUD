from .structured_logger import StructuredLogger
from enum import IntFlag
import re
import random
import string
from typing import Any, Dict, List, Tuple
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


def normalize_var_value(s: str) -> Any:
    """
    Convert a string argument for setvar/setquestvar to the appropriate type.
    - "true" (any capitalization) -> True
    - "false" (any capitalization) -> False
    - int-looking strings -> int
    - float-looking strings -> float
    - otherwise -> string unchanged
    """
    if not isinstance(s, str):
        return s
    t = s.strip()
    lower = t.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if "." in t:
        try:
            return float(t)
        except ValueError:
            pass
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return s


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


def parse_text_pattern_tokens(pattern: str) -> List[Tuple[str, any]]:
    """
    Parse a text pattern into tokens for matching.
    
    Returns a list of tuples: ('word', 'text') or ('group', ['alt1', 'alt2', ...])
    """
    tokens = []
    i = 0
    pattern_len = len(pattern)
    
    while i < pattern_len:
        if pattern[i] == '(':
            # Find matching closing paren
            depth = 1
            start = i + 1
            i += 1
            while i < pattern_len and depth > 0:
                if pattern[i] == '(':
                    depth += 1
                elif pattern[i] == ')':
                    depth -= 1
                i += 1
            group_content = pattern[start:i-1]
            # Split by | to get alternatives
            alternatives = [alt.strip() for alt in group_content.split('|')]
            tokens.append(('group', alternatives))
        elif pattern[i].isspace():
            i += 1
        else:
            # Plain word/phrase - read until space or open paren
            start = i
            while i < pattern_len and not pattern[i].isspace() and pattern[i] != '(':
                i += 1
            word = pattern[start:i]
            if word:
                # Handle standalone pipe operator outside parens - treat as alternatives
                if '|' in word:
                    alternatives = [alt.strip() for alt in word.split('|')]
                    tokens.append(('group', alternatives))
                else:
                    tokens.append(('word', word))
    
    return tokens


def matches_text_pattern(text: str, pattern: str) -> bool:
    """
    Match text against a pattern using a grammar with grouping and alternation.
    
    Grammar:
    - (a|b|c) - matches if text contains 'a' OR 'b' OR 'c' (group with alternatives)
    - a|b|c - same as above, parens optional for single group
    - Multiple groups/terms separated by spaces are ANDed together
    
    Examples:
    - "hello" - simple substring match (backward compatible)
    - "(travel|guide)" - matches if text contains "travel" OR "guide"
    - "(oasis|fresh water)" - matches if text contains "oasis" OR "fresh water"
    - "(travel|guide) (oasis|fresh water)" - must match at least one from each group
    - "cave (dark|dim)" - must contain "cave" AND either "dark" or "dim"
    
    Args:
        text: The text to search in
        pattern: The pattern to match against
        
    Returns:
        True if the text matches the pattern, False otherwise
    """
    text_lower = text.lower()
    pattern = pattern.strip()
    
    if not pattern:
        return False
    
    # If no special grammar characters, use simple substring match (backward compatible)
    if '(' not in pattern and '|' not in pattern:
        return pattern.lower() in text_lower
    
    # Parse and evaluate the grammar
    tokens = parse_text_pattern_tokens(pattern)
    
    # All tokens must match (AND logic)
    for token_type, value in tokens:
        if token_type == 'word':
            if value.lower() not in text_lower:
                return False
        elif token_type == 'group':
            # At least one alternative must match (OR logic)
            found = False
            for alt in value:
                if alt.lower() in text_lower:
                    found = True
                    break
            if not found:
                return False
    
    return True


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
    "contains": lambda a,b,c: matches_text_pattern(a, b),
    "matches": lambda a,b,c: re.match(b, a),
    "true": lambda a,b,c: True,
    "false": lambda a,b,c: False,

}

def evaluate_if_condition(condition_str, vars_dict, game_state):
    """
    Evaluates a condition string like "val1, operator, val2"
    """
    # 1. Split the arguments (usually by comma)
    # Ensure we use our parentheses-honoring splitter if nested functions exist
    parts = split_string_honoring_parentheses(condition_str)

    if len(parts) < 3:
        return False

    # --- TARGETED TRIMMING START ---
    # We trim the values and the operator to handle "$if( x , eq , y )"
    val1 = parts[0].strip()
    operator = parts[1].strip().lower()
    # If more than 3 parts, predicate may contain commas (e.g. "xp,contains,xp,scroll" for activation words)
    val2 = ",".join(p.strip() for p in parts[2:]) if len(parts) > 3 else parts[2].strip()
    # --- TARGETED TRIMMING END ---

    # Logic for numeric operators (should always be trimmed)
    if operator in ["numgt", "numlt", "numeq", "numgte", "numlte"]:
        try:
            n1 = float(val1)
            n2 = float(val2)
            if operator == "numgt": return n1 > n2
            if operator == "numlt": return n1 < n2
            if operator == "numeq": return n1 == n2
            if operator == "numgte": return n1 >= n2
            if operator == "numlte": return n1 <= n2
        except ValueError:
            return False

    # Logic for string operators. eq/neq compare after lowercasing so a variable value of
    # True (boolean) or "true" (string, any case) always compares equal to the script
    # literal "true". Script convention: use lowercase true/false in conditions.
    if operator == "eq":
        return val1.lower() == val2.lower()
    if operator == "neq":
        return val1.lower() != val2.lower()
    if operator == "contains":
        # Comma-separated predicate: true if subject contains any of the words (for activation-word lists)
        if "," in val2:
            words = [w.strip().lower() for w in val2.split(",") if w.strip()]
            return any(w in val1.lower() for w in words)
        return val2.lower() in val1.lower()
    if operator == "oneof":
        # val1 is a single value, val2 is comma-separated list; true if val1 equals one of the list entries
        choices = [x.strip().lower() for x in val2.split(",")]
        return val1.strip().lower() in choices

    return False


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
    """Wrapper for nondb_models.quests.get_quest_var to be used in script functions."""
    from .nondb_models.quests import get_quest_var
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

    # --- NEW MATH FUNCTIONS ---
    "add": lambda a,b,c,gs: str(to_int(a) + to_int(b)),
    "sub": lambda a,b,c,gs: str(to_int(a) - to_int(b)),
    "mul": lambda a,b,c,gs: str(to_int(a) * to_int(b)),
    "div": lambda a,b,c,gs: str(int(to_int(a) / to_int(b))) if to_int(b) != 0 else "0",
    "mod": lambda a,b,c,gs: str(to_int(a) % to_int(b)) if to_int(b) != 0 else "0",
    # --------------------------

    "equipped" : lambda a,b,c,gs: gs.find_target_character(None, a).equip_location_[to_int(b)],
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
    "locroom": lambda a,b,c,gs: gs.find_target_character(None, a).current_room_.name_,
    "loczone": lambda a,b,c,gs: gs.find_target_character(None, a).current_room_.zone_.name_,
    "olocroom": lambda a,b,c,gs: gs.find_target_object(a).current_room_.name_,
    "oloczone": lambda a,b,c,gs: gs.find_target_object(a).current_room_.zone_.name_,
    "words": lambda a,b,c,gs: script_words(a, b, c, gs),
}

# TODO:M: make these handle containers

def does_char_have_item_inv(char_name_or_id: str, item_name_or_id: str, game_state: 'GameStateInterface') -> bool:
    if game_state == None:
        return False
    char = game_state.find_target_character(None, char_name_or_id)
    return False if char == None else game_state.find_target_object(item_name_or_id, char) != None

def does_char_have_item_equipped(char_name_or_id: str, item_name_or_id: str, game_state:  'GameStateInterface') -> bool:
    if game_state == None:
        return False
    char = game_state.find_target_character(None, char_name_or_id)
    return False if char == None else game_state.find_target_object(item_name_or_id, None, char.equipped) != None

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


def script_words(text: str, first_str: str, last_str: str, game_state) -> str:
    """
    Extract a range of words from text. Word numbering is 1-based (first word is 1).
    Punctuation (e.g. , . ! ? ) is stripped from word boundaries and ignored when
    determining words; e.g. "Hello, world!" is two words: "Hello", "world".
    $words(text, first, last): returns words from index first to last (inclusive).
    If last < 1 or last > number of words, returns from first to end of text.
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    raw = text.split()
    words = []
    for token in raw:
        w = token.strip(string.punctuation)
        if w:
            words.append(w)
    n = len(words)
    if n == 0:
        return ""
    first = to_int(first_str)
    last = to_int(last_str)
    if first < 1:
        first = 1
    if first > n:
        return ""
    # last < 1 or last > n -> through end
    if last < 1 or last > n:
        last = n
    if last < first:
        return ""
    # 1-based to 0-based slice
    start = first - 1
    end = last
    return " ".join(words[start:end])


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

        # Replace the function call in the line with the result (ensure string for join)
        logger.debug3(f"{func_name} result: {result}")
        result_parts.append(result if isinstance(result, str) else str(result))
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


def generate_article(name: str) -> str:
    """
    Generate the appropriate article ('a', 'an', or '') for a name.
    
    Returns '' if:
    - Name is empty
    - Name already starts with an article ('The ', 'A ', 'An ')
    
    Returns 'an' if name starts with a vowel sound, 'a' otherwise.
    """
    if not name:
        return ""
    
    # Names that already have an article don't need another one
    name_lower = name.lower()
    if name_lower.startswith("the ") or name_lower.startswith("a ") or name_lower.startswith("an "):
        return ""
    
    # Use 'an' for vowels, 'a' for consonants
    return "an" if name[0].lower() in "aeiou" else "a"


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
    return seconds // Constants.GAME_TICK_SEC

def rounds_from_ticks(ticks: int) -> int:
    return ticks // Constants.TICKS_PER_ROUND

