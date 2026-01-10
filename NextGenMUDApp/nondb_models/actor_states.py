from abc import abstractmethod
from typing import Dict, List, Any, TYPE_CHECKING
from ..command_handler_interface import CommandHandlerInterface
from ..communication import CommTypes
from ..core_actions_interface import CoreActionsInterface
from .actor_interface import ActorType, ActorInterface
from .character_interface import PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags, EquipLocation, CharacterInterface
from .attacks_and_damage import DamageType, DamageMultipliers, DamageReduction
from ..utility import set_vars
from ..comprehensive_game_state_interface import GameStateInterface

if TYPE_CHECKING:
    from .actors import Actor
    from .characters import Character
    from .objects import Object
    from .rooms import Room
    from .triggers import Trigger
    from .zones import Zone
    from .world import WorldDefinition

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
        self.game_state.add_scheduled_event(self, EventType.COOLDOWN_OVER, 
                                            self.cooldown_name, self.cooldown_vars, self.end_cooldown)
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

    def end_cooldown(self, actor: ActorInterface, tick: int, game_state: "GameStateInterface", vars: Dict[str, Any]) -> bool:
        if self.cooldown_end_fn:
            self.cooldown_end_fn(self)
        self.actor.cooldowns.remove(self)
        return True



class ActorState:

    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, vars=None,tick_created=None):
        self.actor: ActorInterface = actor
        self.source_actor: ActorInterface = source_actor
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
        
    def does_add_flag(self, flag: TemporaryCharacterFlags) -> bool:
        return self.character_flags_added.are_flags_set(flag)
    
    def does_remove_flag(self, flag: TemporaryCharacterFlags) -> bool:
        return self.character_flags_removed.are_flags_set(flag)
    
    @abstractmethod
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        """
        Returns the next tick that the state should be applied.
        duration_ticks and end_tick both None means it's indefinite
        """
        if duration_ticks and not end_tick:
            self.tick_ending = start_tick + duration_ticks
        elif duration_ticks and end_tick:
            raise Exception("duration_ticks and end_tick both set")
        else:
            self.tick_ending = end_tick
        self.tick_started = start_tick
        self.next_tick = start_tick + self.tick_period
        self.last_tick_acted = start_tick
        self.duration_remaining = self.tick_ending - self.tick_started
        self.actor.apply_state(self)
        self.game_state.add_scheduled_event(self, EventType.STATE_END, self, "state_end", self.tick_ending, 
                                            None, None, lambda a, t, s, v: self.remove_state())
        if pulse_period_ticks:
            self.game_state.add_scheduled_event(self, EventType.STATE_PULSE, self, f"state_pulse:{self.state_type_name}",
                                                self.next_tick, self.tick_period, None, lambda a, t, s, v: self.perform_pulse(t, s, v))
        return self.next_tick

    @abstractmethod
    def remove_state(self, force=False) -> bool:
        """
        Returns True if the state was removed, False if it was not removed.
        """
        self.actor.remove_state(self)
        return True

    def does_affect_flag(self, flag: TemporaryCharacterFlags) -> bool:
        """
        Returns True if the state affects the given flag, False if it does not.
        """
        return self.character_flags_added.are_flags_set(flag)
    
    def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        self.duration_remaining = max(self.start_tick_ - tick_num, 0)
        self.last_tick_acted = tick_num
        if self.duration_remaining > 0:
            self.next_tick = tick_num + self.tick_period
            self.game_state.add_scheduled_event(self, EventType.STATE_PULSE, self, f"state_pulse:{self.state_type_name}",
                                                self.next_tick, self.tick_period, None, lambda a, t, s, v: self.perform_pulse(t, s, v))
        return True
    
    @abstractmethod
    def get_affect_amount(self):
        return self.affect_amount


class CharacterStateForcedSitting(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You knock {self.actor.art_name} onto the ground."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, self.game_state)
            msg = f"{self.source_actor.art_name_cap} knocks you onto the ground."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, self.game_state)
            msg = f"{self.source_actor.art_name_cap} knocks {self.actor.art_name} onto the ground."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor, self.source_actor],
                                          game_state=self.game_state)
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
        await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                      game_state=self.game_state)
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


