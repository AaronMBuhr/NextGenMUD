from abc import abstractmethod
from .command_handler import processCommand
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
    CATCH_TELL = 2

class TriggerCriteria:
    def __init__(self) -> None:
        self.subject_ = None
        self.operator_ = None
        self.predicate_ = None
    
    @abstractmethod
    def evaluate(self, vars: dict) -> bool:
        subject = execute_functions(replace_vars(self.subject, vars))
        predicate = execute_functions(replace_vars(self.predicate, vars))
        if self.operator_.lower() == 'contains':
            return self.predicate_.lower() in subject.lower()
        elif self.operator_.lower() == 'matches':
            return re.match(self.predicate_, subject)
        
        return False
    
class Trigger:
    
    def __init__(self, trigger_type: TriggerType) -> None:
        self.trigger_type_ = trigger_type
        self.criteria_ = []
        self.script_ = ""

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict, var: dict) -> None:
        pass

    async def runScript(self, actor: 'Actor', vars: dict) -> None:
        for line in self.script_.splitlines():
            await processCommand(actor, line, vars)


# class CatchTellTrigger(Trigger):
#     def __init__(self) -> None:
#         super().__init__(TriggerType.CATCH_TELL)
#         self.criteria_ = ""
#         self.script_ = ""

#     async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
#         if isinstance(self.criteria_, "re") and self.criteria_.match(text) \
#         or self.criteria_ in text.lower():
#             await 
            

class CatchAnyTrigger(Trigger):
    def __init__(self) -> None:
        super().__init__(TriggerType.CATCH_ANY)

    async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
        vars = {**vars, **({ 'a': actor.name_, 'A': actor.reference_number_, '*': text })}
        for crit in self.criteria_:

