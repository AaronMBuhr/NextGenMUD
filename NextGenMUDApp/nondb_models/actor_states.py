from abc import abstractmethod
from typing import Dict, List
from ..command_handler_interface import CommandHandlerInterface
from ..communication import CommTypes
from ..core_actions_interface import CoreActionsInterface
from .actor_interface import ActorType
from .actors import Actor
from .character_interface import PermanentCharacterFlags, TemporaryCharacterFlags, GamePermissionFlags, EquipLocation
from .attacks_and_damage import DamageType, DamageResistances, DamageReduction
from ..utility import set_vars

class ActorState:

    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, vars=None,tick_created=None):
        self.actor: Actor = actor
        self.source_actor: Actor = source_actor
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
        self.game_state: 'GameStateInterface' = game_state

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
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
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
        return self.character_flags_affected.are_flags_set(flag)
    
    def perform_tick(self, tick_num: int) -> bool:
        self.duration_remaining = max(self.start_tick_ - tick_num, 0)
        self.last_tick_acted = tick_num
        if self.tick_ending != 0 and tick_num >= self.tick_ending:
            self.remove_state()
        return True
    
    @abstractmethod
    def get_affect_amount(self):
        return self.affect_amount


class CharacterStateForcedSitting(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

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
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} looks steady enough to stand again."
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                      game_state=self.game_state)
        if self.actortype_ == ActorType.CHARACTER and self.location_room \
            and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
            CommandHandlerInterface.get_instance().process_command(self.actor, "stand")
        if self.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)

        return True

    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateForcedSleeping(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SLEEPING)
        self.character_flags_added.add_flags(TemporaryCharacterFlags.IS_SITTING)

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
        if any([s for s in self.actor.current_states \
                              if s.does_add_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return True
        self.actor.remove_temp_flags(self.character_flags_added)
        msg = "You don't feel sleepy anymore."
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} doesn't look sleepy anymore."
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                    game_state=self.game_state)
        if self.actortype_ == ActorType.CHARACTER and self.location_room \
            and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
            CommandHandlerInterface.get_instance().process_command(self.actor, "stand")
        if self.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                await CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateStunned(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.character_flags_affected.add_flags(TemporaryCharacterFlags.IS_STUNNED)

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
        if any([s for s in self.actor.current_states \
                if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        
        msg = "You shake off the stun."
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
        msg = f"{self.actor.art_name_cap} shakes off the stun."
        set_vars(self.actor, self.source_actor, self.actor, msg)
        self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                        game_state=self.game_state)
        if self.actortype_ == ActorType.CHARACTER and self.location_room \
            and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
            CommandHandlerInterface.get_instance().process_command(self.actor, "stand")
        if self.location_room \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
            and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
            and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CoreActionsInterface.get_instance().do_aggro(self.actor)
        return True
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateHitPenalty(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateHitBonus(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None, \
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)


class CharacterStateDisarmed(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)

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
        if not force and any([s for s in self.actor.current_states if s.does_affect_flag(TemporaryCharacterFlags.IS_SLEEPING)]):
            return False
        mhw = self.vars["mhw"]
        ohw = self.vars["ohw"]
        bhw = self.vars["bhw"]
        if mhw and self.equipped_location_[EquipLocation.MAIN_HAND] is None:
            self.actor.remove_object(mhw)
            self.actor.equip_object(mhw)
        if ohw and self.equip_location_[EquipLocation.OFF_HAND] is None:
            self.actor.remove_object(ohw)
            self.actor.equip_object(ohw)
        if bhw and self.equip_location_[EquipLocation.BOTH_HANDS] is None:
            self.actor.remove_object(bhw)
            self.actor.equip_object(bhw)
        retval = super().remove_state(force)
        if retval is not None:
            self.remove_temp_flags(TemporaryCharacterFlags.IS_DISARMED)
            self.actor.remove_state(self)
            msg = "You ready your weapons again."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=self.game_state)
            msg = f"{self.actor.art_name_cap} readies {self.actor.pronoun_possessive} weapons again."
            set_vars(self.actor, self.source_actor, self.actor, msg)
            self.actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[self.source_actor],
                                          game_state=self.game_state)
            if self.actortype_ == ActorType.CHARACTER and self.location_room \
                and not self.has_perm_flags(PermanentCharacterFlags.IS_PC):
                CommandHandlerInterface.get_instance().process_command(self.actor, "stand")
            if self.location_room \
                and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING) \
                and not self.actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING) \
                and not self.actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
                    CoreActionsInterface.get_instance().do_aggro(self.actor)
        return retval
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDodgePenalty(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDodgeBonus(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateDamageBonus(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateBerserkerStance(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, dodge_penalty:int = 0, hit_bonus:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)

class CharacterStateBleeding(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
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
    
    def perform_tick(self, tick_num: int) -> bool:
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


class CharacterStateStealthed(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, affect_amount:int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.affect_amount = affect_amount

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        self.actor.add_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        self.vars = { "seen_by": [] }
        retval = super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick)
        return retval
    
    def remove_state(self) -> bool:
        self.actor.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        return super().remove_state()
        
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)
    


class CharacterStateShielded(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor = None, 
                 state_type_name=None, resistances: DamageResistances = None, reductions: DamageReduction = None,
                 vars=None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, vars, tick_created)
        self.extra_resistances: DamageResistances = resistances
        self.extra_reductions: DamageReduction = reductions

    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        if self.extra_resistances:
                self.actor.damage_resistances_.add_resistances(self.resistances)
            if self.extra_reductions:
                self.actor.damage_reductions_.add_reductions(self.reductions)
        return retval
    
    def remove_state(self) -> bool:
        if retval := super().remove_state():
            if self.extra_resistances:
                self.actor.damage_resistances_.remove_resistances(self.resistances)
            if self.extra_reductions:
                self.actor.damage_reductions_.remove_reductions(self.reductions)
        return retval
    
    def perform_tick(self, tick_num: int) -> bool:
        return super().perform_tick(tick_num)   


class CharacterStateCasting(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, tick_created=None, casting_finish_func: Callable=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.casting_finish_func = casting_finish_func
        
    def remove_state(self) -> bool:
        if self.casting_finish_func:
            self.casting_finish_func(self)
        return super().remove_state()
        

class CharacterStateRecoveryModifier(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, recovery_modifier: int = 0, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.recovery_modifier = recovery_modifier
        actor.recovery_time += recovery_modifier
        
    def remove_state(self) -> bool:
        self.actor.recovery_time -= self.recovery_modifier
        return super().remove_state()
        

class CharacterStateDamageResistance(ActorState):
    def __init__(self, actor: Actor, game_state: 'GameStateInterface', source_actor: Actor=None,
                 state_type_name=None, damage_resistances: DamageResistances = None, tick_created=None):
        super().__init__(actor, game_state, source_actor, state_type_name, tick_created)
        self.damage_resistances = damage_resistances
        
    def apply_state(self, start_tick=None, duration_ticks=None, end_tick=None) -> int:
        if not super().apply_state(start_tick, duration_ticks=duration_ticks, end_tick=end_tick):
            return False
        self.actor.damage_resistances_.add_resistances(self.damage_resistances)
        return True
        
    def remove_state(self) -> bool:
        self.actor.damage_resistances_.remove_resistances(self.damage_resistances)
        return super().remove_state()
        
       
    
class Cooldown:
    def __init__(self, actor: Actor, cooldown_name: str, game_state: 'GameStateInterface',
                 cooldown_source=None, cooldown_vars: dict=None, cooldown_end_fn: callable=None):
        self.cooldown_source = cooldown_source
        self.cooldown_name = cooldown_name
        self.actor: Actor = actor
        self.cooldown_vars: Dict = cooldown_vars
        self.cooldown_start_tick: int = 0
        self.cooldown_end_tick: int = 0
        self.cooldown_duration: int = 0
        self.cooldown_end_fn = cooldown_end_fn
        self.game_state = game_state

    @classmethod
    def has_cooldown(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return any([c for c in cooldowns if c.cooldown_source == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name == (cooldown_name or c.cooldown_name)])
    
    @classmethod
    def current_cooldowns(cooldowns: List['Cooldown'], cooldown_source = None, cooldown_name: str = None) -> bool:
        return [c for c in cooldowns if c.cooldown_source == (cooldown_source or c.cooldown_source) \
                    and c.cooldown_name == (cooldown_name or c.cooldown_name)]
    
    @classmethod
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

    def end_cooldown(self, actor: Actor, tick: int, game_state: ComprehensiveGameState, vars: Dict[str, Any]) -> bool:
        if self.cooldown_end_fn:
            self.cooldown_end_fn(self)
        return True

