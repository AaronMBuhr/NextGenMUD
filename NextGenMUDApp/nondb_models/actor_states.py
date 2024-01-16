from abc import abstractmethod
from typing import Dict, List
from ..command_handler_interface import CommandHandlerInterface
from ..communication import CommTypes
from ..core_actions_interface import CoreActionsInterface
from .actor_interface import ActorType
from .actors import Actor
from .character_interface import PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags
from ..utility import set_vars

class ActorState:

    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, vars=None,tick_created=None):
        self.actor_: Actor = actor
        self.source_actor_: Actor = source_actor
        self.state_type_name_: str = state_type_name
        self.tick_created_: int = tick_created
        self.tick_started_: int = None
        self.tick_ending_: int = None
        self.last_tick_acted_: int = None
        self.next_tick_: int = None
        self.tick_period_: int = 0
        self.character_flags_affected_: TemporaryCharacterFlags = TemporaryCharacterFlags(0)
        self.affect_amount_: int = 0
        self.duration_remaining_: int = 0
        self.vars = vars
        self.game_state: 'GameStateInterface' = game_state

    def to_dict(self):
        return {
            'class': self.__class__.__name__,
            'actor': self.actor_.rid,
            'tick_created': self.tick_created_,
            'tick_started': self.tick_started_,
            'tick_ending': self.tick_ending_,
            'last_tick_acted': self.last_tick_acted_,
            'next_tick': self.next_tick_,
            'tick_period': self.tick_period_
        }
    
    @abstractmethod
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        """
        Returns the next tick that the state should be applied.
        end_tick = 0 means it's indefinite
        """
        self.tick_started_ = start_tick
        self.tick_ending_ = end_tick
        self.next_tick_ = start_tick + self.tick_period_
        self.last_tick_acted_ = start_tick
        self.duration_remaining_ = self.tick_ending_ - self.tick_started_
        self.actor_.apply_state(self)
        return self.next_tick_

    @abstractmethod
    def remove_state(self, force=False) -> bool:
        """
        Returns True if the state was removed, False if it was not removed.
        """
        pass

    def does_affect_flag(self, flag: TemporaryCharacterFlags) -> bool:
        """
        Returns True if the state affects the given flag, False if it does not.
        """
        return self.character_flags_affected_.are_flags_set(flag)
    
    def perform_tick(self, tick_num: int) -> bool:
        self.duration_remaining_ = max(self.start_tick_ - tick_num, 0)
        self.last_tick_acted_ = tick_num
        if self.tick_ending_ != 0 and tick_num >= self.tick_ending_:
            self.remove_state()
        return True
    
    @abstractmethod
    def get_affect_amount(self):
        return self.affect_amount_


