from custom_detail_logger import CustomDetailLogger
from . import command_handler
from .constants import Constants
from .nondb_models.actors import Actor, Character, Room, Object
from .operating_state import operating_state


def replace_vars(script: str, vars: dict) -> str:
    for var, value in vars.items():
        script = script.replace(f"%{var}", value)
    return script

# # Example usage
# vars = {'t': 'long sword', 'T': 'O12345', 'a': 'city guard', 'A': 'C45678'}
# script = """
# echo The %a picks up the %t.
# get %T
# """

# processed_script = replace_vars(script, vars)
# print(processed_script)


async def run_script(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="run_script()> ")
    logger.debug(f"actor: {actor}, script: {script}, vars: {vars}")
    script = replace_vars(script, vars)
    logger.debug(f"after replace_vars: {script}")
    while script := await process_line(actor, script, vars):
        logger.debug(f"remaining: {script}")
        # pass


async def process_line(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="process_line()> ")
    # Process the first command or line
    end = script.find('\n') if '\n' in script else len(script)
    line = script[:end].strip()
    logger.debug(f"line: {line}")
    remaining_script = script[end:].strip()

    # Evaluate and replace custom function calls in the line
    line = evaluate_functions_in_line(actor, line, vars)
    logger.debug(f"line after evaluate_functions_in_line(): {line}")

    if line.startswith('$if'):
        # Special handling for if-else condition
        # Extract the condition and blocks
        condition_end = line.find(')') + 1
        condition = line[4:condition_end]

        condition_body = line[condition_end:].lstrip()
        # true_block_end = condition_body.find('} else {')
        # true_block = condition_body[:true_block_end].strip()
        # false_block = condition_body[true_block_end + 8:].strip('} ')
        if 'else {' in condition_body:
            true_block_end = condition_body.find('} else {')
            true_block = condition_body[:true_block_end].strip()
            false_block = condition_body[true_block_end + 8:].strip('} ')
        else:
            true_block_end = condition_body.find('}')
            true_block = condition_body[:true_block_end].strip()
            false_block = ""
        # Evaluate the condition
        condition_result = evaluate_condition(actor, condition, vars)
        
        # Choose the correct block and append it to the remaining script
        chosen_block = true_block if condition_result else false_block
        remaining_script = chosen_block + '\n' + remaining_script
    else:
        logger.debug(f"process_command on line: {line}")
        await command_handler.process_command(actor, line, vars)

    return remaining_script


def evaluate_condition(actor: Actor, condition: str, vars: dict) -> bool:
    # Evaluate the condition based on the state
    # ...

    return True  # Placeholder


def evaluate_functions_in_line(actor: Actor, line: str, vars: dict):
    # Loop to find and replace all function calls in the line
    while '$' in line:
        start = line.find('$')
        end = line.find(')', start) + 1
        if end == 0:  # No closing parenthesis found
            break

        function_call = line[start:end]
        func_name, args_str = function_call[1:].split('(', 1)
        args = args_str[:-1].split(',')

        # Evaluate the function based on its name and arguments
        if func_name == 'name':
            result = name(args[0], state)
        elif func_name == 'equipped':
            result = equipped(args[0], args[1], state)
        # Add more functions here as needed
        else:
            result = 'UNKNOWN_FUNCTION'

        # Replace the function call in the line with the result
        line = line.replace(function_call, result, 1)

    return line

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


