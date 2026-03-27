from abc import abstractmethod
import asyncio
from enum import Enum
from typing import Dict, List, Any, TYPE_CHECKING, Optional, Type
from ..command_handler_interface import CommandHandlerInterface
from ..communication import CommTypes
from ..core_actions_interface import CoreActionsInterface
from .actor_interface import ActorType, ActorInterface
from .character_interface import PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags, EquipLocation, CharacterInterface
from .attacks_and_damage import DamageType, DamageMultipliers, DamageReduction
from ..utility import set_vars, ticks_from_seconds
from ..comprehensive_game_state_interface import GameStateInterface, EventType

if TYPE_CHECKING:
    from .actors import Actor
    from .characters import Character
    from .objects import Object
    from .rooms import Room
    from .triggers import Trigger
    from .zones import Zone
    from .world import WorldDefinition


class DurationType(Enum):
    TIMED = "timed"
    WHILE_SOURCE_PRESENT = "while_source_present"
    PERMANENT = "permanent"


def _get_current_tick_value(game_state: GameStateInterface) -> int:
    for attr in ("current_tick", "world_clock_tick"):
        value = getattr(game_state, attr, None)
        if value is not None:
            return int(value)
    getter = getattr(game_state, "get_current_tick", None)
    if callable(getter):
        return int(getter())
    return 0


