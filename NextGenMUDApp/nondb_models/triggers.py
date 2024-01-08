from abc import abstractmethod
from custom_detail_logger import CustomDetailLogger
from enum import Enum
import re

def execute_functions(text: str) -> str:
    # TODO: handle various functions such as $name()
    return text

def replace_vars(text: str, vars: dict) -> str:
    for var, value in vars.items():
        text = text.replace(f"%{var}", value)
    return text

class TriggerType(Enum):
    CATCH_ANY = 1
    CATCH_SAY = 2
    CATCH_TELL = 3

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
        logger.debug(f"checking {self.subject_},{self.operator_},{self.predicate_}")
        subject = execute_functions(replace_vars(self.subject_, vars))
        predicate = execute_functions(replace_vars(self.predicate_, vars))
        logger.debug(f"checking calculated {subject},{self.operator_},{predicate}")
        if self.operator_.lower() == 'contains':
            return predicate.lower() in subject.lower()
        elif self.operator_.lower() == 'matches':
            return re.match(predicate, subject)
        logger.debug(f"returning False")
        return False
    
class Trigger:
    
    def __init__(self, trigger_type: TriggerType) -> None:
        if (isinstance(trigger_type, str)):
            self.trigger_type_ = TriggerType[trigger_type.upper()]
        else:
            self.trigger_type_ = trigger_type
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
    def new_trigger(cls, trigger_type):
        logger = CustomDetailLogger(__name__, prefix="Trigger.new_trigger()> ")
        if type(trigger_type) == str:
            trigger_type = TriggerType[trigger_type.upper()]
        if trigger_type == TriggerType.CATCH_ANY:
            logger.debug("returning TriggerCatchAny")
            return TriggerCatchAny()
        # elif trigger_type == TriggerType.CATCH_TELL:
        #     return CatchTellTrigger()
        else:
            raise Exception(f"Unknown trigger type: {trigger_type}")

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
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
    def __init__(self) -> None:
        super().__init__(TriggerType.CATCH_ANY)

    async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
        logger = CustomDetailLogger(__name__, prefix="TriggerCatchAny.run()> ")
        vars = {**vars, **({ 'a': actor.name_, 'A': actor.reference_number_, 'e': actor.pronoun_, '*': text })}
        logger.debug("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars):
                return
        logger.debug("executing script")
        await self.execute_trigger_script(actor, vars)


