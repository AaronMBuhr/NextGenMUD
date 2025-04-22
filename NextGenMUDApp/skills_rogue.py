from .skills_core import Skills
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation, TemporaryCharacterFlags, PermanentCharacterFlags
from .nondb_models.actor_states import (
    CharacterStateStealthed, CharacterStateDodgeBonus, Cooldown
)
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, seconds_from_ticks
from .core_actions_interface import CoreActionsInterface

class Skills_Rogue(Skills):
    @classmethod
    async def do_rogue_backstab(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        BACKSTAB_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        
        if actor.cooldowns.has_cooldown(actor, "backstab"):
            msg = f"You can't use backstab again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        if not actor.has_temp_flags(TemporaryCharacterFlags.HIDDEN):
            msg = "You must be hidden to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        if target == None:
            msg = "You must specify a target to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        if actor.equipped_[EquipLocation.BOTH_HANDS]:
            msg = "You can't backstab with a two-handed weapon!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        mhw = actor.equipped_[EquipLocation.MAIN_HAND]
        if not mhw:
            msg = "You must have a weapon equipped to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_rogue_backstab_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You aim your backstab..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += BACKSTAB_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, BACKSTAB_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_rogue_backstab_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        BACKSTAB_DAMAGE_MULT = 4
        BACKSTAB_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        cooldown = Cooldown(actor, "backstab", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": BACKSTAB_COOLDOWN_TICKS})
        await cooldown.start(game_tick, BACKSTAB_COOLDOWN_TICKS)
        
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        attrib_mod = (actor.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        
        mhw = actor.equipped_[EquipLocation.MAIN_HAND]
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.BACKSTAB], difficulty_modifier):
            damage = roll_dice(mhw.damage_dice_number_, mhw.damage_dice_size_, mhw.damage_dice_modifier_) * BACKSTAB_DAMAGE_MULT
            msg = f"You backstab {target.art_name} for {damage} damage!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs you for {damage} damage!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs {target.art_name}!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, mhw.damage_type_)
            return True
        else:
            msg = f"You try to backstab {target.art_name}, but fumble your attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab you, but fumbles {actor.pronoun_possessive} attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab {target.art_name}, but fumbles {actor.pronoun_possessive} attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

    @classmethod
    async def do_rogue_stealth(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        STEALTH_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_rogue_stealth_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You focus on your stealth..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += STEALTH_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, STEALTH_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_rogue_stealth_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        STEALTH_RETRY_COOLDOWN_SEC = 3
        RETRY_SKILL_CHECK_SEC = 10
        last_cooldown = actor.last_cooldown(actor, Cooldown.last_cooldown(actor.cooldowns_, cooldown_source=cls.do_rogue_stealth))
        if last_cooldown:
            secs_remaining = seconds_from_ticks(last_cooldown.ticks_remaining(game_tick))
            msg = f"You can't retry stealth for another {secs_remaining} seconds!"
            vars = set_vars(actor, actor, target, msg, {'d': secs_remaining})
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        # cooldown before re-trying to stealth
        new_cooldown = Cooldown(actor, "stealth", cls.game_state, cooldown_source=cls.do_rogue_stealth)
        actor.add_cooldown(new_cooldown)
        new_cooldown.start(game_tick, ticks_from_seconds(STEALTH_RETRY_COOLDOWN_SEC))
        # have to re-try skill check
        new_cooldown = Cooldown(actor, "recheck stealth", cls.game_state, cooldown_source=cls.do_rogue_stealth, 
                                cooldown_vars=None, cooldown_end_fn=lambda cd: cls.recheck_stealth(actor,cd))
        actor.add_cooldown(new_cooldown)
        new_cooldown.start(game_tick, ticks_from_seconds(RETRY_SKILL_CHECK_SEC))
        return True

    @classmethod
    def stealthcheck(cls, sneaker: Actor, viewer: Actor, difficulty_modifier=0) -> bool:
        """
        Returns True if the actor successfully stealths, False otherwise"""
        level_mult = sneaker.levels_[CharacterClassRole.ROGUE] / viewer.total_levels_()
        attrib_mod = (sneaker.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        return cls.do_skill_check(sneaker, sneaker.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.STEALTH], difficulty_modifier)
    
    @classmethod
    def remove_stealth(cls, actor: Actor):
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        states = [s for s in actor.current_states if s is CharacterStateStealthed]
        for s in actor.remove_state:
            actor.remove_state(s)
        cds = [cd for cd in actor.cooldowns_ if cd.cooldown_source_ == cls.do_rogue_stealth]

    @classmethod
    def recheck_stealth(cls, sneaker: Actor, cooldown: Cooldown=None):
        if not sneaker.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
            retval = False
        for viewer in sneaker._location_room:
            if viewer == sneaker:
                continue
            if not cls.stealthcheck(sneaker, viewer):
                msg = f"You notice {sneaker.art_name} trying to hide!"
                vars = set_vars(sneaker, sneaker, viewer, msg, cls.game_state)
                viewer.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                if viewer.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE):
                    msg = f"{viewer.art_name} notices you and attacks!"
                    vars = set_vars(sneaker, viewer, sneaker, msg)
                    sneaker.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                    msg = f"{viewer.art_name_cap} notices {sneaker.art_name} and attacks!"
                    vars = set_vars(sneaker, sneaker, viewer, msg)
                    sneaker._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[sneaker, viewer], game_state=cls.game_state)
                    cls.remove_stealth(sneaker)
                    CoreActionsInterface.get_instance().start_fighting(viewer,sneaker)
                    CoreActionsInterface.get_instance().start_fighting(sneaker,viewer)
                retval = False

    @classmethod
    async def do_rogue_evade(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        EVADE_CAST_TIME_TICKS = ticks_from_seconds(0.25)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_rogue_evade_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You focus on evading blows..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += EVADE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, EVADE_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_rogue_evade_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0) -> bool:
        EVADE_DURATION_MIN = ticks_from_seconds(6)
        EVADE_DURATION_MAX = ticks_from_seconds(12)
        EVADE_DODGE_BONUS_MIN = 4
        EVADE_DODGE_BONUS_MAX = 8
        level_mult = actor.levels_[CharacterClassRole.ROGUE] / 4
        duration = random.randint(EVADE_DURATION_MIN, EVADE_DURATION_MAX)
        dodge_bonus = random.randint(EVADE_DODGE_BONUS_MIN, EVADE_DODGE_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.EVADE],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateDodgeBonus(target, actor, "evading", dodge_bonus, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You focus on evading blows!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try being evasive, but fail!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

    @classmethod
    async def do_rogue_pickpocket(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Pickpocketing is not yet implemented!", cls.game_state)
        return False 