class CharacterStateForcedSleeping(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SLEEPING)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You put {self.actor} to sleep."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} puts you to sleep."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} puts {self.actor.art_name} to sleep."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor, self.source_actor],
                                          game_state=self.game_state)
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
        await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor],
                                    game_state=self.game_state)
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
        


class CharacterStateStunned(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_STUNNED)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_flag(TemporaryCharacterFlags.IS_STUNNED)
            if self.source_actor:
                msg = f"You stun {self.actor.art_name}."
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} stuns you."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg, game_state=self.game_state)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} stuns {self.actor.art_name}."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars,
                                          exceptions=[self.actor, self.source_actor], game_state=self.game_state)
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
        await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor],
                                        game_state=self.game_state)
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True
        


class CharacterStateHitPenalty(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
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
        

class CharacterStateHitBonus(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"{self.actor.art_name_cap} feels {self.state_type_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"You feel {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            self.actor.hit_modifier += self.affect_amount
        return retval

    def remove_state(self) -> bool:
        if super().remove_state():
            msg = f"You no longer feel {self.state_type_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars)
            self.actor.hit_modifier -= self.affect_amount
            return True
        else:
            return False
        


class CharacterStateDisarmed(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if not retval is None:
            self.vars = {}
            mhw = self.vars["main hand weapon"] = self.actor.equipment_[EquipLocation.MAIN_HAND]
            ohw = self.vars["off hand weapon"] = self.actor.equipment_[EquipLocation.OFF_HAND]
            bhw = self.vars["both hands weapon"] = self.actor.equipment_[EquipLocation.BOTH_HANDS]
            self.vars["main hand weapon"] = mhw
            self.vars["off hand weapon"] = ohw
            self.vars["both hands weapon"] = bhw
            if mhw == None and ohw == None and bhw == None:
                msg = "They aren't using any weapons."
                set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                return
            if mhw:
                self.actor.unequip_location(EquipLocation.MAIN_HAND)
                self.actor.add_object(mhw)
            if ohw:
                self.actor.unequip_location(EquipLocation.OFF_HAND)
                self.actor.add_object(ohw)
            if bhw:
                self.actor.unequip_location(EquipLocation.BOTH_HANDS)
                self.actor.add_object(bhw)
            
            self.add_temp_flags(TemporaryCharacterFlags.IS_DISARMED)
            msg = f"You disarm {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg, game_state=self.game_state)
            self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} disarms you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} disarms {actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor, self.source_actor])
        return retval
    

    async def remove_state(self, force=True) -> bool:
        if not force and any([s for s in self.actor.current_states if s is not self \
                              and s.does_affect_flag(TemporaryCharacterFlags.IS_DISARMED)]):
            return True
        mhw = self.vars.get("mhw")
        ohw = self.vars.get("ohw")
        bhw = self.vars.get("bhw")
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
        await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor],
                                      game_state=self.game_state)
        # Re-aggro if appropriate
        if self.actor.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True
        

