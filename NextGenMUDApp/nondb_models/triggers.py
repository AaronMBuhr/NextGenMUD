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

# -----------------------------------------------------------------------------
# trigger_run debug: log only for triggers on actors in the activator's room
# -----------------------------------------------------------------------------
def _trigger_run_should_log(game_state, trigger_owner) -> bool:
    """True if trigger_run debug is on and trigger_owner is in same room as the PC who enabled it."""
    if not game_state or not getattr(game_state, 'is_debug_enabled', lambda n: False)('trigger_run'):
        return False
    get_activator = getattr(game_state, 'get_debug_activator_character', None)
    if not get_activator:
        return False
    activator = get_activator('trigger_run')
    if not activator or not getattr(activator, 'location_room', None):
        return False
    if trigger_owner is None:
        return False
    from .actor_interface import ActorType
    owner_room = (
        trigger_owner
        if getattr(trigger_owner, 'actor_type', None) == ActorType.ROOM
        else getattr(trigger_owner, 'location_room', None)
    )
    return owner_room is not None and owner_room == activator.location_room


def _trigger_run_log(game_state, trigger_owner, msg: str, **kwargs):
    """Emit a [trigger_run] debug log line if trigger_run is on and owner is in activator's room."""
    if not _trigger_run_should_log(game_state, trigger_owner):
        return
    log = StructuredLogger(__name__, prefix="[trigger_run] ")
    parts = [msg]
    for k, v in kwargs.items():
        vstr = repr(v) if len(repr(v)) <= 120 else repr(v)[:117] + "..."
        parts.append(f"{k}={vstr}")
    log.debug(" ".join(parts))


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
        # For "contains" with comma-separated predicate (activation words), match if subject contains any of them
        if self.operator and self.operator.strip().lower() == "contains" and "," in str(predicate):
            words = [w.strip().lower() for w in str(predicate).split(",") if w.strip()]
            subject_lower = str(subject).lower()
            result = any(w in subject_lower for w in words)
        else:
            condition_str = f"{subject},{self.operator},{predicate}"
            result = evaluate_if_condition(condition_str, vars, game_state)
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

        if trigger_type_enum == TriggerType.ON_ANY:
            logger.debug3("returning TriggerOnAny")
            return TriggerOnAny(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.TIMER_TICK:
            logger.debug3("returning TriggerTimerTick")
            return TriggerTimerTick(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_LOOK:
            logger.debug3("returning TriggerCatchLook")
            return TriggerCatchLook(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_SAY:
            logger.debug3("returning TriggerOnSay")
            return TriggerOnSay(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_TELL:
            logger.debug3("returning TriggerOnTell")
            return TriggerOnTell(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_ARRIVE:
            logger.debug3("returning TriggerOnArrive")
            return TriggerOnArrive(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_LEAVE:
            logger.debug3("returning TriggerOnLeave")
            return TriggerOnLeave(trigger_id, actor, disabled)
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
        elif trigger_type_enum == TriggerType.ON_ATTACKED:
            logger.debug3("returning TriggerOnAttacked")
            return TriggerOnAttacked(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_GO:
            logger.debug3("returning TriggerCatchGo")
            return TriggerCatchGo(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_ENTER:
            logger.debug3("returning TriggerOnEnter")
            return TriggerOnEnter(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_ZEROHP:
            logger.debug3("returning TriggerCatchZerohp")
            return TriggerCatchZerohp(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.ON_SIGNAL:
            logger.debug3("returning TriggerOnSignal")
            return TriggerOnSignal(trigger_id, actor, disabled)
        elif trigger_type_enum == TriggerType.CATCH_COMMAND:
            logger.debug3("returning TriggerCatchCommand")
            return TriggerCatchCommand(trigger_id, actor, disabled)
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

    def _trigger_run_debug_log(self, game_state, msg: str, **kwargs):
        """Log for trigger_run debug mode (only when owner is in activator's room)."""
        _trigger_run_log(game_state, self.actor_, msg, **kwargs)

    def get_criteria_summary(self) -> str:
        """Get a human-readable summary of this trigger's criteria."""
        if not self.criteria_:
            return "no criteria"
        
        summaries = []
        for crit in self.criteria_:
            if hasattr(crit, 'subject') and hasattr(crit, 'operator') and hasattr(crit, 'predicate'):
                summaries.append(f"{crit.subject} {crit.operator} '{crit.predicate}'")
            else:
                summaries.append(str(crit))
        return "; ".join(summaries) if summaries else "no criteria"

    async def execute_trigger_script(self, actor: 'Actor', vars: dict, game_state: GameStateInterface = None, 
                                      initiator_ref: str = None, enable_llm_tracking: bool = True) -> None:
        """
        Execute the trigger's script.
        
        Args:
            actor: The actor (NPC/room/object) that owns this trigger
            vars: Variable dictionary for substitution
            game_state: Current game state
            initiator_ref: Reference to the character who triggered this (e.g., %S% value)
            enable_llm_tracking: Whether to track script execution for LLM integration
        """
        logger = StructuredLogger(__name__, prefix="Trigger.execute_trigger_script()> ")
        logger.debug3("executing execute_trigger_script")
        logger.debug3(f"script: {self.script_}")

        # trigger_run debug: detailed log only for triggers in activator's room
        if _trigger_run_should_log(game_state, actor):
            vars_preview = {k: (repr(v)[:80] + "..." if len(repr(v)) > 80 else repr(v)) for k, v in (vars or {}).items()}
            self._trigger_run_debug_log(
                game_state,
                "execute_trigger_script START",
                trigger_id=self.id,
                trigger_type=self.trigger_type_.name,
                owner_rid=getattr(actor, 'rid', None),
                owner_name=getattr(actor, 'name', None),
                owner_id=getattr(actor, 'id', None),
                vars_keys=list((vars or {}).keys()),
                vars_preview=vars_preview,
            )
            _trigger_run_log(game_state, actor, "script", script=self.script_ or "")

        # For Characters with LLM tracking enabled (not TIMER_TICK), wrap script with tracking commands
        from .actor_interface import ActorType
        should_track = (
            enable_llm_tracking and 
            actor.actor_type == ActorType.CHARACTER and
            self.trigger_type_ != TriggerType.TIMER_TICK
        )
        
        if should_track:
            # Get initiator reference from vars if not provided
            if initiator_ref is None:
                initiator_ref = vars.get('S', '')  # %S% is usually the triggering character's reference
            
            # Build criteria summary for LLM context
            criteria_summary = self.get_criteria_summary()
            
            # Build trigger info - use pipe separator since criteria might contain spaces
            trigger_info = f"{self.trigger_type_.name}|{self.id}|{criteria_summary}|{initiator_ref}"
            
            # Queue _trigger_start before script commands
            actor.command_queue.append(f"_trigger_start {trigger_info}")
            
            # Run the script (which queues its commands for Characters)
            await self.script_handler_.run_script(actor, self.script_, vars, game_state)
            
            # Queue _trigger_end after script commands
            actor.command_queue.append("_trigger_end")
        else:
            # No tracking - just run the script normally
            await self.script_handler_.run_script(actor, self.script_, vars, game_state)

        if _trigger_run_should_log(game_state, actor):
            self._trigger_run_debug_log(game_state, "execute_trigger_script DONE", trigger_id=self.id)



# class CatchTellTrigger(Trigger):
#     def __init__(self) -> None:
#         super().__init__(TriggerType.ON_TELL)
#         self.criteria_ = ""
#         self.script_ = ""

#     async def run(self, actor: 'Actor', text: str, vars: dict) -> None:
#         if isinstance(self.criteria_, "re") and self.criteria_.match(text) \
#         or self.criteria_ in text.lower():
#             await 
            

class TriggerOnAny(Trigger):
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_ANY, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnAny.run()> ")
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        if self.disabled_:
            return False
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text }),
                **(actor.get_vars("a"))}
        logger.debug3("evaluating")
        for i, crit in enumerate(self.criteria_):
            result = crit.evaluate(vars, game_state)
            self._trigger_run_debug_log(game_state, f"criterion[{i}]", subject=getattr(crit, 'subject', None), operator=getattr(crit, 'operator', None), predicate=getattr(crit, 'predicate', None), result=result)
            if not result:
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
    

class TriggerOnSay(Trigger):
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_SAY, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnSay.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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


class TriggerOnTell(Trigger):
    """
    Fires when someone directs speech at this actor via sayto, tell, whisper, or ask.
    Does not fire on plain 'say' (room speech); use ON_SAY for that.
    Variables: %s%/%S% = the speaker (who said to you), %a%/%A% = this actor (recipient), %*% = the text said.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_TELL, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'GameStateInterface' = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnTell.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # actor param = trigger owner (this NPC); vars from caller have a/A = speaker, t/T = target (this NPC)
        # Script gets: %s%/%S% = speaker, %a%/%A% = this actor (recipient), %*% = text
        vars = {**(vars or {}),
                's': vars.get('a', '') if vars else '',
                'S': vars.get('A', '') if vars else '',
                'a': self.actor_.name,
                'A': Constants.REFERENCE_SYMBOL + self.actor_.reference_number,
                'p': self.actor_.pronoun_subject,
                'P': self.actor_.pronoun_object,
                '*': text or ''}
        vars.update(self.actor_.get_vars("a"))
        for i, crit in enumerate(self.criteria_):
            result = crit.evaluate(vars, game_state)
            self._trigger_run_debug_log(game_state, f"criterion[{i}]", subject=getattr(crit, 'subject', None), operator=getattr(crit, 'operator', None), predicate=getattr(crit, 'predicate', None), result=result, vars_star=vars.get('*', ''))
            if not result:
                return False
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerCatchCommand(Trigger):
    """
    Fires when the player types a command whose first word is in this trigger's
    comma-separated list of command words. Check order: room, then room objects,
    then room NPCs, then each character's top-level inventory (not container contents).
    Condition: criteria with operator "oneof" and predicate = comma-separated command words.
    Variables: %text% = full command input (including the command word); %*% = command word only (for criteria).
    If the trigger runs, command processing stops.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_COMMAND, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerCatchCommand.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # actor = player who issued the command; self.actor_ = owner (room/object/npc/item)
        vars = {**(vars or {}),
                **({'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number,
                    'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text}),
                **(actor.get_vars("a"))}
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerCatchGo(Trigger):
    """
    Fires when a player uses "go <keyword>" or "enter <keyword>" in the room.
    The keyword is available as %*% for criteria matching.
    Variables available: %S% = player, %s% = player name, %*% = keyword
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_GO, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerCatchGo.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
    Fires when this actor enters a new room (via any means: walk, teleport, etc.).
    Condition: no criteria = any room; otherwise %room_id% contains zone_id, or
    zone_id.subzone_id, or zone_id.subzone_id.room_id.
    Variables: %room_id% = zone_id.subzone_id.room_id of the room being entered;
    %S%/%s% = this actor.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_ENTER, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface = None) -> bool:
        logger = StructuredLogger(__name__, prefix="TriggerOnEnter.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # vars must include room_id (set by caller to zone_id.subzone_id.room_id of room entered)
        vars = {**(vars or {}),
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object,
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        # No criteria = fire on any room entry
        if not self.criteria_:
            logger.debug3("executing on_enter script (no criteria)")
            await self.execute_trigger_script(actor, vars, game_state)
            return True
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        logger.debug3("executing on_enter script")
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnArrive(Trigger):
    """
    Fires when someone arrives at the room/NPC/object where this trigger is attached.
    From the room's perspective: someone else arrives. Variables: %S% = arriving character, %s% = name.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_ARRIVE, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        """
        Run this trigger when someone arrives (actor = the arriving character).
        """
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnArrive.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # Build vars with arriving character info
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_arrive for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        
        logger.debug3("executing on_arrive script")
        # Execute script as the trigger owner (room/npc/object); arriving character is %S%/%s%
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerCatchZerohp(Trigger):
    """
    Fires when damage reduces this actor's HP to 0 or less. If the script sets the actor's HP
    above 0 before finishing, death is cancelled and combat continues. Variables: %a%/%A% = this
    actor (script owner), %s%/%S% = the actor who did the damage, %t%/%T% = this actor (target).
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.CATCH_ZEROHP, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: GameStateInterface = None) -> bool:
        """
        actor = the one who did the damage (subject); self.actor_ = the one who hit 0 HP (script owner/target).
        """
        logger = StructuredLogger(__name__, prefix="TriggerCatchZerohp.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # vars from caller: a/A = damaged (this actor), s/S = damager, t/T = damaged
        vars = {**(vars or {}),
                **({ 'a': self.actor_.name, 'A': Constants.REFERENCE_SYMBOL + self.actor_.reference_number,
                     's': actor.name if actor else '', 'S': Constants.REFERENCE_SYMBOL + actor.reference_number if actor else '',
                     't': self.actor_.name, 'T': Constants.REFERENCE_SYMBOL + self.actor_.reference_number,
                     'p': self.actor_.pronoun_subject, 'P': self.actor_.pronoun_object,
                     'q': self.actor_.pronoun_possessive, '*': text or '' }),
                **(self.actor_.get_vars("a"))}
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerOnSignal(Trigger):
    """
    Fires when a signal is sent to this receiver's scope (room/subzone/zone/world).
    Registers in a class-level registry when enabled; unregisters when disabled.
    Variables: %a%/%A% = signaler (who ran the signal command), %t%/%T% = target (third arg of signal),
    %signal% = signal name, %text% = message (fourth and later words).
    """
    _signal_registry = []  # list of TriggerOnSignal instances; pruned when iterating

    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_SIGNAL, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    def enable(self):
        super().enable()
        if self not in TriggerOnSignal._signal_registry:
            TriggerOnSignal._signal_registry.append(self)

    def disable(self):
        TriggerOnSignal.unregister_trigger(self)
        super().disable()

    @classmethod
    def unregister_trigger(cls, trigger: 'TriggerOnSignal') -> None:
        """Remove the given trigger from the signal registry (e.g. when disabling or in catch_zerohp)."""
        if trigger in cls._signal_registry:
            cls._signal_registry.remove(trigger)

    @classmethod
    def get_receivers_for_scope(cls, signaler_room, scope: str):
        """
        Return list of TriggerOnSignal instances whose receiver is in the given scope.
        scope is 'room' | 'subzone' | 'zone' | 'world'.
        Prunes registry of triggers whose owner is deleted or has no location.
        """
        if not signaler_room:
            return []
        signaler_zone = getattr(signaler_room, 'zone', None)
        signaler_subzone_id = getattr(signaler_room, 'subzone_id', None)
        valid = []
        to_remove = []
        for trig in cls._signal_registry:
            if trig.disabled_:
                to_remove.append(trig)
                continue
            owner = trig.actor_
            if owner is None or getattr(owner, 'is_deleted', False):
                to_remove.append(trig)
                continue
            # Owner was dereferenced (e.g. zone unload) -> no longer in registry
            ref_num = getattr(owner, 'reference_number', None)
            if ref_num and Actor.get_reference(ref_num) is None:
                to_remove.append(trig)
                continue
            recv_room = getattr(owner, 'location_room', None)
            if recv_room is None:
                to_remove.append(trig)
                continue
            if scope == 'room':
                if recv_room != signaler_room:
                    continue
            elif scope == 'subzone':
                recv_zone = getattr(recv_room, 'zone', None)
                recv_sub = getattr(recv_room, 'subzone_id', None)
                if recv_zone != signaler_zone or recv_sub != signaler_subzone_id:
                    continue
            elif scope == 'zone':
                recv_zone = getattr(recv_room, 'zone', None)
                if recv_zone != signaler_zone:
                    continue
            # scope == 'world' or anything else: match all
            valid.append(trig)
        for t in to_remove:
            if t in cls._signal_registry:
                cls._signal_registry.remove(t)
        return valid

    async def run(self, signaler: 'Actor', text: str, vars: dict, game_state: GameStateInterface = None) -> bool:
        """
        signaler = who ran the signal command (subject in script).
        In script: actor (a/A) = trigger owner (receiver), subject (s/S) = signaler, target (t/T) = third arg.
        """
        logger = StructuredLogger(__name__, prefix="TriggerOnSignal.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(signaler, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        signal_name = (vars or {}).get('signal', '')
        target_actor = (vars or {}).get('target_actor')
        vars = {**(vars or {}),
                'signal': signal_name,
                'text': text or '',
                '*': text or '',
                'a': self.actor_.name if self.actor_ else '',
                'A': Constants.REFERENCE_SYMBOL + self.actor_.reference_number if self.actor_ else '',
                's': signaler.name if signaler else '',
                'S': Constants.REFERENCE_SYMBOL + signaler.reference_number if signaler else '',
                'p': signaler.pronoun_subject if signaler else '',
                'P': signaler.pronoun_object if signaler else '',
                't': target_actor.name if target_actor else '',
                'T': Constants.REFERENCE_SYMBOL + target_actor.reference_number if target_actor else '',
                'r': target_actor.pronoun_subject if target_actor else '',
                'R': target_actor.pronoun_object if target_actor else '',
                **(self.actor_.get_vars("a"))}
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerOnLeave(Trigger):
    """
    Fires when a character leaves the room where this trigger is attached.
    The leaving character is available via %S%, %s%, etc. in vars.
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_LEAVE, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnLeave.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number, 
                     's': actor.name, 'S': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("s"))}
        
        logger.debug3(f"evaluating on_leave for {actor.name}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        logger.debug3("executing on_leave script")
        # Execute script as the trigger owner (room/npc/object), not the leaving character
        # The leaving character is still available via %S%, %s%, etc. in vars
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True


class TriggerOnReceive(Trigger):
    """
    Fires when an NPC receives an item via the give command.

    Variable convention: actor = trigger owner, subject = initiator, target = recipient, object = item.
    - a/A = trigger owner (receiver)
    - s/S = subject = giver (initiator of the give)
    - t/T = target = receiver (recipient of the give, same as actor)
    - o/O = object = the item received (o = art_name/id, O = reference)
    - item, item_id, item_name, giver, giver_id
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # Vars from give: a/A=receiver, s/S=giver, t/T=receiver, o/O=item. Add * and trigger-owner prefixed vars.
        vars = {**(vars or {}),
                '*': text or '',
                **(self.actor_.get_vars("a"))}
        
        logger.debug3(f"evaluating on_receive for {self.actor_.name}, item: {vars.get('item_id', 'unknown')}")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        
        logger.debug3("executing on_receive script")
        await self.execute_trigger_script(self.actor_, vars, game_state)
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
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
    Fires when an object is used, drunk, or read (e.g. potions, scrolls).
    Actor = trigger owner (the item). Subject = initiator (character using the object). Target = thing acted upon (item when use/read without "on X", else the specified target).
    Variables: %a%/%A% = actor (item), %s%/%S% = subject (user), %t%/%T% = target (acted upon).
    %use_type% = "use" | "drink" | "read". When "use X on Y", %target% and %target_id% are the target's name and id.
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
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # actor = trigger owner (the item). Keep s/S from incoming vars = character using the object (per docstring).
        vars = {**(vars or {}),
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, '*': text or '' }),
                **(actor.get_vars("a"))}
        
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                return False
        
        await self.execute_trigger_script(actor, vars, game_state)
        return True


class TriggerOnAttacked(Trigger):
    """
    Fires when an attack is attempted against an actor (NPC/character),
    regardless of whether it hits or misses.
    
    Variables available:
    - %S% = the character who was attacked (the trigger owner)
    - %a% / %A% = the attacker's name / reference
    - %attack_noun% = the attack noun (e.g., "sword", "claws")
    - %attack_verb% = the attack verb (e.g., "slashes", "bites")
    """
    def __init__(self, id: str, actor: 'Actor', disabled=True) -> None:
        super().__init__(id, TriggerType.ON_ATTACKED, actor)
        if disabled:
            self.disable()
        else:
            self.enable()

    async def run(self, actor: 'Actor', text: str, vars: dict, game_state: 'ComprehensiveGameState' = None) -> bool:
        """
        Run this trigger when an attack is attempted against the owner.
        
        Args:
            actor: The character who attacked (the attacker)
            text: Unused for this trigger type
            vars: Variables dict containing attack info
            game_state: Current game state
            
        Returns:
            True if the trigger executed, False otherwise
        """
        from ..nondb_models.actors import Actor
        logger = StructuredLogger(__name__, prefix="TriggerOnAttacked.run()> ")
        if self.disabled_:
            return False
        self._trigger_run_debug_log(game_state, "run() entered", trigger_id=self.id, trigger_type=self.trigger_type_.name, run_actor_rid=getattr(actor, 'rid', None), text=(text[:60] + "..." if text and len(text) > 60 else text))
        # Build vars - attacker info goes in 'a'/'A', defender (trigger owner) in 's'/'S'
        vars = {**(vars or {}), 
                **({ 'a': actor.name, 'A': Constants.REFERENCE_SYMBOL + actor.reference_number,
                     's': self.actor_.name, 'S': Constants.REFERENCE_SYMBOL + self.actor_.reference_number,
                     'p': actor.pronoun_subject, 'P': actor.pronoun_object, 
                     'q': actor.pronoun_possessive, '*': text or '' }),
                **(actor.get_vars("a")),
                **(self.actor_.get_vars("s"))}
        
        logger.debug3(f"evaluating on_attacked for {self.actor_.name} (attacked by {actor.name})")
        for crit in self.criteria_:
            if not crit.evaluate(vars, game_state):
                logger.debug3("criteria not met")
                return False
        
        logger.debug3("executing on_attacked script")
        # Execute script as the trigger owner (the one being attacked)
        await self.execute_trigger_script(self.actor_, vars, game_state)
        return True