class CharacterStateForcedSitting(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_SITTING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            if self.source_actor:
                msg = f"You knock %%t onto the ground."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = f"{self.source_actor_.art_name_cap} knocks you onto the ground."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = f"{self.source_actor_.art_name_cap} knocks %t% onto the ground."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor], game_state=cls.game_state_)
            self.actor_.add_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        return retval


    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s is not self and s.does_affect_flag(TemporaryCharacterFlags.IS_SITTING)]):
            return False
        retval = super().remove_state(force)
        if retval:
            self.actor_.remove_state(self)
        msg = "The dizziness wears off, you feel steady enough to stand again."
        set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
        msg = "%t% looks steady enough to stand again."
        set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[source_actor], game_state=cls.game_state_)
        if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
            and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
            CommandHandlerInterface.get_instance().process_command(self.actor_, "stand")
        if self.location_room_ \
            and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor_.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CoreActionsInterface.get_instance().do_aggro(self.actor_)

        return retval

    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateForcedSleeping(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_SLEEPING)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            self.actor_.remove_temp_flags(TemporaryCharacterFlags.IS_SITTING)
            self.actor_.remove_temp_flags(TemporaryCharacterFlags.IS_SLEEPING)
            if self.source_actor:
                msg = f"You put %t% to sleep."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{self.source_actor_.art_name_cap} puts you to sleep."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{self.source_actor_.art_name_cap} puts %t% to sleep."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor], game_state=cls.game_state_)
        return retval



    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        retval = super().remove_state(force)
        if retval is not None:
            msg = "You don't feel sleepy anymore."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "%t% doesn't look sleepy anymore."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CommandHandlerInterface.get_instance().process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    CoreActionsInterface.get_instance().do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateStunned(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected_.add_flags(TemporaryCharacterFlags.IS_STUNNED)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if retval is not None:
            self.actor_.add_flag(TemporaryCharacterFlags.IS_STUNNED)
            if self.source_actor:
                msg = f"You stun %t%."
                vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
                self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg, game_state=cls.game_state_)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor], game_state=cls.game_state_)
        return retval

    def remove_state(self, force=False) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        retval = super().remove_state(force)
        if retval is not None:
            msg = "You shake off the stun."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "%t% shakes off the stun."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CommandHandlerInterface.get_instance().process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    CoreActionsInterface.get_instance().do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateHitPenalty(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        # not gonna say anything for a hit penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
        #         self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        return retval

    def remove_state(self) -> bool:
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDisarmed(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        if not retval is None:
            self.vars = {}
            mhw = self.vars["main hand weapon"] = self.actor_.equipment_[EquipLocation.MAIN_HAND]
            ohw = self.vars["off hand weapon"] = self.actor_.equipment_[EquipLocation.OFF_HAND]
            bhw = self.vars["both hands weapon"] = self.actor_.equipment_[EquipLocation.BOTH_HANDS]
            self.vars["main hand weapon"] = mhw
            self.vars["off hand weapon"] = ohw
            self.vars["both hands weapon"] = bhw
            if mhw == None and ohw == None and bhw == None:
                msg = "They aren't using any weapons."
                set_vars(self.actor_, self.source_actor_, self.actor_, msg)
                self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
                return
            if mhw:
                self.actor_.unequip_location(EquipLocation.MAIN_HAND)
                self.actor_.add_object(mhw)
            if ohw:
                self.actor_.unequip_location(EquipLocation.OFF_HAND)
                self.actor_.add_object(ohw)
            if bhw:
                self.actor_.unequip_location(EquipLocation.BOTH_HANDS)
                self.actor_.add_object(bhw)
            
            self.add_temp_flags(TemporaryCharacterFlags.IS_DISARMED)
            msg = f"You disarm %%t!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg, game_state=cls.game_state_)
            self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} disarms you!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} disarms %t%!"
            vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        return retval
    

    def remove_state(self, force=True) -> bool:
        if not force and any([s for s in self.actor_.current_states_ if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        mhw = self.vars["mhw"]
        ohw = self.vars["ohw"]
        bhw = self.vars["bhw"]
        if mhw and self.equipped_location_[EquipLocation.MAIN_HAND] is None:
            self.actor_.remove_object(mhw)
            self.actor_.equip_object(mhw)
        if ohw and self.equip_location_[EquipLocation.OFF_HAND] is None:
            self.actor_.remove_object(ohw)
            self.actor_.equip_object(ohw)
        if bhw and self.equip_location_[EquipLocation.BOTH_HANDS] is None:
            self.actor_.remove_object(bhw)
            self.actor_.equip_object(bhw)
        retval = super().remove_state(force)
        if retval is not None:
            self.remove_temp_flags(TemporaryCharacterFlags.IS_DISARMED)
            self.actor_.remove_state(self)
            msg = "You ready your weapons again."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state_)
            msg = "$cap(%t%) readies %R% weapons again."
            set_vars(self.actor_, self.source_actor_, self.actor_, msg)
            self.actor_.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[source_actor], game_state=cls.game_state_)
            if self.actor_type_ == ActorType.CHARACTER and self.location_room_ \
                and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CommandHandlerInterface.get_instance().process_command(self.actor_, "stand")
            if self.location_room_ \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor_.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor_.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    CoreActionsInterface.get_instance().do_aggro(self.actor_)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDodgePenalty(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not duration_ticks and not end_tick:
            raise Exception("duration and end_tick are both None")
        if duration_ticks and end_tick:
            raise Exception("duration and end_tick are both set")   
        if duration_ticks:
            end_tick = start_tick + duration_ticks
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        # not gonna say anything for a dodge penalty
        # if retval is not None:
        #     if self.source_actor:
        #         msg = f"You stun %t%."
        #         vars = set_vars(self.source_actor_, self.source_actor_, self.actor_, msg)
        #         self.source_actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor_.article_, self.source_actor_.name_, cap=True)} stuns you."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor_.echo(CommTypes.DYNAMIC, msg, vars)
        #     msg = f"{article_plus_name(self.source_actor.article_, self.source_actor_.name_)} stuns %t%."
        #     vars = set_vars(self.actor_, self.source_actor_, self.actor_, msg)
        #     self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, source_actor])
        return retval
    
    def remove_state(self) -> bool:
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateStealthed(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount_ = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        self.actor.add_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        self.vars = { "seen_by": [] }
        retval = super().apply_state(start_tick, duration_ticks=None, end_tick=end_tick)
        return retval
    
    def remove_state(self) -> bool:
        self.actor.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)
    


    
class Cooldown:
    def __init__(self, actor: Actor, cooldown_name: str, game_state: 'GameStateInterface',
                 cooldown_source=None, cooldown_vars: dict=None, cooldown_end_fn: callable=None):
        self.cooldown_source_ = cooldown_source
        self.cooldown_name_ = cooldown_name
        self.actor_: Actor = actor
        self.cooldown_vars: Dict = cooldown_vars
        self.cooldown_start_tick_: int = 0
        self.cooldown_end_tick_: int = 0
        self.cooldown_duration: int = 0
        self.cooldown_end_fn_ = cooldown_end_fn
        self.game_state_ = game_state

    @classmethod
    def has_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return any([c for c in cooldowns if c.cooldown_source_ == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name_ == (cooldown_name or c.cooldown_name)])
    
    @classmethod
    def current_cooldowns(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return [c for c in cooldowns if c.cooldown_source_ == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name_ == (cooldown_name or c.cooldown_name)]
    
    @classmethod
    def last_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return max([c for c in Cooldown.current_cooldowns(cooldowns, cooldown_source, cooldown_name)],
                   key=lambda c: c.cooldown_end_tick_)
    
    def start(self, current_tick: int, cooldown_duration_ticks: int = None, cooldown_end_tick: int = None) -> bool:
        self.cooldown_start_tick_ = current_tick
        if cooldown_duration_ticks:
            self.cooldown_duration_ = cooldown_duration_ticks
            self.cooldown_end_tick_ = current_tick + cooldown_duration_ticks
        else:
            self.cooldown_end_tick_ = cooldown_end_tick
            self.cooldown_duration_ = cooldown_end_tick - current_tick
        return True

    def to_dict(self):
        return {
            'actor': self.actor_.rid,
            'cooldown_source': self.cooldown_source_,
            'cooldown_name': self.cooldown_name_,
            'cooldown_start_tick': self.cooldown_start_tick_,
            'cooldown_end_tick': self.cooldown_end_tick_,
            'cooldown_duration': self.cooldown_end_tick_ - self.cooldown_start_tick_
        }

    def cooldown_finished(self, current_tick: int) -> bool:
        return current_tick >= self.cooldown_end_tick_
    
    def ticks_remaining(self, current_tick: int) -> int:
        return max(self.cooldown_end_tick_ - current_tick, 0)

    def end_cooldown(self) -> bool:
        if self.cooldown_end_fn_:
            self.cooldown_end_fn_(self)
        return True