def _restore_source_from_save(game_state: GameStateInterface, state_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build kwargs for from_saved_state: source_actor, source_refid, duration_type."""
    from .actors import Actor
    source_refid = state_data.get('source_refid') or state_data.get('source_instance_id')
    source_actor = Actor.get_reference(source_refid) if source_refid else None
    duration_type_str = state_data.get('duration_type', DurationType.TIMED.value)
    try:
        duration_type = DurationType(duration_type_str)
    except ValueError:
        duration_type = DurationType.TIMED
    return {
        'source_actor': source_actor,
        'source_refid': source_refid,
        'duration_type': duration_type,
        'tick_created': _get_current_tick_value(game_state),
    }

class Cooldown:
    def __init__(self, actor: ActorInterface, cooldown_name: str, game_state: GameStateInterface,
                 cooldown_source=None, cooldown_vars: dict=None, cooldown_end_fn: callable=None):
        self.cooldown_source = cooldown_source
        self.cooldown_name = cooldown_name
        self.actor: ActorInterface = actor
        self.cooldown_vars: Dict = cooldown_vars
        self.cooldown_start_tick: int = 0
        self.cooldown_end_tick: int = 0
        self.cooldown_duration: int = 0
        self.cooldown_end_fn = cooldown_end_fn
        self.game_state = game_state

    @staticmethod
    def has_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return any([c for c in cooldowns if c.cooldown_source == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name == (cooldown_name or c.cooldown_name)])
    
    @staticmethod
    def current_cooldowns(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return [c for c in cooldowns if c.cooldown_source == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name == (cooldown_name or c.cooldown_name)]
    
    @staticmethod
    def last_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return max([c for c in Cooldown.current_cooldowns(cooldowns, cooldown_source, cooldown_name)],
                   key=lambda c: c.cooldown_end_tick_)
    
    async def start(self, current_tick: int, cooldown_duration_ticks: int = None, cooldown_end_tick: int = None) -> bool:
        self.cooldown_start_tick = current_tick
        if cooldown_duration_ticks:
            self.cooldown_duration_ = cooldown_duration_ticks
            self.cooldown_end_tick = current_tick + cooldown_duration_ticks
        else:
            self.cooldown_end_tick = cooldown_end_tick
            self.cooldown_duration_ = cooldown_end_tick - current_tick
            
        self.actor.cooldowns.append(self)
        self.game_state.add_scheduled_event(EventType.COOLDOWN_OVER, self, self.cooldown_name,
                                            scheduled_tick=self.cooldown_end_tick,
                                            vars=self.cooldown_vars,
                                            func=self.end_cooldown,
                                            attach_to_actor=self.actor)
        return True

    def to_dict(self):
        return {
            'actor': self.actor.rid,
            'cooldown_source': self.cooldown_source,
            'cooldown_name': self.cooldown_name,
            'cooldown_start_tick': self.cooldown_start_tick,
            'cooldown_end_tick': self.cooldown_end_tick,
            'cooldown_duration': self.cooldown_end_tick - self.cooldown_start_tick
        }

    def cooldown_finished(self, current_tick: int) -> bool:
        return current_tick >= self.cooldown_end_tick
    
    def ticks_remaining(self, current_tick: int) -> int:
        return max(self.cooldown_end_tick - current_tick, 0)

    async def end_cooldown(self, actor: ActorInterface, tick: int, game_state: "GameStateInterface", vars: Dict[str, Any]) -> bool:
        if self.cooldown_end_fn:
            result = self.cooldown_end_fn(self)
            if asyncio.iscoroutine(result):
                await result
        self.actor.cooldowns.remove(self)
        return True


def get_actor_state(actor: ActorInterface, state_class: Type['ActorState']) -> Optional['ActorState']:
    """
    Return the first state on the actor that is an instance of state_class, or None.
    Use for single-state checks, e.g.:
      if (state := get_actor_state(a, CharacterStateExperienceModifier)) is not None:
          ...
    """
    states_list = getattr(actor, 'states', None) or getattr(actor, 'current_states', [])
    return next((s for s in states_list if isinstance(s, state_class)), None)


def get_actor_states(actor: ActorInterface, state_class: Type['ActorState']) -> List['ActorState']:
    """Return all states on the actor that are instances of state_class."""
    states_list = getattr(actor, 'states', None) or getattr(actor, 'current_states', [])
    return [s for s in states_list if isinstance(s, state_class)]


class ActorState:
    """source_refid is the stable actor registry id (UUID) for whoever applied this state; it is persisted.
    Pass source_actor when available (skills/spells) for messages and immediate logic; source_refid is
    derived from source_actor.reference_number if omitted. After load, source_actor is re-resolved from
    source_refid when possible; use resolve_source_actor() for a fresh registry lookup."""
    persist_on_save: bool = False

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, vars=None, tick_created=None,
                 duration_type: DurationType = DurationType.TIMED,
                 source_refid: str = None):
        self.actor: ActorInterface = actor
        ref = source_refid if source_refid is not None else (
            getattr(source_actor, 'reference_number', None) if source_actor else None
        )
        self.source_refid: Optional[str] = ref
        from .actors import Actor
        if source_actor is not None and ref and getattr(source_actor, 'reference_number', None) == ref:
            self.source_actor: ActorInterface = source_actor
        else:
            self.source_actor = Actor.get_reference(ref) if ref else source_actor
        self.duration_type: DurationType = duration_type
        self.state_type_name: str = state_type_name
        self.tick_created: int = tick_created
        self.tick_started: int = None
        self.tick_ending: int = None
        self.last_tick_acted: int = None
        self.next_tick: int = None
        self.tick_period: int = 0
        self.character_flags_added: TemporaryCharacterFlags = TemporaryCharacterFlags(0)
        self.character_flags_removed: TemporaryCharacterFlags = TemporaryCharacterFlags(0)
        self.affect_amount: int = 0
        self.duration_remaining: int = 0
        self.vars = vars
        self.game_state: GameStateInterface = game_state
        self._restoring_state: bool = False

    def to_dict(self):
        return {
            'class': self.__class__.__name__,
            'actor': self.actor.rid,
            'tick_created': self.tick_created,
            'tick_started': self.tick_started,
            'tick_ending': self.tick_ending,
            'last_tick_acted': self.last_tick_acted,
            'next_tick': self.next_tick,
            'tick_period': self.tick_period
        }

    def is_restoring(self) -> bool:
        return self._restoring_state

    def should_emit_messages(self) -> bool:
        return not self.is_restoring()

    def get_remaining_duration_ticks(self, current_tick: int = None) -> int:
        if self.tick_ending is None:
            return 0
        if current_tick is None:
            current_tick = _get_current_tick_value(self.game_state)
        return max(int(self.tick_ending - current_tick), 0)

    def get_persist_data(self) -> Dict[str, Any]:
        return {}

    def resolve_source_actor(self) -> Optional[ActorInterface]:
        """Return the current source actor from the registry, or None."""
        from .actors import Actor
        if not self.source_refid:
            return self.source_actor
        resolved = Actor.get_reference(self.source_refid)
        return resolved if resolved is not None else self.source_actor

    def save_state(self, current_tick: int = None) -> Optional[Dict[str, Any]]:
        if not self.persist_on_save:
            return None
        data = {
            'class': self.__class__.__name__,
            'state_type_name': self.state_type_name,
            'duration_type': self.duration_type.value,
            'source_refid': self.source_refid,
        }
        if self.duration_type == DurationType.TIMED:
            remaining_duration_ticks = self.get_remaining_duration_ticks(current_tick)
            if remaining_duration_ticks <= 0:
                return None
            data['remaining_duration_ticks'] = remaining_duration_ticks
        if self.tick_period:
            data['tick_period'] = self.tick_period
        data.update(self.get_persist_data())
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'ActorState':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            **sk,
        )

    def get_restore_apply_kwargs(self) -> Dict[str, Any]:
        return {}

    async def restore_state(self, start_tick: int, duration_ticks: int) -> int:
        self._restoring_state = True
        try:
            return await self.apply_state(
                start_tick=start_tick,
                duration_ticks=duration_ticks,
                **self.get_restore_apply_kwargs(),
            )
        finally:
            self._restoring_state = False

    async def _send_status_update_if_needed(self) -> None:
        if not hasattr(self.actor, 'has_perm_flags') or not hasattr(self.actor, 'send_status_update'):
            return
        if not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            return
        result = self.actor.send_status_update()
        if asyncio.iscoroutine(result):
            await result

    async def _echo_to_room(self, msg: str, vars: dict, exceptions: List = None) -> None:
        """Echo to the actor's current room. No-op if actor has no location_room (e.g. dead, removed)."""
        if self.actor.location_room is not None:
            await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars,
                exceptions=exceptions, game_state=self.game_state)
        
    def does_add_flag(self, flag: TemporaryCharacterFlags) -> bool:
        return self.character_flags_added.are_flags_set(flag)
    
    def does_remove_flag(self, flag: TemporaryCharacterFlags) -> bool:
        return self.character_flags_removed.are_flags_set(flag)
    
    @abstractmethod
    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        """
        Returns the next tick that the state should be applied.
        duration_ticks and end_tick both None means it's indefinite (WHILE_SOURCE_PRESENT or PERMANENT).
        """
        if pulse_period_ticks:
            self.tick_period = pulse_period_ticks
        if duration_ticks and not end_tick:
            self.tick_ending = start_tick + duration_ticks
        elif duration_ticks and end_tick:
            raise Exception("duration_ticks and end_tick both set")
        else:
            self.tick_ending = end_tick  # None for indefinite states
        self.tick_started = start_tick
        self.next_tick = start_tick + self.tick_period
        self.last_tick_acted = start_tick
        self.duration_remaining = (self.tick_ending - self.tick_started) if self.tick_ending is not None else 0
        self.actor.apply_state(self)
        if self.tick_ending is not None:
            self.game_state.add_scheduled_event(EventType.STATE_END, self, "state_end", scheduled_tick=self.tick_ending,
                                                vars=None, func=lambda a, t, s, v: self.remove_state(),
                                                attach_to_actor=self.actor)
        if pulse_period_ticks:
            self.game_state.add_scheduled_event(EventType.STATE_PULSE, self, f"state_pulse:{self.state_type_name}",
                                                scheduled_tick=self.next_tick, in_ticks=self.tick_period,
                                                vars=None, func=lambda a, t, s, v: self.perform_pulse(t, s, v),
                                                attach_to_actor=self.actor)
        return self.next_tick

    @abstractmethod
    def remove_state(self, force=False) -> bool:
        """
        Returns True if the state was removed, False if it was not removed.
        """
        return self.actor.remove_state(self)

    def does_affect_flag(self, flag: TemporaryCharacterFlags) -> bool:
        """
        Returns True if the state affects the given flag, False if it does not.
        """
        return self.character_flags_added.are_flags_set(flag)
    
    def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if self.tick_ending is None:
            self.duration_remaining = 0
        else:
            self.duration_remaining = max(self.tick_ending - tick_num, 0)
        self.last_tick_acted = tick_num
        if self.duration_remaining > 0:
            self.next_tick = tick_num + self.tick_period
            self.game_state.add_scheduled_event(EventType.STATE_PULSE, self, f"state_pulse:{self.state_type_name}",
                                                scheduled_tick=self.next_tick, in_ticks=self.tick_period,
                                                vars=None, func=lambda a, t, s, v: self.perform_pulse(t, s, v),
                                                attach_to_actor=self.actor)
        return True
    
    @abstractmethod
    def get_affect_amount(self):
        return self.affect_amount

    def get_my_status_message(self) -> Optional[str]:
        """Message shown to the character about this state (e.g. 'You are burning.'). Default: None."""
        return None

    def get_room_status_message(self) -> Optional[str]:
        """Template for room: use %s% for the character's article+name (e.g. '%s% is burning.'). Default: None."""
        return None


