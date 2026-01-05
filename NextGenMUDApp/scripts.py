from .structured_logger import StructuredLogger
from .command_handler import CommandHandler
from .command_handler_interface import CommandHandlerInterface
from .constants import Constants
from .nondb_models.actors import Actor
from .nondb_models.actor_interface import ActorType
from .nondb_models.characters import Character
from .nondb_models.objects import Object
from .nondb_models.rooms import Room
from .comprehensive_game_state import ComprehensiveGameState, live_game_state
from .utility import evaluate_if_condition, replace_vars, to_int, evaluate_functions_in_line, find_matching_parenthesis, split_string_honoring_parentheses, parse_blocks


class ScriptHandler:
    game_state: ComprehensiveGameState = live_game_state

    @classmethod
    async def run_script(cls, actor: Actor, script: str, vars: dict, game_state: ComprehensiveGameState = None):
        logger = StructuredLogger(__name__, prefix="run_script()> ")
        logger.debug3(f"actor.rid: {actor.rid}, script: {script}, vars: {vars}")
        script = replace_vars(script, vars).strip()
        logger.debug3(f"after replace_vars: {script}")
        # while script := await cls.process_line(actor, script, vars):
        #     logger.debug3(f"remaining: {script}")
        #     # pass
        while True:
            # print("*********** run_script")
            # print(script)
            if script.startswith("$if("):
                end_of_condition_pos = find_matching_parenthesis(script, 3)
                condition = script[4:end_of_condition_pos]
                after_condition = script[end_of_condition_pos + 1:].strip()
                blocks = parse_blocks(after_condition)
                logger.debug3("condition: " + condition)
                logger.debug3("blocks: " + str(blocks))
                condition_parts = split_string_honoring_parentheses(condition)
                if_subject = evaluate_functions_in_line(condition_parts[0], vars, cls.game_state)
                if_operator = evaluate_functions_in_line(condition_parts[1], vars, cls.game_state)
                if_predicate = evaluate_functions_in_line(condition_parts[2], vars, cls.game_state)
                condition_result = cls.evaluate_condition(actor, if_subject, if_operator, if_predicate, vars, game_state)
                script = (blocks['true_block'] if condition_result else blocks['false_block']) + '\n' + blocks['remainder']
            else:
                script = (await cls.process_line(actor, script, vars, game_state)).strip()
                logger.debug3(f"remaining: {script}")
            script = script.strip()
            # print("----------------")
            # print("******* script done")
            # print(script)
            # raise Exception("run_script break")
            if not script:
                break



    @classmethod
    async def process_line(cls, actor: Actor, script: str, vars: dict, game_state: ComprehensiveGameState = None):
        logger = StructuredLogger(__name__, prefix="cls.process_line()> ")
        # Process the first command or line
        end = script.find('\n') if '\n' in script else len(script)
        line = script[:end].strip()
        logger.debug3(f"line: {line}")
        remaining_script = script[end:].strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            logger.debug3(f"skipping empty/comment line: {line}")
            return remaining_script

        logger.debug3(f"process_command on line: {line}")
        line = evaluate_functions_in_line(line, vars, cls.game_state)
        logger.debug3(f"line after evaluate_functions_in_line(): {line}")
        logger.debug3(f"should process command on line: {line}")
        
        # For Characters (NPCs/PCs), queue the command for natural timing
        # For Rooms and Objects, execute immediately
        if actor.actor_type == ActorType.CHARACTER:
            # Add to command queue - will be processed on next tick (~0.5s)
            actor.command_queue.append(line)
            logger.debug3(f"queued command for {actor.rid}: {line}")
        else:
            # Rooms and Objects execute immediately
            await CommandHandlerInterface.get_instance().process_command(actor, line, vars, from_script=True)

        return remaining_script



    @classmethod
    def evaluate_condition(cls, actor: Actor, if_subject: str, if_operator: str,
                           if_predicate: str, vars: dict, game_state: ComprehensiveGameState = None) -> bool:
        logger = StructuredLogger(__name__, prefix="cls.evaluate_condition()> ")
        logger.debug3(f"if_subject: {if_subject}, if_operator: {if_operator}, if_predicate: {if_predicate}")
        return evaluate_if_condition(if_subject, if_operator, if_predicate)


    # # Placeholder implementations of the functions
    # def name(item_code, state):
    #     # Implement the logic to return a name based on the item code and state
    #     return "name_of_" + item_code

    # def equipped(target, item_type, state):
    #     # Implement the logic to check if the target has an item of the given type equipped
    #     return "equipped_item_for_" + target

