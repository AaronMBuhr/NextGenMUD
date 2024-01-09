from abc import abstractmethod
from ..constants import Constants
from custom_detail_logger import CustomDetailLogger
from enum import Enum
import re
import time
from ..core import evaluate_if_condition, replace_vars, evaluate_functions_in_line

def execute_functions(text: str) -> str:
    # TODO: handle various functions such as $name()
    return text

def actor_vars(actor: 'Actor', name: str) -> dict:
    # Using dictionary comprehension to prefix keys and combine dictionaries
    return {f"{name}.{key}": value for d in [actor.temp_variables_, actor.perm_variables_] for key, value in d.items()}

class TriggerType(Enum):
    CATCH_ANY = 1
    CATCH_SAY = 2
    CATCH_TELL = 3
    TIMER_TICK = 4
    CATCH_LOOK = 5

    def __str__(self):
        return "TriggerType." + self.name

class TriggerCriteria:
    def __init__(self) -> None:
        self.subject_ = None
        self.operator_ = None
        self.predicate_ = None
    
    def to_dict(self):
        return {'subject_': self.subject_, 'operator_': self.operator_, 'predicate_': self.predicate_ }

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def from_dict(self, values: dict):
        # logger = CustomDetailLogger(__name__, prefix="TriggerCriteria.from_dict()> ")
        # logger.debug(f"values: {values}")
        # print(values)
        self.subject_ = values['subject']
        self.operator_ = values['operator']
        self.predicate_ = values['predicate']
        return self
        # print(self.to_dict())

    @abstractmethod
    def evaluate(self, vars: dict) -> bool:
        logger = CustomDetailLogger(__name__, prefix="TriggerCriteria.evaluate()> ")
        logger.debug(f"vars: {vars}")
        logger.debug(f"checking {self.subject_},{self.operator_},{self.predicate_}")
        # subject = execute_functions(replace_vars(self.subject_, vars))
        # predicate = execute_functions(replace_vars(self.predicate_, vars))
        if type(self.subject_) is str:
            subject = evaluate_functions_in_line(replace_vars(self.subject_, vars), vars)
        else:
            subject = self.subject_
        if type(self.predicate_) is str:
            predicate = evaluate_functions_in_line(replace_vars(self.predicate_, vars), vars)
        else:
            predicate = self.predicate_
        # if self.subject_ == subject:
        #     raise Exception(f"Unable to replace variables in subject: {self.subject_}")
        logger.debug(f"checking calculated {subject},{self.operator_},{predicate}")
        result = evaluate_if_condition(subject, self.operator_, predicate)
        # if self.operator_.lower() == 'contains':
        #     return predicate.lower() in subject.lower()
        # elif self.operator_.lower() == 'matches':
        #     return re.match(predicate, subject)
        # logger.debug(f"returning False")
        # return False
        return result
    
class Trigger:
    
    def __init__(self, trigger_type: TriggerType, actor: 'Actor') -> None:
        if (isinstance(trigger_type, str)):
            self.trigger_type_ = TriggerType[trigger_type.upper()]
        else:
            self.trigger_type_ = trigger_type
        self.actor_ = actor
        self.criteria_ = []
        self.script_ = ""

    def to_dict(self):
        return {'trigger_type_': self.trigger_type_, 'criteria_': [ c.to_dict() for c in self.criteria_ ], 'script_': self.script_ }

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def from_dict(self, values: dict):
        logger = CustomDetailLogger(__name__, prefix="Trigger.from_dict()> ")
        self.trigger_type_: TriggerType[values['type'].upper()]
        self.criteria_ = [TriggerCriteria().from_dict(crit) for crit in values['criteria']]
        self.script_ = values['script']
        return self
    
    @classmethod
    def new_trigger(cls, trigger_type, actor: 'Actor'):
        logger = CustomDetailLogger(__name__, prefix="Trigger.new_trigger()> ")
        if type(trigger_type) == str:
            trigger_type = TriggerType[trigger_type.upper()]
        if trigger_type == TriggerType.CATCH_ANY:
            logger.debug("returning TriggerCatchAny")
            return TriggerCatchAny(actor)
        elif trigger_type == TriggerType.TIMER_TICK:
            logger.debug("returning TriggerTimerTick")
            return TriggerTimerTick(actor)
        elif trigger_type == TriggerType.CATCH_LOOK:
            logger.debug("returning TriggerCatchLook")
            return TriggerCatchLook(actor)
        # elif trigger_type == TriggerType.CATCH_TELL:
        #     return CatchTellTrigger()
        else:
            raise Exception(f"Unknown trigger type: {trigger_type}")

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict) -> bool:
        raise Exception("Trigger.run() must be overridden.")

    async def execute_trigger_script(self, actor: 'Actor', vars: dict) -> None:
        from ..scripts import run_script
        logger = CustomDetailLogger(__name__, prefix="Trigger.execute_trigger_script()> ")
        # for line in self.script_.splitlines():
        #     logger.debug(f"running script line: {line}")
        #     await process_command(actor, line, vars)
        # script = self.script_
        # while script := process_line(actor, script, vars):
        #     pass
        logger.debug("executing run_script")
        await run_script(actor, self.script_, vars)