class CharacterStateForcedSitting(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You knock {self.actor.art_name} onto the ground."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, self.game_state)
            msg = f"{self.source_actor.art_name_cap} knocks you onto the ground."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, self.game_state)
            msg = f"{self.source_actor.art_name_cap} knocks {self.actor.art_name} onto the ground."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval


    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        if any([s for s in self.actor.current_states if s is not self \
                              and s.does_add_flag(TemporaryCharacterFlags.IS_SITTING)]):
            return True
        self.actor.remove_temp_flags(self.character_flags_added)
        msg = "The dizziness wears off, you feel steady enough to stand again."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} looks steady enough to stand again."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.source_actor])
        # NPCs automatically stand up when the forced sitting wears off
        if self.actor.actor_type == ActorType.CHARACTER and self.actor.location_room \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            # Queue the stand command so it goes through normal command handling
            self.actor.command_queue.append("stand")
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)

        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are sitting on the ground."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is sitting on the ground."


class CharacterStateForcedSleeping(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SLEEPING)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You put {self.actor} to sleep."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} puts you to sleep."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} puts {self.actor.art_name} to sleep."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval


    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        if any([s for s in self.actor.current_states if s is not self \
                              and s.does_add_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return True
        self.actor.remove_temp_flags(self.character_flags_added)
        msg = "You wake up, no longer feeling sleepy."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} wakes up."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.actor])
        # NPCs automatically stand up when the sleep wears off
        if self.actor.actor_type == ActorType.CHARACTER and self.actor.location_room \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            # Queue the stand command so it goes through normal command handling
            self.actor.command_queue.append("stand")
        # Re-aggro if appropriate (only if not still sitting from another effect)
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are asleep."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is asleep."


class CharacterStateStunned(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_STUNNED)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_flag(TemporaryCharacterFlags.IS_STUNNED)
            if self.source_actor:
                msg = f"You stun {self.actor.art_name}."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} stuns you."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg, game_state=self.game_state)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} stuns {self.actor.art_name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval

    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        if any([s for s in self.actor.current_states if s is not self \
                and s.does_affect_flag(TemporaryCharacterFlags.IS_STUNNED)]):
            return True
        
        self.actor.remove_temp_flags(TemporaryCharacterFlags.IS_STUNNED)
        msg = "You shake off the stun."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} shakes off the stun."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.actor])
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are stunned."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is stunned."


