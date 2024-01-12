from .constants import Constants
from custom_detail_logger import CustomDetailLogger
from enum import IntFlag
import re
import random
from typing import Dict, List

def to_int(v) -> int:
    if type(v) is int:
        return v
    if type(v) is str:
        if v == "":
            return 0
        else:
            return int(float(v))
    return int(v)


def replace_vars(script, vars: dict) -> str:
    logger = CustomDetailLogger(__name__, prefix="replace_vars()> ")
    logger.debug3("starting, script:")
    # print(script)
    if not type(script) is str:
        logger.debug3("not str")
        return script
    logger.debug3("is str")
    logger.debug3(f"vars: {vars}")   
    logger.debug3(f"script in : {script}")
    for var, value in vars.items():
        # logger.debug3('script.replace("%{"' + var + '"}, ' + value + 'if ' + value + ' is str else str(' + value + '))')
        script = script.replace("%{" + var + "}", value if value is str else str(value))
    logger.debug3(f"script out : {script}")
    return script


def evaluate_if_condition(if_subject: str, if_operator: str, if_predicate: str) -> bool:
    logger = CustomDetailLogger(__name__, prefix="evaluate_if_condition()> ")
    logger.debug3(f"if_subject: {if_subject}, if_operator: {if_operator}, if_predicate: {if_predicate}")

    if if_operator == 'contains':
        return if_predicate.lower() in if_subject.lower()
    elif if_operator == 'eq':
        return if_subject.lower().strip() == if_predicate.lower().strip()
    elif if_operator == "numeq":
        return to_int(if_subject) == to_int(if_predicate)
    elif if_operator == "numneq":
        return to_int(if_subject) != to_int(if_predicate)
    elif if_operator == "numgt":
        return to_int(if_subject) > to_int(if_predicate)
    elif if_operator == "numlt":
        return to_int(if_subject) < to_int(if_predicate)
    elif if_operator == "numgte":
        return to_int(if_subject) >= to_int(if_predicate)
    elif if_operator == "numlte":
        return to_int(if_subject) <= to_int(if_predicate)
    elif if_operator == 'contains':
        return if_predicate.lower() in if_subject.lower()
    elif if_operator == 'matches':
        return re.match(if_predicate, if_subject)
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



def evaluate_functions_in_line(line: str, vars: dict) -> str:
    from .scripts import ScriptHandler
    logger = CustomDetailLogger(__name__, prefix="evaluate_functions_in_line()> ")
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
        args = [evaluate_functions_in_line(ap, vars) for ap in arg_parts]
        logger.debug3(f"func_name: {func_name}, args: {args}")
        # Evaluate the function based on its name and arguments
        if func_name == 'name':
            # result = name(args[0], state)
            raise NotImplementedError("name() function not implemented")
        elif func_name == 'equipped':
            # result = equipped(args[0], args[1], state)
            raise NotImplementedError("equipped() function not implemented")
        # Add more functions here as needed
        elif func_name == "numeq":
            result = "true" if to_int(args[0]) == to_int(args[1]) else "false"
        elif func_name == "numneq":
            result = "true" if to_int(args[0]) != to_int(args[1]) else "false"
        elif func_name == "numgt":
            result = "true" if to_int(args[0]) > to_int(args[1]) else "false"
        elif func_name == "numlt":
            result = "true" if to_int(args[0]) < to_int(args[1]) else "false"
        elif func_name == "numgte":
            result = "true" if to_int(args[0]) >= to_int(args[1]) else "false"
        elif func_name == "numlte":
            result = "true" if to_int(args[0]) <= to_int(args[1]) else "false"
        elif func_name == 'between':
            result = "true" if to_int(args[0]) <= to_int(args[1]) <= to_int(args[2]) else "false"
        elif func_name == 'random':
            result = str(random.randint(to_int(args[0]), to_int(args[1])))
        elif func_name == 'tempvar':
            result = ScriptHandler.get_tempvar(args[0], args[1])
        elif func_name == 'permvar':
            result = ScriptHandler.get_permvar(args[0], args[1])
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


def actor_vars(actor: 'Actor', name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}


