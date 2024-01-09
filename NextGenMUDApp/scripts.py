from custom_detail_logger import CustomDetailLogger
from . import command_handler
from .constants import Constants
from .nondb_models.actors import Actor, Character, Room, Object
from .operating_state import operating_state
import random

def replace_vars(script: str, vars: dict) -> str:
    for var, value in vars.items():
        script = script.replace("%{" + var + "}", value)
    return script



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


async def run_script(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="run_script()> ")
    logger.debug(f"actor.rid: {actor.rid}, script: {script}, vars: {vars}")
    script = replace_vars(script, vars).strip()
    logger.debug(f"after replace_vars: {script}")
    # while script := await process_line(actor, script, vars):
    #     logger.debug(f"remaining: {script}")
    #     # pass
    while True:
        if script.startswith("$if("):
            end_of_condition_pos = find_matching_parenthesis(script, 3)
            condition = script[4:end_of_condition_pos]
            after_condition = script[end_of_condition_pos + 1:].strip()
            blocks = parse_blocks(after_condition)
            logger.debug("condition: " + condition)
            logger.debug("blocks: " + str(blocks))
            condition_parts = split_string_honoring_parentheses(condition)
            if_subject = evaluate_functions_in_line(actor, condition_parts[0], vars)
            if_operator = evaluate_functions_in_line(actor, condition_parts[1], vars)
            if_predicate = evaluate_functions_in_line(actor, condition_parts[2], vars)
            condition_result = evaluate_condition(actor, if_subject, if_operator, if_predicate, vars)
            script = blocks['true_block'] if condition_result else blocks['false_block'] + '\n' + blocks['remainder']
        else:
            script = (await process_line(actor, script, vars)).strip()
            logger.debug(f"remaining: {script}")
        script = script.strip()
        if not script:
            break



async def process_line(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="process_line()> ")
    # Process the first command or line
    end = script.find('\n') if '\n' in script else len(script)
    line = script[:end].strip()
    logger.debug(f"line: {line}")
    remaining_script = script[end:].strip()

    # Evaluate and replace custom function calls in the line
    # in theory var replacement happened in run_script so this shouldn't be necessary
    # line = replace_vars(line, vars)

    # if line.startswith('$if'):
    #     logger.debug("have $if")
    #     # Find the matching parenthesis for the if condition
    #     start_index = line.find('(')
    #     condition_end = find_matching_parenthesis(line, start_index)
    #     condition = line[4:condition_end].strip()
    #     condition_body = line[condition_end:].lstrip()
    #     logger.debug(f"condition: {condition}, condition_body: {condition_body}")
    #     # true_block_end = condition_body.find('} else {')
    #     # true_block = condition_body[:true_block_end].strip()
    #     # false_block = condition_body[true_block_end + 8:].strip('} ')
    #     if 'else {' in condition_body:
    #         true_block_end = condition_body.find('} else {')
    #         true_block = condition_body[:true_block_end].strip()
    #         false_block = condition_body[true_block_end + 8:].strip('} ')
    #     else:
    #         true_block_end = condition_body.find('}')
    #         true_block = condition_body[:true_block_end].strip()
    #         false_block = ""
    #     # Evaluate the condition
    #     logger.debug(f"true_block: {true_block}, false_block: {false_block}")
    #     if_components = split_string_honoring_parentheses(condition)
    #     if_subject = evaluate_functions_in_line(actor, if_components[0], vars)
    #     if_operator = evaluate_functions_in_line(actor, if_components[1], vars)
    #     if_predicate = evaluate_functions_in_line(actor, if_components[2], vars)
    #     condition_result = evaluate_condition(actor, if_subject, if_operator, if_predicate, vars)
    #     logger.debug(f"condition_result: {condition_result}")
    #     # Choose the correct block and append it to the remaining script
    #     chosen_block = true_block if condition_result else false_block
    #     remaining_script = chosen_block + '\n' + remaining_script
    # else:
    #     logger.debug(f"process_command on line: {line}")
    #     line = evaluate_functions_in_line(actor, line, vars)
    #     logger.debug(f"line after evaluate_functions_in_line(): {line}")
    #     await command_handler.process_command(actor, line, vars)

    logger.debug(f"process_command on line: {line}")
    line = evaluate_functions_in_line(actor, line, vars)
    logger.debug(f"line after evaluate_functions_in_line(): {line}")
    await command_handler.process_command(actor, line, vars)

    return remaining_script


def evaluate_condition(actor: Actor, if_subject: str, if_operator: str, if_predicate: str, vars: dict) -> bool:
    logger = CustomDetailLogger(__name__, prefix="evaluate_condition()> ")
    logger.debug(f"if_subject: {if_subject}, if_operator: {if_operator}, if_predicate: {if_predicate}")

    if if_operator == 'contains':
        return if_predicate.lower() in if_subject.lower()
    elif if_operator == 'eq':
        return if_subject.lower().strip() == if_predicate.lower().strip()
    else:
        raise NotImplementedError(f"evaluate_condition() does not support operator {if_operator}")