class CharacterStateHitPenalty(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateHitPenalty':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            # not gonna say anything for a hit penalty
            # if self.source_actor:
            #     msg = f"You stun %t%."
            #     vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
            #     self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            # msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_, cap=True)} stuns you."
            # vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            # self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            # msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_)} stuns %t%."
            # vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            # self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
            self.actor.hit_modifier -= self.affect_amount
        return retval

    def remove_state(self) -> bool:
        if super().remove_state():
            self.actor.hit_modifier += self.affect_amount
            return True
        else:
            return False

    def get_my_status_message(self) -> Optional[str]:
        return f"You are {self.state_type_name}."
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% looks {self.state_type_name}."


class CharacterStateHitBonus(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateHitBonus':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"{self.actor.art_name_cap} feels {self.state_type_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"You feel {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            self.actor.hit_modifier += self.affect_amount
        return retval

    async def remove_state(self) -> bool:
        if super().remove_state():
            msg = f"You no longer feel {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            self.actor.hit_modifier -= self.affect_amount
            return True
        else:
            return False

    def get_my_status_message(self) -> Optional[str]:
        return f"You feel {self.state_type_name}!"
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% looks {self.state_type_name}."


class CharacterStateExperienceModifier(ActorState):
    """
    Multiplicative modifier to experience gained, stored on the state as modifier (float).
    Examples: modifier=0.75 for a death penalty, modifier=1.25 for a scroll of learning.
    Messages use state_type_name: "You feel {state_type_name}." / "You no longer feel {state_type_name}."
    """
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, modifier: float = 1.0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name or "perspicacious", tick_created=tick_created, **kwargs)
        self.modifier = float(modifier)

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'modifier': self.modifier,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateExperienceModifier':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            modifier=float(state_data.get('modifier', 1.0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None and self.should_emit_messages():
            name = self.state_type_name or "perspicacious"
            if self.source_actor and self.source_actor is not self.actor:
                msg = f"{self.actor.art_name_cap} feels {name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"You feel {name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        return retval

    def get_my_status_message(self) -> Optional[str]:
        name = self.state_type_name or "perspicacious"
        return f"You feel {name}."
    def get_room_status_message(self) -> Optional[str]:
        name = self.state_type_name or "perspicacious"
        return f"%s% looks {name}."

    async def remove_state(self, force=False) -> bool:
        if super().remove_state(force):
            name = self.state_type_name or "perspicacious"
            msg = f"You no longer feel {name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        return False


# =============================================================================
# FOR DEBUGGING REMOVE BEFORE PRODUCTION
# CharacterStateAdmin: temporary admin privileges (is_admin true) for duration.
# Used by God Potion. Remove this state and the God Potion before production.
# =============================================================================
class CharacterStateAdmin(ActorState):
    """
    Temporarily grants GamePermissionFlags.IS_ADMIN to the character for the state duration.
    On apply: add IS_ADMIN. On remove: remove IS_ADMIN.
    FOR DEBUGGING REMOVE BEFORE PRODUCTION.
    """
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface = None,
                 state_type_name: str = None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name or "godlike", tick_created=tick_created, **kwargs)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None and hasattr(self.actor, 'add_game_flags'):
            self.actor.add_game_flags(GamePermissionFlags.IS_ADMIN)
            name = self.state_type_name or "godlike"
            if self.source_actor and self.source_actor is not self.actor:
                msg = f"{self.actor.art_name_cap} radiates divine authority!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"You feel {name} — admin privileges granted."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        return retval

    async def remove_state(self, force=False) -> bool:
        if super().remove_state(force):
            if hasattr(self.actor, 'remove_game_flags'):
                self.actor.remove_game_flags(GamePermissionFlags.IS_ADMIN)
            name = self.state_type_name or "godlike"
            msg = f"You no longer feel {name} — admin privileges have ended."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        return False

    def get_my_status_message(self) -> Optional[str]:
        name = self.state_type_name or "godlike"
        return f"You have temporary admin privileges ({name})."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% radiates divine authority."


class CharacterStateDisarmed(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_DISARMED)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.vars = {}
            mhw = self.actor.equipped.get(EquipLocation.MAIN_HAND)
            ohw = self.actor.equipped.get(EquipLocation.OFF_HAND)
            bhw = self.actor.equipped.get(EquipLocation.BOTH_HANDS)
            self.vars["main hand weapon"] = mhw
            self.vars["off hand weapon"] = ohw
            self.vars["both hands weapon"] = bhw
            if mhw is None and ohw is None and bhw is None:
                msg = "They aren't using any weapons."
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                return retval
            if mhw:
                self.actor.unequip_location(EquipLocation.MAIN_HAND)
                self.actor.add_object(mhw)
            if ohw:
                self.actor.unequip_location(EquipLocation.OFF_HAND)
                self.actor.add_object(ohw)
            if bhw:
                self.actor.unequip_location(EquipLocation.BOTH_HANDS)
                self.actor.add_object(bhw)
            self.actor.add_temp_flags(self.character_flags_added)
            msg = f"You disarm {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg, game_state=self.game_state)
            await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} disarms you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} disarms {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval
    

    async def remove_state(self, force=True) -> bool:
        if not force and any([s for s in self.actor.current_states if s is not self \
                              and s.does_affect_flag(TemporaryCharacterFlags.IS_DISARMED)]):
            return True
        mhw = self.vars.get("main hand weapon")
        ohw = self.vars.get("off hand weapon")
        bhw = self.vars.get("both hands weapon")
        if mhw and self.actor.equipped.get(EquipLocation.MAIN_HAND) is None:
            self.actor.remove_object(mhw)
            self.actor.equip_object(mhw)
        if ohw and self.actor.equipped.get(EquipLocation.OFF_HAND) is None:
            self.actor.remove_object(ohw)
            self.actor.equip_object(ohw)
        if bhw and self.actor.equipped.get(EquipLocation.BOTH_HANDS) is None:
            self.actor.remove_object(bhw)
            self.actor.equip_object(bhw)
        if not super().remove_state(force):
            return False
        self.actor.remove_temp_flags(TemporaryCharacterFlags.IS_DISARMED)
        msg = "You ready your weapons again."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} readies {self.actor.pronoun_possessive} weapons again."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.actor])
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are disarmed."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is disarmed."


class CharacterStateDodgePenalty(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateDodgePenalty':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if not retval:
            return False
            # not gonna say anything for a dodge penalty
            # if retval is not None:
            #     if self.source_actor:
            #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
        #         self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_)} stuns %t%."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        self.actor.dodge_modifier -= self.affect_amount
        return True
    
    def remove_state(self) -> bool:
        self.actor.dodge_modifier += self.affect_amount
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return f"You are {self.state_type_name}."
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% is {self.state_type_name}."


class CharacterStateDodgeBonus(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateDodgeBonus':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        # not gonna say anything for a dodge penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
        #         self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_)} stuns %t%."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        self.actor.dodge_modifier += self.affect_amount
        return True
    
    def remove_state(self) -> bool:
        self.actor.dodge_modifier -= self.affect_amount
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return f"You are {self.state_type_name}."
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% is {self.state_type_name}."


class CharacterStateDamageBonus(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateDamageBonus':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        
        self.actor.damage_modifier += self.affect_amount
        
        if self.should_emit_messages() and self.source_actor:
            msg = f"{self.actor.art_name_cap} becomes {self.state_type_name}!"
            vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
            await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)

        if self.should_emit_messages():
            msg = f"You become {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            
            msg = f"{self.actor.art_name_cap} becomes {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor])
        return True
    
    async def remove_state(self) -> bool:
        self.actor.damage_modifier -= self.affect_amount
        msg = f"You are no longer {self.state_type_name}."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        
        msg = f"{self.actor.art_name_cap} is no longer {self.state_type_name}."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.actor])
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return f"You are {self.state_type_name}."
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% is {self.state_type_name}."