# class CatchTellTrigger(Trigger):
#     def __init__(self) -> None:
#         super().__init__(TriggerType.CATCH_TELL)
#         self.criteria_ = ""
#         self.script_ = ""

#     async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
#         if isinstance(self.criteria_, "re") and self.criteria_.match(text) \
#         or self.criteria_ in text.lower():
#             await 
            

class TriggerCatchAny(Trigger):
    def __init__(self, actor: 'Actor') -> None:
        super().__init__(TriggerType.CATCH_ANY, actor)

    async def run(self, actor: 'Actor', text: str, vars: dict) -> bool:
        logger = CustomDetailLogger(__name__, prefix="TriggerCatchAny.run()> ")
        vars = {**vars, 
                **({ 'a': actor.name_, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 'p': actor.pronoun_subject_, 'P': actor.pronoun_object_, '*': text }),
                **(actor_vars(actor, "a"))}
        logger.debug("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars):
                return False
        logger.debug("executing script")
        await self.execute_trigger_script(actor, vars)
        return True


class TriggerTimerTick(Trigger):
    timer_tick_triggers_ = []

    def __init__(self, actor: 'Actor') -> None:
        super().__init__(TriggerType.TIMER_TICK, actor)
        self.last_ticked_ = 0
        TriggerTimerTick.timer_tick_triggers_.append(self)

    async def run(self, actor: 'Actor', text: str, vars: dict) -> bool:
        from ..nondb_models.actors import Actor
        logger = CustomDetailLogger(__name__, prefix="TriggerCatchAny.run()> ")
        if not Actor.get_reference(actor.reference_number_):
            TriggerTimerTick.timer_tick_triggers_.remove(self)
            return False
        time_elapsed = time.time() - self.last_ticked_
        vars = {**vars, 
                **({ 'a': actor.name_, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 'p': actor.pronoun_subject_, 'P': actor.pronoun_object_, '*': text }),
                **(actor_vars(actor, "a"))}
        vars['time_elapsed'] = time_elapsed
        logger.debug("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars):
                return False
        logger.debug("executing script")
        self.last_ticked_ = time.time()
        await self.execute_trigger_script(actor, vars)
        return True

class TriggerCatchLook(Trigger):

    def __init__(self, actor: 'Actor') -> None:
        super().__init__(TriggerType.CATCH_LOOK, actor)

    async def run(self, actor: 'Actor', text: str, vars: dict) -> bool:
        from ..nondb_models.actors import Actor
        logger = CustomDetailLogger(__name__, prefix="TriggerCatchLook.run()> ")
        logger.debug(f"text: {text}")
        vars = {**vars, 
                **({ 'a': actor.name_, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number_, 'p': actor.pronoun_subject_, 'P': actor.pronoun_object_, '*': text }),
                **(actor_vars(actor, "a"))}
        logger.debug("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars):
                return False
        logger.debug("executing script")
        await self.execute_trigger_script(actor, vars)
        return True
    