class CharacterStateDodgePenalty(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
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
        

class CharacterStateDodgeBonus(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
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
        

class CharacterStateDamageBonus(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        
        self.actor.damage_modifier += self.affect_amount
        
        if self.source_actor:
            msg = f"{self.actor.art_name_cap} becomes {self.state_type_name}!"
            vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
            self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        
        msg = f"You become {self.state_type_name}!"
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        
        msg = f"{self.actor.art_name_cap} becomes {self.state_type_name}!"
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                     exceptions=[self.actor], game_state=self.game_state)
        return True
    
    def remove_state(self) -> bool:
        self.actor.damage_modifier -= self.affect_amount
        msg = f"You are no longer {self.state_type_name}."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        
        msg = f"{self.actor.art_name_cap} is no longer {self.state_type_name}."
        vars = set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                     exceptions=[self.actor], game_state=self.game_state)
        return super().remove_state()
        

class CharacterStateBerserkerStance(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, dodge_penalty:int = 0, hit_bonus:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.dodge_penalty = dodge_penalty
        self.hit_bonus = hit_bonus

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
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


class CharacterStateDefensiveStance(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, dodge_bonus:int = 0, hit_penalty:int = 0, damage_multipliers=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.dodge_bonus = dodge_bonus
        self.hit_penalty = hit_penalty
        self.damage_multipliers = damage_multipliers

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
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
        

class CharacterStateBleeding(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"You tear open bloody wounds on {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} tears open bloody wounds on you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} tears open bloody wounds on {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor, self.source_actor],
                                          game_state=self.game_state)
        return retval

    def remove_state(self) -> bool:
        if retval := super().remove_state():
            msg = "Your wounds stop bleeding."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.actor.art_name_cap} stops bleeding."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                          game_state=self.game_state)
        return retval
    
    def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_tick(tick_num):
            msg = f"Your wounds bleed for {self.affect_amount} damage."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"%t%'s wounds bleed for {self.affect_amount} damage."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                          game_state=self.game_state)
            CoreActionsInterface.get_instance().do_damage(self.source_actor, self.actor, self.affect_amount,
                                                          DamageType.RAW, False)
        return retval

class CharacterStateStealthed(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount
        self.character_flags_added = TemporaryCharacterFlags.IS_STEALTHED

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        self.actor.add_temp_flags(self.character_flags_added)
        self.vars = { "seen_by": [] }
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        return retval
    
    def remove_state(self) -> bool:
        self.actor.remove_temp_flags(self.character_flags_added)
        return super().remove_state()
        


class CharacterStateShielded(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface = None, 
                 state_type_name=None, multipliers: DamageMultipliers = None, reductions: DamageReduction = None,
                 vars=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, vars, tick_created)
        self.extra_multipliers: DamageMultipliers = multipliers
        self.extra_reductions: DamageReduction = reductions

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
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
    

class CharacterStateCasting(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, casting_finish_func: callable=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.casting_finish_func = casting_finish_func
        
    def remove_state(self) -> bool:
        if self.casting_finish_func:
            self.casting_finish_func(self)
        return super().remove_state()
        

class CharacterStateRecoveryModifier(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, recovery_modifier: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.recovery_modifier = recovery_modifier
        actor.recovery_time += recovery_modifier
        
    def remove_state(self) -> bool:
        self.actor.recovery_time -= self.recovery_modifier
        return super().remove_state()
        

class CharacterStateDamageMultipliers(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_multipliers: DamageMultipliers = None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.damage_multipliers = damage_multipliers
        
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        self.actor.damage_multipliers.add_multipliers(self.damage_multipliers)
        return True
        
    def remove_state(self) -> bool:
        self.actor.damage_multipliers.minus_multipliers(self.damage_multipliers)
        return super().remove_state()
        

class CharacterStateBurning(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None, damage_amount: int = 0):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.damage_amount = damage_amount

    def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_tick(tick_num):
            damage, target_hp = CoreActionsInterface.get_instance().do_calculated_damage(self.source_actor, self.actor, self.affect_amount,
                                                          DamageType.FIRE, False, False)
            if damage > 0:
                msg = f"You burn for {self.affect_amount} damage!"
                set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"%t% burns!"
                set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                            game_state=self.game_state)
            if target_hp <= 0:
                CoreActionsInterface.get_instance().do_die(self.actor, self.actor)
        return retval



class CharacterStateArmorBonus(ActorState):
    """Adds flat damage reduction to physical damage types (slashing, piercing, bludgeoning)."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, affect_amount: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
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


class CharacterStateRegenerating(ActorState):
    """Heals the target periodically over time."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, heal_amount: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.heal_amount = heal_amount
        self.total_healed = 0

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick, 
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None:
            if self.source_actor and self.source_actor != self.actor:
                msg = f"You invoke regenerative magic upon {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.source_actor.art_name_cap} invokes regenerative magic upon you!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            else:
                msg = "Regenerative magic flows through you!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Regenerative magic surrounds {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                         exceptions=[self.actor, self.source_actor] if self.source_actor else [self.actor],
                                         game_state=self.game_state)
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            msg = f"The regenerative magic fades. (Total healed: {self.total_healed})"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval
    
    def perform_pulse(self, tick_num: int, game_state: GameStateInterface, vars: Dict[str, Any]) -> bool:
        if retval := super().perform_pulse(tick_num, game_state, vars):
            old_hp = self.actor.current_hit_points
            self.actor.current_hit_points = min(self.actor.max_hit_points, 
                                                self.actor.current_hit_points + self.heal_amount)
            actual_heal = int(self.actor.current_hit_points - old_hp)
            self.total_healed += actual_heal
            
            if actual_heal > 0:
                msg = f"Regenerative magic heals you for {actual_heal} hit points!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        return retval


class CharacterStateZealotry(ActorState):
    """Increases damage dealt but reduces healing received."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_bonus: int = 0, healing_penalty: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.damage_bonus = damage_bonus
        self.healing_penalty = healing_penalty  # Percentage reduction in healing received (e.g., 50 = 50% less healing)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
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


class CharacterStateCharmed(ActorState):
    """Marks a character as charmed/controlled by another character."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.charmed_by = source_actor
        self.character_flags_added = TemporaryCharacterFlags(0)  # Could add IS_CHARMED flag if needed

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            # Store reference to who charmed this character
            self.actor.charmed_by = self.charmed_by
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            # Check if still charmed by another effect
            still_charmed = any(s for s in self.actor.current_states 
                               if s is not self and isinstance(s, CharacterStateCharmed))
            if not still_charmed:
                self.actor.charmed_by = None
                msg = f"{self.actor.art_name_cap} is no longer under your control!"
                vars = set_vars(self.charmed_by, self.charmed_by, self.actor, msg)
                await self.charmed_by.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
                msg = f"{self.actor.art_name_cap} breaks free from {self.charmed_by.art_name}'s control!"
                vars = set_vars(self.actor, self.charmed_by, self.actor, msg)
                await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                                   exceptions=[self.charmed_by], game_state=self.game_state)
        return retval


class CharacterStateConsecrated(ActorState):
    """Burns the target with holy fire periodically over time, dealing holy damage."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_amount: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.damage_amount = damage_amount
        self.total_damage = 0

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick,
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None:
            if self.source_actor:
                msg = f"Holy fire engulfs {self.actor.art_name}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Holy fire engulfs you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"Holy fire engulfs {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                         exceptions=[self.actor, self.source_actor],
                                         game_state=self.game_state)
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
                msg = f"{self.actor.art_name_cap} burns with holy fire!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                                   exceptions=[self.actor], game_state=self.game_state)
        return retval


class CharacterStateIgnited(ActorState):
    """Burns the target periodically over time, dealing fire damage."""
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, damage_amount: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.damage_amount = damage_amount
        self.total_damage = 0

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None, pulse_period_ticks=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick,
                                     pulse_period_ticks=pulse_period_ticks)
        if retval is not None:
            if self.source_actor:
                msg = f"You set {self.actor.art_name} ablaze!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} sets you ablaze!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} sets {self.actor.art_name} ablaze!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                         exceptions=[self.actor, self.source_actor],
                                         game_state=self.game_state)
        return retval

    async def remove_state(self, force=False) -> bool:
        if retval := super().remove_state(force):
            msg = "The flames on you die out."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"The flames on {self.actor.art_name} die out."
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                               exceptions=[self.actor], game_state=self.game_state)
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
                msg = f"{self.actor.art_name_cap} burns!"
                vars = set_vars(self.actor, self.source_actor, self.actor, msg)
                await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, 
                                                   exceptions=[self.actor], game_state=self.game_state)
        return retval


class CharacterStateFrozen(ActorState):
    def __init__(self, actor: ActorInterface, game_state: GameStateInterface, source_actor: ActorInterface=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created=tick_created)
        self.character_flags_added = self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_FROZEN)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        if retval is not None:
            self.actor.add_temp_flags(self.character_flags_added)
            if self.source_actor:
                msg = f"You freeze {self.actor}!"
                vars = set_vars(self.source_actor, self.source_actor, self.actor, msg)
                self.source_actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} freezes you!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.source_actor.art_name_cap} freezes {self.actor.art_name}!"
            vars = set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor, self.source_actor],
                                          game_state=self.game_state)
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
        await self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.actor],
                                    game_state=self.game_state)
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
        