class CharacterStateBerserkerStance(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, dodge_penalty:int = 0, hit_bonus:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.dodge_penalty = dodge_penalty
        self.hit_bonus = hit_bonus

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'dodge_penalty': self.dodge_penalty,
            'hit_bonus': self.hit_bonus,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateBerserkerStance':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            dodge_penalty=int(state_data.get('dodge_penalty', 0)),
            hit_bonus=int(state_data.get('hit_bonus', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        # not gonna say anything for a dodge penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
        #         self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor.name_)} stuns %t%."
        #     vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        self.actor.dodge_modifier -= self.dodge_penalty
        self.actor.hit_modifier += self.hit_bonus
        return True
    
    def remove_state(self) -> bool:
        self.actor.dodge_modifier += self.dodge_penalty
        self.actor.hit_modifier -= self.hit_bonus   
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return "You are in a berserker stance."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is in a berserker stance."


class CharacterStateDefensiveStance(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, dodge_bonus:int = 0, hit_penalty:int = 0, damage_multipliers=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.dodge_bonus = dodge_bonus
        self.hit_penalty = hit_penalty
        self.damage_multipliers = damage_multipliers

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'dodge_bonus': self.dodge_bonus,
            'hit_penalty': self.hit_penalty,
        }
        if self.damage_multipliers:
            data['damage_multipliers'] = {dt.name: value for dt, value in self.damage_multipliers.profile.items()}
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateDefensiveStance':
        damage_multipliers = None
        if state_data.get('damage_multipliers'):
            damage_multipliers = DamageMultipliers()
            for damage_type_name, value in state_data['damage_multipliers'].items():
                try:
                    damage_multipliers.set(DamageType[damage_type_name], value)
                except KeyError:
                    continue
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            dodge_bonus=int(state_data.get('dodge_bonus', 0)),
            hit_penalty=int(state_data.get('hit_penalty', 0)),
            damage_multipliers=damage_multipliers,
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        self.actor.dodge_modifier += self.dodge_bonus
        self.actor.hit_modifier -= self.hit_penalty
        if self.damage_multipliers:
            self.actor.damage_multipliers.add_multipliers(self.damage_multipliers)
        return True
    
    def remove_state(self) -> bool:
        self.actor.dodge_modifier -= self.dodge_bonus
        self.actor.hit_modifier += self.hit_penalty
        if self.damage_multipliers:
            self.actor.damage_multipliers.minus_multipliers(self.damage_multipliers)
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return "You are in a defensive stance."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is in a defensive stance."


class CharacterStateBleeding(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'affect_amount': self.affect_amount,
        }
        if self.tick_period:
            data['tick_period'] = self.tick_period
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateBleeding':
        sk = _restore_source_from_save(game_state, state_data)
        state = cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )
        state.tick_period = int(state_data.get('tick_period', 0))
        return state

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"You tear open bloody wounds on {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} tears open bloody wounds on you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} tears open bloody wounds on {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval

    async def remove_state(self) -> bool:
        if retval := super().remove_state():
            msg = "Your wounds stop bleeding."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.actor.art_name_cap} stops bleeding."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.source_actor])
        return retval
    
    async def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            msg = f"Your wounds bleed for {self.affect_amount} damage."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"%t%'s wounds bleed for {self.affect_amount} damage."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.source_actor])
            CoreActionsInterface.get_instance().do_damage(self.source_actor, self.actor, self.affect_amount,
                                                          DamageType.RAW, False)
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are bleeding."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is bleeding."


