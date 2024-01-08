from abc import abstractmethod
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
    
    def from_dict(self, values: dict) -> None:
        self.subject_ = values['subject']
        self.operator_ = values['operator']
        self.predicate_ = values['predicate']

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
        if (isinstance(trigger_type, str)):
            self.trigger_type_ = TriggerType[trigger_type.upper()]
        else:
            self.trigger_type_ = trigger_type
        self.criteria_ = []
        self.script_ = ""

    def from_dict(self, values: dict) -> None:
        self.trigger_type_: TriggerType[values['type'].upper()]
        self.criteria_ = [TriggerCriteria().from_dict(crit) for crit in values['criteria']]
        self.script_ = values['script']

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict, var: dict) -> None:
        pass

    async def runScript(self, actor: 'Actor', vars: dict) -> None:
        from ..command_handler import process_command
        for line in self.script_.splitlines():
            await process_command(actor, line, vars)


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
            if not crit.evaluate(vars):
                return
        await self.runScript(actor, vars)

async def run_script(script: str, vars: dict) -> None:
    while script := scripts.process_line(script, vars):
        pass

