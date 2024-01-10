from custom_detail_logger import CustomDetailLogger
from . import command_handler
from .constants import Constants
from .nondb_models.actors import Actor, Character, Room, Object
from .operating_state import operating_state
from .core import evaluate_if_condition, replace_vars, to_int, evaluate_functions_in_line, find_matching_parenthesis, split_string_honoring_parentheses, parse_blocks



async def run_script(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="run_script()> ")
    logger.debug3(f"actor.rid: {actor.rid}, script: {script}, vars: {vars}")
    script = replace_vars(script, vars).strip()
    logger.debug3(f"after replace_vars: {script}")
    # while script := await process_line(actor, script, vars):
    #     logger.debug3(f"remaining: {script}")
    #     # pass
    while True:
        if script.startswith("$if("):
            end_of_condition_pos = find_matching_parenthesis(script, 3)
            condition = script[4:end_of_condition_pos]
            after_condition = script[end_of_condition_pos + 1:].strip()
            blocks = parse_blocks(after_condition)
            logger.debug3("condition: " + condition)
            logger.debug3("blocks: " + str(blocks))
            condition_parts = split_string_honoring_parentheses(condition)
            if_subject = evaluate_functions_in_line(condition_parts[0], vars)
            if_operator = evaluate_functions_in_line(condition_parts[1], vars)
            if_predicate = evaluate_functions_in_line(condition_parts[2], vars)
            condition_result = evaluate_condition(actor, if_subject, if_operator, if_predicate, vars)
            script = blocks['true_block'] if condition_result else blocks['false_block'] + '\n' + blocks['remainder']
        else:
            script = (await process_line(actor, script, vars)).strip()
            logger.debug3(f"remaining: {script}")
        script = script.strip()
        if not script:
            break



async def process_line(actor: Actor, script: str, vars: dict):
    logger = CustomDetailLogger(__name__, prefix="process_line()> ")
    # Process the first command or line
    end = script.find('\n') if '\n' in script else len(script)
    line = script[:end].strip()
    logger.debug3(f"line: {line}")
    remaining_script = script[end:].strip()

    logger.debug3(f"process_command on line: {line}")
    line = evaluate_functions_in_line(line, vars)
    logger.debug3(f"line after evaluate_functions_in_line(): {line}")
    await command_handler.process_command(actor, line, vars)

    return remaining_script



def evaluate_condition(actor: Actor, if_subject: str, if_operator: str, if_predicate: str, vars: dict) -> bool:
    logger = CustomDetailLogger(__name__, prefix="evaluate_condition()> ")
    logger.debug3(f"if_subject: {if_subject}, if_operator: {if_operator}, if_predicate: {if_predicate}")
    return evaluate_if_condition(if_subject, if_operator, if_predicate)



# Placeholder implementations of the functions
def name(item_code, state):
    # Implement the logic to return a name based on the item code and state
    return "name_of_" + item_code

def equipped(target, item_type, state):
    # Implement the logic to check if the target has an item of the given type equipped
    return "equipped_item_for_" + target

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