class CharacterStateStealthed(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount
        self.character_flags_added = TemporaryCharacterFlags.IS_STEALTHED

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateStealthed':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        self.actor.add_temp_flags(self.character_flags_added)
        self.vars = { "seen_by": [] }
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        return retval
    
    def remove_state(self) -> bool:
        self.actor.remove_temp_flags(self.character_flags_added)
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return "You are stealthed."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is hidden in the shadows."


class CharacterStateShielded(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface = None, 
                 state_type_name=None, multipliers: DamageMultipliers = None, reductions: DamageReduction = None,
                 vars=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, vars, tick_created, **kwargs)
        self.extra_multipliers: DamageMultipliers = multipliers
        self.extra_reductions: DamageReduction = reductions

    def get_persist_data(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if self.extra_multipliers:
            data['multipliers'] = {dt.name: value for dt, value in self.extra_multipliers.profile.items()}
        if self.extra_reductions:
            data['reductions'] = {dt.name: value for dt, value in self.extra_reductions.profile.items()}
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateShielded':
        multipliers = None
        if state_data.get('multipliers'):
            multipliers = DamageMultipliers()
            for damage_type_name, value in state_data['multipliers'].items():
                try:
                    multipliers.set(DamageType[damage_type_name], value)
                except KeyError:
                    continue
        reductions = None
        if state_data.get('reductions'):
            reductions = DamageReduction()
            for damage_type_name, value in state_data['reductions'].items():
                try:
                    reductions.set(DamageType[damage_type_name], value)
                except KeyError:
                    continue
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            multipliers=multipliers,
            reductions=reductions,
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if not retval:
            return False
        if self.extra_multipliers:
            self.actor.damage_multipliers.add_multipliers(self.extra_multipliers)
        if self.extra_reductions:
            self.actor.damage_reductions_.add_reductions(self.extra_reductions)
        return retval
    
    def remove_state(self) -> bool:
        if retval := super().remove_state():
            if self.extra_multipliers:
                self.actor.damage_multipliers.minus_multipliers(self.extra_multipliers)
            if self.extra_reductions:
                self.actor.damage_reductions_.remove_reductions(self.extra_reductions)
        return retval

    def get_my_status_message(self) -> Optional[str]:
        name = self.state_type_name or "shielded"
        return f"You are protected by {name}."
    def get_room_status_message(self) -> Optional[str]:
        name = self.state_type_name or "a shield"
        return f"%s% is protected by {name}."


class CharacterStateCasting(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, casting_finish_func: callable=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.casting_finish_func = casting_finish_func
    
    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        return await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        
    async def remove_state(self, force=False) -> bool:
        if self.casting_finish_func:
            result = self.casting_finish_func()
            if asyncio.iscoroutine(result):
                await result
        return super().remove_state(force)

    def get_my_status_message(self) -> Optional[str]:
        return "You are casting."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is casting."


class CharacterStateRecoveryModifier(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, recovery_modifier: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.recovery_modifier = recovery_modifier
        actor.recovery_ticks += recovery_modifier
        
    def remove_state(self) -> bool:
        self.actor.recovery_ticks -= self.recovery_modifier
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return None
    def get_room_status_message(self) -> Optional[str]:
        return None


# NOT USED AND NOT FULLY IMPLEMENTED:
# `CharacterStateDamageMultipliers` is an older plural/profile-based concept that
# is not referenced by live command, scripting, or combat code. The active path is
# `CharacterStateDamageMultiplier` below, which handles a single damage type plus
# multiplier and is what `applystate damagemultiplier` uses.
#
# class CharacterStateDamageMultipliers(ActorState):
#     def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
#                  state_type_name=None, damage_multipliers: DamageMultipliers = None, tick_created=None):
#         super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
#         self.damage_multipliers = damage_multipliers
#
#     async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
#         if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
#             return False
#         self.actor.damage_multipliers.add_multipliers(self.damage_multipliers)
#         return True
#
#     def remove_state(self) -> bool:
#         self.actor.damage_multipliers.minus_multipliers(self.damage_multipliers)
#         return super().remove_state()
#
#     def get_my_status_message(self) -> Optional[str]:
#         return None
#     def get_room_status_message(self) -> Optional[str]:
#         return None


class CharacterStateBurning(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, damage_amount: int = 0, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.damage_amount = damage_amount

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'damage_amount': self.damage_amount,
        }
        if self.tick_period:
            data['tick_period'] = self.tick_period
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateBurning':
        sk = _restore_source_from_save(game_state, state_data)
        state = cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            damage_amount=int(state_data.get('damage_amount', 0)),
            **sk,
        )
        state.tick_period = int(state_data.get('tick_period', 0))
        return state

    def get_restore_apply_kwargs(self) -> Dict[str, Any]:
        if self.tick_period > 0:
            return {'pulse_period_ticks': self.tick_period}
        return {}

    async def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            damage, target_hp = CoreActionsInterface.get_instance().do_calculated_damage(self.source_actor, self.actor, self.damage_amount,
                                                          DamageType.FIRE, False, False)
            if damage > 0:
                msg = f"You burn for {damage} damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"%t% burns for {damage} damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self._echo_to_room(msg, vars, exceptions=[self.source_actor])
            if target_hp <= 0:
                CoreActionsInterface.get_instance().do_die(self.actor, self.actor)
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are burning."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is burning."


class CharacterStateArmorBonus(ActorState):
    """Adds flat damage reduction to physical damage types (slashing, piercing, bludgeoning)."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateArmorBonus':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        # Add armor bonus to physical damage types
        self.actor.current_damage_reduction[DamageType.SLASHING] += self.affect_amount
        self.actor.current_damage_reduction[DamageType.PIERCING] += self.affect_amount
        self.actor.current_damage_reduction[DamageType.BLUDGEONING] += self.affect_amount
        return True
    
    def remove_state(self) -> bool:
        # Remove armor bonus from physical damage types
        self.actor.current_damage_reduction[DamageType.SLASHING] -= self.affect_amount
        self.actor.current_damage_reduction[DamageType.PIERCING] -= self.affect_amount
        self.actor.current_damage_reduction[DamageType.BLUDGEONING] -= self.affect_amount
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        name = self.state_type_name or "armored"
        return f"You are protected ({name})."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is protected."


class CharacterStateMaxHpBonus(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name or "fortified", tick_created=tick_created, **kwargs)
        self.affect_amount = affect_amount

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'affect_amount': self.affect_amount,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateMaxHpBonus':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            affect_amount=int(state_data.get('affect_amount', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is None:
            return retval
        self.actor.max_hit_points = max(1, self.actor.max_hit_points + self.affect_amount)
        if self.should_emit_messages():
            msg = f"You feel {self.state_type_name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        await self._send_status_update_if_needed()
        return retval

    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        self.actor.max_hit_points = max(1, self.actor.max_hit_points - self.affect_amount)
        self.actor.current_hit_points = min(self.actor.current_hit_points, self.actor.max_hit_points)
        if self.should_emit_messages():
            msg = f"You no longer feel {self.state_type_name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        await self._send_status_update_if_needed()
        return True

    def get_my_status_message(self) -> Optional[str]:
        return f"You feel {self.state_type_name}."

    def get_room_status_message(self) -> Optional[str]:
        return f"%s% looks {self.state_type_name}."


class CharacterStateConfused(ActorState):
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name or "confused", tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_CONFUSED)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.should_emit_messages():
                msg = "Your thoughts twist into disorienting confusion."
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval

    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        states_list = getattr(self.actor, 'current_states', getattr(self.actor, 'states', []))
        if any([s for s in states_list if s is not self
                and s.does_add_flag(TemporaryCharacterFlags.IS_CONFUSED)]):
            return True
        self.actor.remove_temp_flags(self.character_flags_added)
        if self.should_emit_messages():
            msg = "Your thoughts finally settle and clear."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are confused."

    def get_room_status_message(self) -> Optional[str]:
        return "%s% looks confused."


class CharacterStateRegenerating(ActorState):
    """Heals the target periodically over time."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, heal_amount: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.heal_amount = heal_amount
        self.total_healed = 0

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'heal_amount': self.heal_amount,
        }
        if self.tick_period:
            data['tick_period'] = self.tick_period
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateRegenerating':
        sk = _restore_source_from_save(game_state, state_data)
        state = cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            heal_amount=int(state_data.get('heal_amount', 0)),
            **sk,
        )
        state.tick_period = int(state_data.get('tick_period', 0))
        return state

    def get_restore_apply_kwargs(self) -> Dict[str, Any]:
        if self.tick_period > 0:
            return {'pulse_period_ticks': self.tick_period}
        return {}

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        if pulse_period_ticks:
            self.tick_period = pulse_period_ticks
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick, 
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None and self.should_emit_messages():
            if self.source_actor and self.source_actor != self.actor:
                msg = f"You invoke regenerative magic upon {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.source_actor.art_name_cap} invokes regenerative magic upon you!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            else:
                msg = "Regenerative magic flows through you!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Regenerative magic surrounds {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars,
                exceptions=[self.actor, self.source_actor] if self.source_actor else [self.actor])
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            msg = f"The regenerative magic fades. (Total healed: {self.total_healed})"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval
    
    async def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            actual_heal = self.actor.increase_hp(self.heal_amount)
            self.total_healed += actual_heal
            
            if actual_heal > 0:
                msg = f"Regenerative magic heals you for {actual_heal} hit points!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are regenerating."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is surrounded by regenerative magic."