def evaluate_functions_in_line(actor: Actor, line: str, vars: dict) -> str:
    logger = CustomDetailLogger(__name__, prefix="evaluate_functions_in_line()> ")
    logger.debug(f"line: {line}")
    result_parts = []
    # Loop to find and replace all function calls in the line
    start = 0
    next = line.find('$')
    while next > -1:
        result_parts.append(line[start:next])
        logger.debug(f"result_parts: {result_parts}")
        fn_start = next + 1
        fn_end = line.find('(', next + 1)
        func_name = line[fn_start:fn_end]
        logger.debug("func_name: " + func_name)
        args_start = fn_end + 1
        logger.debug(f"before find_matching_paren: {line[args_start:]}")
        args_end = find_matching_parenthesis(line, args_start - 1)
        logger.debug(f"args_start: {args_start}, args_end: {args_end}")
        args_str = line[args_start:args_end]
        logger.debug("args_str: " + args_str)
        arg_parts = split_string_honoring_parentheses(args_str)
        logger.debug(f"arg_parts: {arg_parts}")
        args = [evaluate_functions_in_line(actor, ap, vars) for ap in arg_parts]
        logger.debug(f"func_name: {func_name}, args: {args}")
        # Evaluate the function based on its name and arguments
        if func_name == 'name':
            # result = name(args[0], state)
            raise NotImplementedError("name() function not implemented")
        elif func_name == 'equipped':
            # result = equipped(args[0], args[1], state)
            raise NotImplementedError("equipped() function not implemented")
        # Add more functions here as needed
        elif func_name == "numeq":
            result = "true" if int(args[0] or "0") == int(args[1] or "0") else "false"
        elif func_name == "numneq":
            result = "true" if int(args[0] or "0") != int(args[1] or "0") else "false"
        elif func_name == "numgt":
            result = "true" if int(args[0] or "0") > int(args[1] or "0") else "false"
        elif func_name == "numlt":
            result = "true" if int(args[0] or "0") < int(args[1] or "0") else "false"
        elif func_name == "numgte":
            result = "true" if int(args[0] or "0") >= int(args[1] or "0") else "false"
        elif func_name == "numlte":
            result = "true" if int(args[0] or "0") <= int(args[1] or "0") else "false"
        elif func_name == 'between':
            result = "true" if int(args[0] or "0") <= int(args[1] or "0") <= int(args[2] or "0") else "false"
        elif func_name == 'random':
            result = str(random.randint(int(args[0] or "0"), int(args[1] or "0")))
        elif func_name == 'tempvar':
            result = get_tempvar(args[0], args[1])
        elif func_name == 'permvar':
            result = get_permvar(args[0], args[1])
        else:
            logger.debug("Unknown function: " + func_name)
            result = 'UNKNOWN_FUNCTION'

        # Replace the function call in the line with the result
        logger.debug(f"{func_name} result: {result}")
        result_parts.append(result)
        start = args_end + 1
        next = line.find('$', start) 

    result_parts.append(line[start:])
    retval = ''.join(result_parts)
    logger.debug("retval: " + retval)
    return retval

# Placeholder implementations of the functions
def name(item_code, state):
    # Implement the logic to return a name based on the item code and state
    return "name_of_" + item_code

def equipped(target, item_type, state):
    # Implement the logic to check if the target has an item of the given type equipped
    return "equipped_item_for_" + target

# # Example usage
# state = {}
# line = "You have $name($equipped(%t,weapon))"
# processed_line = evaluate_functions_in_line(line, state)
# print(processed_line)

# def evaluate_condition(condition, state):
#     # Evaluate the condition based on the state
#     # ...

#     return True  # Placeholder

# # Example usage
# state = {}  # Placeholder for the state (e.g., inventory)
# script = """
# $if($name($inv(%t,1)),contains,sword)) {
# steal %t sword
# $if($name($inv(%t,1)),contains,sword)) {
# steal %t sword
# }
# }
# """
# # Process the script line by line
# while script:
#     script = process_line(script, state)
#     # Update the state based on the line processed (if needed)


def get_tempvar(source_actor_ptr: str, var_name: str) -> str:
    if source_actor_ptr[0] == Constants.REFERENCE_SYMBOL:
        source_actor_ptr = source_actor_ptr[1:]
    source_actor = Actor.get_reference(source_actor_ptr)
    if not source_actor:
        return ""
    return source_actor.temp_variables_.get(var_name, "")

def get_permvar(source_actor_ptr: str, var_name: str) -> str:
    if source_actor_ptr[0] == Constants.REFERENCE_SYMBOL:
        source_actor_ptr = source_actor_ptr[1:]
    source_actor = Actor.get_reference(source_actor_ptr)
    if not source_actor:
        return ""
    return source_actor.perm_variables_.get(var_name, "")

