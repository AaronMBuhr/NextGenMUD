from abc import abstractmethod
from ..structured_logger import StructuredLogger
from enum import Enum
import re
import time
from .actors import Actor
from .character_interface import PermanentCharacterFlags
from ..constants import Constants
from ..comprehensive_game_state_interface import GameStateInterface
from .trigger_interface import TriggerInterface, TriggerType, TriggerFlags
from ..utility import evaluate_if_condition, replace_vars, evaluate_functions_in_line


class TriggerCriteria:
    def __init__(self) -> None:
        self.subject = None
        self.operator = None
        self.predicate = None
    
    def to_dict(self):
        return {'subject_': self.subject, 'operator_': self.operator, 'predicate_': self.predicate }
    
    def shortdesc(self):
        return f"{self.subject},{self.operator},{self.predicate}"

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def from_dict(self, values: dict):
        logger = StructuredLogger(__name__, prefix="TriggerCriteria.from_dict()> ")
        logger.debug3(f"values: {values}")
        # print(values)
        self.subject = values['subject']
        self.operator = values['operator']
        self.predicate = values['predicate']
        return self
        # print(self.to_dict())

    @abstractmethod
    def evaluate(self, vars: dict, game_state: GameStateInterface) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerCriteria.evaluate()> ")
        logger.debug3(f"vars: {vars}")
        logger.debug3(f"checking {self.subject},{self.operator},{self.predicate}")
        # subject = execute_functions(replace_vars(self.subject_, vars))
        # predicate = execute_functions(replace_vars(self.predicate_, vars))
        if type(self.subject) is str:
            subject = evaluate_functions_in_line(replace_vars(self.subject, vars), vars, game_state)
        else:
            subject = self.subject
        if type(self.predicate) is str:
            predicate = evaluate_functions_in_line(replace_vars(self.predicate, vars), vars, game_state)
        else:
            predicate = self.predicate
        # if self.subject_ == subject:
        #     raise Exception(f"Unable to replace variables in subject: {self.subject_}")
        logger.debug3(f"checking calculated {subject},{self.operator},{predicate}")
        result = evaluate_if_condition(subject, self.operator, predicate)
        # if self.operator_.lower() == 'contains':
        #     return predicate.lower() in subject.lower()
        # elif self.operator_.lower() == 'matches':
        #     return re.match(predicate, subject)
        # logger.debug3(f"returning False")
        # return False
        return result
    