class CharacterStateZealotry(ActorState):
    """Increases damage dealt but reduces healing received."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_bonus: int = 0, healing_penalty: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.damage_bonus = damage_bonus
        self.healing_penalty = healing_penalty  # Percentage reduction in healing received (e.g., 50 = 50% less healing)

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'damage_bonus': self.damage_bonus,
            'healing_penalty': self.healing_penalty,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateZealotry':
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            damage_bonus=int(state_data.get('damage_bonus', 0)),
            healing_penalty=int(state_data.get('healing_penalty', 0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        self.actor.damage_modifier += self.damage_bonus
        # Store healing penalty on actor for healing spells to check
        if not hasattr(self.actor, 'healing_received_modifier'):
            self.actor.healing_received_modifier = 0
        self.actor.healing_received_modifier -= self.healing_penalty
        return True
    
    def remove_state(self) -> bool:
        self.actor.damage_modifier -= self.damage_bonus
        self.actor.healing_received_modifier += self.healing_penalty
        return super().remove_state()

    def get_my_status_message(self) -> Optional[str]:
        return f"You are {self.state_type_name}."
    def get_room_status_message(self) -> Optional[str]:
        return f"%s% looks {self.state_type_name}."


class CharacterStateCharmed(ActorState):
    """Marks a character as charmed/controlled by another character."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.charmed_by = self.source_actor
        self.character_flags_added = TemporaryCharacterFlags(0)

    @classmethod
    def resolve_saved_charmer(cls, state_data: Dict[str, Any]):
        """Resolve the charmer from saved data (source_refid / legacy keys)."""
        from .actors import Actor
        source_id = state_data.get('source_refid') or state_data.get('source_instance_id') or state_data.get('charmed_by_reference')
        if not source_id:
            return None
        return Actor.get_reference_if_alive(source_id)

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateCharmed':
        sk = _restore_source_from_save(game_state, state_data)
        charmer = cls.resolve_saved_charmer(state_data)
        sk['source_actor'] = charmer
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            # Store reference to who charmed this character
            self.actor.charmed_by = self.charmed_by
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            # Check if still charmed by another effect
            states_list = getattr(self.actor, 'current_states', getattr(self.actor, 'states', []))
            still_charmed = any(s for s in states_list
                               if s is not self and isinstance(s, CharacterStateCharmed))
            if not still_charmed:
                self.actor.charmed_by = None
                msg = f"{self.actor.art_name_cap} is no longer under your control!"
                vars = set_vars(self.charmed_by, self.charmed_by, self.actor, msg)
                await self.charmed_by.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.actor.art_name_cap} breaks free from {self.charmed_by.art_name}'s control!"
                vars = set_vars(self.actor, self.charmed_by, self.actor, msg)
                await self._echo_to_room(msg, vars, exceptions=[self.charmed_by])
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are charmed."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is charmed."