def set_vars(actor: 'Actor', subject: 'Actor', target: 'Actor', message: str) -> dict:
    vars = { **{
        'a': actor.name_ if actor else "", 
        'A': Constants.REFERENCE_SYMBOL + actor.reference_number_ if actor else "", 
        'p': actor.pronoun_subject_ if actor else "",
        'P': actor.pronoun_object_ if actor else "",
        's': subject.name_ if subject else "", 
        'S': Constants.REFERENCE_SYMBOL + subject.reference_number_ if subject else "", 
        'q': subject.pronoun_subject_ if subject else "", 
        'Q': subject.pronoun_object_ if subject else "", 
        't': target.name_ if target else "",  
        'T': Constants.REFERENCE_SYMBOL + target.reference_number_ if target else "", 
        'r': target.pronoun_subject_ if target else "",
        'R': target.pronoun_object_ if target else "",
    '*': message }, 
    **(actor_vars(actor, "a")), 
    **(actor_vars(subject, "s") if subject else {}), 
    **(actor_vars(target, "t") if target else {}) }

    return vars

    
def get_dice_parts(dice_def: str) -> (int,int,int):
    if type(dice_def) is int:
        return (0,0,dice_def)
    parts = dice_def.split('d')
    num_dice = to_int(parts[0])
    if len(parts) != 2:
        # raise ValueError(f"Invalid dice definition: {dice_def}")
        return (0,0,num_dice)
    extra = parts[1].split('+')
    dice_size = to_int(extra[0])
    if len(extra) > 1:
        num_bonus = to_int(extra[1])
    else:
        num_bonus = 0
    return (num_dice, dice_size, num_bonus)

def roll_dice(num_dice: int, dice_size: int, dice_bonus: int) -> int:
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


# class FlagBitmap:
#     def __init__(self):
#         self.flags = 0

#     def set_flag(self, flag):
#         self.flags |= flag

#     def clear_flag(self, flag):
#         self.flags &= ~flag

#     def is_flag_set(self, flag):
#         return bool(self.flags & flag)

#     def are_flags_set(self, flags):
#         return self.flags & flags == flags


# class DescriptiveFlags(FlagBitmap):
#     @staticmethod
#     def field_name_safe(index: int) -> str:
#         try:
#             return DescriptiveFlags.field_name(index)
#         except IndexError:
#             return "unknown_flag"

#     def describe(self):
#         descriptions = [self.field_name_safe(flag.value - 1) for flag in type(self) if self & flag]
#         return ', '.join(descriptions)

#     # Placeholder for the field_name method. To be implemented in child classes.
#     @staticmethod
#     def field_name(idx):
#         raise NotImplementedError("This method should be implemented in child classes.")

class DescriptiveFlags(IntFlag):

    def __init__(self, value=0, *args, **kwargs):
        super().__init__(value)

    @classmethod
    def field_name_safe(cls, index: int) -> str:
        try:
            return cls.field_name(index)
        except IndexError:
            return "unknown_flag"

    @classmethod
    def field_name(cls, index: int):
        raise NotImplementedError("This method should be overridden in a child class")

    def to_comma_separated(self):
        # Generate a comma-separated list of descriptions for all enabled flags
        return ', '.join(self.field_name_safe(flag.value.bit_length() - 1) for flag in self.__class__ if flag in self)


    def add_flags(self, flags):
        # Add one or more flags
        if isinstance(flags, self.__class__):
            return self | flags
        elif isinstance(flags, int):
            return self.__class__(self.value | flags)
        else:
            raise ValueError("Invalid flag or flag combination")

    def minus_flags(self, flags):
        # Remove one or more flags
        if isinstance(flags, self.__class__):
            return self & ~flags
        elif isinstance(flags, int):
            return self.__class__(self.value & ~flags)
        else:
            raise ValueError("Invalid flag or flag combination")

    def add_flag_name(self, flag_name):
        # Add a flag by its name
        flag_name = flag_name.upper().replace(" ", "_")  # Convert to the expected enum name format
        if flag_name in self.__class__.__members__:
            flag = self.__class__.__members__[flag_name]
            return self.add_flags(flag)
        else:
            raise ValueError(f"Invalid flag name: {flag_name}")


    def are_flags_set(self, flags):
        # Check if each flag in a bitwise OR combination is set
        if isinstance(flags, self.__class__):
            for flag in self.__class__:
                if flags & flag and not self & flag:
                    return False
            return True
        else:
            raise ValueError("Invalid flag or flag combination")

    def are_flags_list_set(self, *flags):
        # Check if multiple specified flags are all set
        for flag in flags:
            if not isinstance(flag, self.__class__):
                raise ValueError(f"Invalid flag: {flag}")
            if not self & flag == flag:
                return False
        return True



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


def actor_vars(actor: 'Actor', name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}