class Trigger(TriggerInterface):
    
    def __init__(self, id: str, trigger_type: TriggerType, actor: 'Actor', disabled=True) -> None:
        from ..scripts import ScriptHandler
        self.id = id
        if (isinstance(trigger_type, str)):
            self.trigger_type_ = TriggerType[trigger_type.upper()]
        else:
            self.trigger_type_ = trigger_type
        self.actor_ = actor
        self.criteria_ = []
        self.script_ = ""
        self.disabled_ = disabled
        self.script_handler_ = ScriptHandler

    def to_dict(self):
        return {'trigger_type_': self.trigger_type_, 'criteria_': [ c.to_dict() for c in self.criteria_ ], 'script_': self.script_ }
    
    def shortdesc(self):
        return f"{self.trigger_type_}: {';'.join([ c.shortdesc() for c in self.criteria_ ])}"

    def __repr__(self):
        fields_dict = self.to_dict()
        fields_info = ', '.join([f"{key}={value}" for key, value in fields_dict.items()])
        return f"{self.__class__.__name__}({fields_info})"

    def from_dict(self, values: dict):
        logger = StructuredLogger(__name__, prefix="Trigger.from_dict()> ")
        self.id = values['id']
        trigger_type_str = values.get('type')
        if trigger_type_str:
            try:
                self.trigger_type_ = TriggerType[trigger_type_str.upper()]
            except KeyError:
                 logger.error(f"Invalid trigger type '{trigger_type_str}' found for trigger ID '{self.id}' on actor '{self.actor_.rid if self.actor_ else 'None'}'")
                 self.trigger_type_ = TriggerType.UNKNOWN
        else:
             logger.error(f"Trigger type missing for trigger ID '{self.id}' on actor '{self.actor_.rid if self.actor_ else 'None'}'")
             self.trigger_type_ = TriggerType.UNKNOWN
             
        self.criteria_ = [TriggerCriteria().from_dict(crit) for crit in values.get('criteria', [])]
        self.script_ = values.get('script', "")
        
        flags_list = values.get('flags', [])
        if flags_list and isinstance(flags_list, list):
            try:
                flags_str = ','.join(flags_list)
                self.flags = TriggerFlags.from_names(flags_str)
            except ValueError as e:
                 logger.error(f"Invalid flag value in trigger {self.id}: {e}")
                 self.flags = TriggerFlags(0)
        else:
            self.flags = TriggerFlags(0)
            
        return self
    
    @classmethod
    def new_trigger(cls, trigger_type, actor: 'Actor', disabled=False):
        logger = StructuredLogger(__name__, prefix="Trigger.new_trigger()> ")
        trigger_id = "temp_id"
        
        if type(trigger_type) == str:
            try:
                trigger_type_enum = TriggerType[trigger_type.upper()]
            except KeyError:
                 logger.error(f"Unknown trigger type string '{trigger_type}' passed to new_trigger for actor '{actor.rid if actor else 'None'}'")
                 raise ValueError(f"Unknown trigger type: {trigger_type}") 
        elif isinstance(trigger_type, TriggerType):
            trigger_type_enum = trigger_type
        else:
            logger.error(f"Invalid trigger_type type ({type(trigger_type)}) passed to new_trigger for actor '{actor.rid if actor else 'None'}'")
            raise TypeError(f"trigger_type must be str or TriggerType enum, got {type(trigger_type)}")

        if trigger_type_enum == TriggerType.CATCH_ANY:
            logger.debug3("returning TriggerCatchAny")
            return TriggerCatchAny(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.TIMER_TICK:
            logger.debug3("returning TriggerTimerTick")
            return TriggerTimerTick(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_LOOK:
            logger.debug3("returning TriggerCatchLook")
            return TriggerCatchLook(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_SAY:
            logger.debug3("returning TriggerCatchSay")
            return TriggerCatchSay(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_ENTER:
            logger.debug3("returning TriggerOnEnter")
            return TriggerOnEnter(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_EXIT:
            logger.debug3("returning TriggerOnExit")
            return TriggerOnExit(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_RECEIVE:
            logger.debug3("returning TriggerOnReceive")
            return TriggerOnReceive(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_GET:
            logger.debug3("returning TriggerOnGet")
            return TriggerOnGet(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_DROP:
            logger.debug3("returning TriggerOnDrop")
            return TriggerOnDrop(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_OPEN:
            logger.debug3("returning TriggerOnOpen")
            return TriggerOnOpen(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_CLOSE:
            logger.debug3("returning TriggerOnClose")
            return TriggerOnClose(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_LOCK:
            logger.debug3("returning TriggerOnLock")
            return TriggerOnLock(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_UNLOCK:
            logger.debug3("returning TriggerOnUnlock")
            return TriggerOnUnlock(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_USE:
            logger.debug3("returning TriggerOnUse")
            return TriggerOnUse(trigger_id, actor, disabled)
        else:
            logger.warning(f"Unhandled trigger type enum: {trigger_type_enum}")
            raise ValueError(f"Unknown or unhandled trigger type: {trigger_type_enum}")

    @abstractmethod
    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface=None) -> bool:
        raise Exception("Trigger.run() must be overridden.")

    def enable(self):
        self.reset_timer()
        self.disabled_ = False

    def disable(self):
        self.disabled_ = True

    def are_flags_set(self, flags: TriggerFlags) -> bool:
        return self.flags.are_flags_set(flags)

    async def execute_trigger_script(self, actor: 'Actor', vars: dict, game_state: GameStateInterface = None) -> None:
        logger = StructuredLogger(__name__, prefix="Trigger.execute_trigger_script()> ")
        # for line in self.script_.splitlines():
        #     logger.debug3(f"running script line: {line}")
        #     await process_command(actor, line, vars)
        # script = self.script_
        # while script := process_line(actor, script, vars):
        #     pass
        logger.debug3("executing execute_trigger_script")
        logger.debug3(f"script: {self.script_}")
        await self.script_handler_.run_script(actor, self.script_, vars, game_state)



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
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_ANY, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerCatchAny.run()> ")
        if self.disabled_:
            return False
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text }),
                **(actor.get_vars("a"))}
        logger.debug3("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        logger.debug3("executing script")
        logger.debug3(f"script: {self.script_}")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerTimerTick(Trigger):
    timer_tick_triggers_ = set()

    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        logger = StructuredLogger(__name__, prefix="TriggerTimerTick.__init__()> ")
        logger.debug3(f"__init__ actor: {actor.id}")
        if not actor or actor == None:
            raise Exception("actor is None")
        super().__init__(id, TriggerType.TIMER_TICK, actor)
        self.last_ticked_ = 0
        if disabled:
            self.disable()
        else:
            self.enable()

    def to_dict(self):
        return {'trigger_type_': self.trigger_type_, 'criteria_': [ c.to_dict() for c in self.criteria_ ], 'disabled_': self.disabled_, 'last_ticked_': self.last_ticked_ }

    def enable(self):
        super().enable()
        TriggerTimerTick.timer_tick_triggers_.add(self)
        # print("trigger enabled: " + repr(self.to_dict()))

    def disable(self):
        super().disable()
        if self in TriggerTimerTick.timer_tick_triggers_:
            TriggerTimerTick.timer_tick_triggers_.remove(self)    

    def reset_timer(self):
        self.last_ticked_ = time.time()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerTimerTick.run()> ")
        if self.disabled_:
            logger.debug3("disabled")
            return False
        if not Actor.get_reference(actor.reference_number) or actor.is_deleted:
            if self in TriggerTimerTick.timer_tick_triggers_:
                TriggerTimerTick.timer_tick_triggers_.remove(self)
            logger.debug3("actor no longer exists")
            return False
        if self.flags.are_flags_set(TriggerFlags.ONLY_WHEN_PC_ROOM):
            pc_here = False
            for ch in actor.location_room.get_characters():
                if ch.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    pc_here = True
                    break
            if not pc_here:
                logger.debug3("pc not in room")
                return False
        if self.flags.are_flags_set(TriggerFlags.ONLY_WHEN_PC_ZONE):
            pc_in_zone = False
            for player in game_state.players_:
                if player.location_room.zone == actor.location_room.zone:
                    pc_in_zone = True
                    break
            if not pc_in_zone:
                logger.debug3("pc not in zone")
                return False
        logger.debug3(f"running, actor: {actor.name} ({actor.rid}) text: {text}")
        logger.debug3(f"actor: {actor.rid}")
        time_elapsed = time.time() - self.last_ticked_
        logger.debug3(f"time_elapsed: {time_elapsed}")
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text }),
                **(actor.get_vars("a"))}
        vars['time_elapsed'] = time_elapsed
        logger.debug3("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        logger.debug3("executing script")
        self.last_ticked_ = time.time()
        logger.debug3(f"script: {self.script_}")
        await self.execute_trigger_script(actor, vars, game_state)
        return True

class TriggerCatchLook(Trigger):

    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_LOOK, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerCatchLook.run()> ")
        if self.disabled_:
            return False
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text }),
                **(actor.get_vars("a"))}
        logger.debug3("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        logger.debug3("executing script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True
    

class TriggerCatchSay(Trigger):
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_SAY, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerCatchSay.run()> ")
        if self.disabled_:
            return False
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text }),
                **(actor.get_vars("a"))}
        logger.debug3("evaluating")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        logger.debug3("executing script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnEnter(Trigger):
    """
    Fires when a character enters the room where this trigger is attached.
    The entering character is the 'actor' for script execution.
    Variables available: %S% = entering character, %s% = character name
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_ENTER, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        """
        Run this trigger when a character enters.
        
        Args:
            actor: The character who just entered the room
            text: Unused for this trigger type
            vars: Variables dict
            game_state: Current game state
            
        Returns:
            True if the trigger executed, False otherwise
        """
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnEnter.run()> ")
        if self.disabled_:
            return False
        
        # Build vars with entering character info
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_enter for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        
        logger.debug3("executing on_enter script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnExit(Trigger):
    """
    Fires when a character exits the room where this trigger is attached.
    The exiting character is the 'actor' for script execution.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_EXIT, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnExit.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_exit for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        logger.debug3("executing on_exit script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnReceive(Trigger):
    """
    Fires when an NPC receives an item via the give command.
    
    Variables available:
    - %S% = the player who gave the item
    - %item% = the item that was given
    - %item_id% = the item's id
    - %item_name% = the item's name
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_RECEIVE, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnReceive.run()> ")
        if self.disabled_:
            return False
        
        # vars should already contain item info from the give command
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_receive for {self.actor_.name}, item: {vars.get('item_id', 'unknown')}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        
        logger.debug3("executing on_receive script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnGet(Trigger):
    """
    Fires when an object is picked up.
    
    Variables available:
    - %S% = the character who picked up the item
    - %item% = the object being picked up
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_GET, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnGet.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_get for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        logger.debug3("executing on_get script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnDrop(Trigger):
    """
    Fires when an object is dropped.
    
    Variables available:
    - %S% = the character who dropped the item
    - %item% = the object being dropped
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_DROP, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnDrop.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_drop for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        logger.debug3("executing on_drop script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnOpen(Trigger):
    """Fires when an object is opened."""
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_OPEN, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnOpen.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnClose(Trigger):
    """Fires when an object is closed."""
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_CLOSE, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnClose.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnLock(Trigger):
    """Fires when an object is locked."""
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_LOCK, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnLock.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnUnlock(Trigger):
    """Fires when an object is unlocked."""
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_UNLOCK, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnUnlock.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnUse(Trigger):
    """
    Fires when an object is used.
    
    Variables available:
    - %S% = the character using the object
    - %target% = the target of the use (if "use X on Y")
    - %target_id% = the target's id
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_USE, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnUse.run()> ")
        if self.disabled_:
            return False
        
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True