class CharacterStateConsecrated(ActorState):
    """Burns the target with holy fire periodically over time, dealing holy damage."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_amount: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.damage_amount = damage_amount
        self.total_damage = 0

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'damage_amount': self.damage_amount,
        }
        if self.tick_period:
            data['tick_period'] = self.tick_period
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateConsecrated':
        sk = _restore_source_from_save(game_state, state_data)
        state = cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            damage_amount=int(state_data.get('damage_amount', 0)),
            **sk,
        )
        state.tick_period = int(state_data.get('tick_period', 0))
        return state

    def get_restore_apply_kwargs(self) -> Dict[str, Any]:
        if self.tick_period > 0:
            return {'pulse_period_ticks': self.tick_period}
        return {}

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick,
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None:
            if self.source_actor:
                msg = f"Holy fire engulfs {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Holy fire engulfs you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Holy fire engulfs {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            msg = "The holy fire fades."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval
    
    async def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            damage, target_hp = await CoreActionsInterface.get_instance().do_calculated_damage(
                self.source_actor, self.actor, self.damage_amount, DamageType.HOLY, do_msg=False, do_die=True)
            self.total_damage += damage
            
            if damage > 0:
                msg = f"Holy fire burns you for {damage} damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.actor.art_name_cap} burns with holy fire for {damage} damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self._echo_to_room(msg, vars, exceptions=[self.actor])
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are burning with holy fire."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is burning with holy fire."


class CharacterStateIgnited(ActorState):
    """Burns the target periodically over time, dealing fire damage."""
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_amount: int = 0, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.damage_amount = damage_amount
        self.total_damage = 0

    def get_persist_data(self) -> Dict[str, Any]:
        data = {
            'damage_amount': self.damage_amount,
        }
        if self.tick_period:
            data['tick_period'] = self.tick_period
        return data

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateIgnited':
        sk = _restore_source_from_save(game_state, state_data)
        state = cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            damage_amount=int(state_data.get('damage_amount', 0)),
            **sk,
        )
        state.tick_period = int(state_data.get('tick_period', 0))
        return state

    def get_restore_apply_kwargs(self) -> Dict[str, Any]:
        if self.tick_period > 0:
            return {'pulse_period_ticks': self.tick_period}
        return {}

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick,
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None:
            if self.source_actor:
                msg = f"You set {self.actor.art_name} ablaze!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} sets you ablaze!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} sets {self.actor.art_name} ablaze!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            msg = "The flames on you die out."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"The flames on {self.actor.art_name} die out."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor])
        return retval
    
    async def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            damage, target_hp = await CoreActionsInterface.get_instance().do_calculated_damage(
                self.source_actor, self.actor, self.damage_amount, DamageType.FIRE, do_msg=False, do_die=True)
            self.total_damage += damage
            
            if damage > 0:
                msg = f"You burn for {damage} fire damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.actor.art_name_cap} burns for {damage} fire damage!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self._echo_to_room(msg, vars, exceptions=[self.actor])
        return retval

    def get_my_status_message(self) -> Optional[str]:
        return "You are on fire."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is on fire."


class CharacterStateDamageMultiplier(ActorState):
    """
    Per-damage-type multiplicative modifier to incoming damage.
    multiplier < 1 = resistance (e.g. 0.5 halves fire damage),
    multiplier > 1 = vulnerability (e.g. 1.5 increases fire damage by 50%).
    Multiple instances stack multiplicatively.
    """
    persist_on_save = True

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface = None,
                 state_type_name: str = None, damage_type: 'DamageType' = None, multiplier: float = 1.0,
                 tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.damage_type: 'DamageType' = damage_type
        self.multiplier: float = float(multiplier)

    def get_persist_data(self) -> Dict[str, Any]:
        return {
            'damage_type': self.damage_type.name if self.damage_type else None,
            'multiplier': self.multiplier,
        }

    @classmethod
    def from_saved_state(cls, actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> 'CharacterStateDamageMultiplier':
        damage_type = None
        damage_type_name = state_data.get('damage_type')
        if damage_type_name:
            try:
                damage_type = DamageType[damage_type_name]
            except KeyError:
                damage_type = None
        sk = _restore_source_from_save(game_state, state_data)
        return cls(
            actor=actor,
            game_state=game_state,
            state_type_name=state_data.get('state_type_name'),
            damage_type=damage_type,
            multiplier=float(state_data.get('multiplier', 1.0)),
            **sk,
        )

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None and self.should_emit_messages():
            dt_word = self.damage_type.word() if self.damage_type else "all"
            if self.multiplier < 1:
                desc = f"resistant to {dt_word} damage"
            elif self.multiplier > 1:
                desc = f"vulnerable to {dt_word} damage"
            else:
                desc = f"unaffected by {dt_word} modifiers"
            if self.source_actor and self.source_actor is not self.actor:
                msg = f"{self.actor.art_name_cap} becomes {desc}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"You become {desc}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
        return retval

    async def remove_state(self, force=False) -> bool:
        if super().remove_state(force):
            dt_word = self.damage_type.word() if self.damage_type else "all"
            if self.multiplier < 1:
                msg = f"You are no longer resistant to {dt_word} damage."
            elif self.multiplier > 1:
                msg = f"You are no longer vulnerable to {dt_word} damage."
            else:
                msg = f"Your {dt_word} damage modifier fades."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        return False

    def get_my_status_message(self) -> Optional[str]:
        dt_word = self.damage_type.word() if self.damage_type else "all"
        if self.multiplier < 1:
            pct = int((1 - self.multiplier) * 100)
            return f"You have {pct}% resistance to {dt_word} damage."
        elif self.multiplier > 1:
            pct = int((self.multiplier - 1) * 100)
            return f"You have {pct}% vulnerability to {dt_word} damage."
        return None

    def get_room_status_message(self) -> Optional[str]:
        return None


class CharacterStateFrozen(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, **kwargs):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created, **kwargs)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_FROZEN)

    async def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = await super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You freeze {self.actor}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                await self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} freezes you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} freezes {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self._echo_to_room(msg, vars, exceptions=[self.actor, self.source_actor])
        return retval


    async def remove_state(self, force=False) -> bool:
        if not super().remove_state(force):
            return False
        if any([s for s in self.actor.current_states if s is not self \
                              and s.does_add_flag(TemporaryCharacterFlags.IS_FROZEN)]):
            return True
        self.actor.remove_temp_flags(self.character_flags_added)
        msg = "You unfreeze!"
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} unfreezes!"
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        await self._echo_to_room(msg, vars, exceptions=[self.actor])
        # NPCs automatically stand up when the freeze wears off
        if self.actor.actor_type == ActorType.CHARACTER and self.actor.location_room \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            # Queue the stand command so it goes through normal command handling
            self.actor.command_queue.append("stand")
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True

    def get_my_status_message(self) -> Optional[str]:
        return "You are frozen."
    def get_room_status_message(self) -> Optional[str]:
        return "%s% is frozen."


async def load_state_from_data(actor: ActorInterface, game_state: GameStateInterface, state_data: Dict[str, Any]) -> Optional[ActorState]:
    from .actors import Actor

    class_name = state_data.get('class')
    state_cls = globals().get(class_name)
    if not state_cls or not isinstance(state_cls, type) or not issubclass(state_cls, ActorState):
        raise ValueError(f"Unknown actor state class: {class_name}")
    if not getattr(state_cls, 'persist_on_save', False):
        return None

    duration_type_str = state_data.get('duration_type', DurationType.TIMED.value)
    try:
        duration_type = DurationType(duration_type_str)
    except ValueError:
        duration_type = DurationType.TIMED

    start_tick = _get_current_tick_value(game_state)

    if duration_type == DurationType.WHILE_SOURCE_PRESENT:
        source_id = state_data.get('source_refid') or state_data.get('source_instance_id')
        if source_id and Actor.get_reference_if_alive(source_id) is None:
            return None  # Source gone, state should be removed

    if duration_type == DurationType.TIMED:
        remaining_duration_ticks = state_data.get('remaining_duration_ticks')
        if remaining_duration_ticks is None:
            legacy_duration_seconds = state_data.get('duration')
            if legacy_duration_seconds is not None:
                remaining_duration_ticks = ticks_from_seconds(int(float(legacy_duration_seconds)))
        if remaining_duration_ticks is None:
            raise ValueError(f"Saved actor state {class_name} is missing remaining duration")
        remaining_duration_ticks = int(remaining_duration_ticks)
        if remaining_duration_ticks <= 0:
            return None
    else:
        remaining_duration_ticks = None

    if state_cls is CharacterStateCharmed:
        charmer = CharacterStateCharmed.resolve_saved_charmer(state_data)
        if charmer is None:
            state = CharacterStateConfused(
                actor=actor,
                game_state=game_state,
                source_actor=None,
                state_type_name="confused",
                tick_created=start_tick,
            )
            if remaining_duration_ticks:
                await state.restore_state(start_tick=start_tick, duration_ticks=remaining_duration_ticks)
            else:
                await state.apply_state(start_tick=start_tick)
            return state

    state = state_cls.from_saved_state(actor, game_state, state_data)
    if remaining_duration_ticks:
        await state.restore_state(start_tick=start_tick, duration_ticks=remaining_duration_ticks)
    else:
        state._restoring_state = True
        try:
            await state.apply_state(start_tick=start_tick)
        finally:
            state._restoring_state = False
    return state


