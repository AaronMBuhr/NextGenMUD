from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation, TemporaryCharacterFlags, PermanentCharacterFlags
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBleeding, CharacterStateHitBonus, CharacterStateStealthed, Cooldown
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageMultipliers
# CharacterSkill import removed - not used in this file
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, seconds_from_ticks, firstcap
from .core_actions_interface import CoreActionsInterface
import random


class Skills_Rogue(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["stealth", "backstab", "pick lock", "detect traps"]
        tier2_skills = ["poison", "evasion", "disarm trap", "dual wield"]
        tier3_skills = ["shadowstep", "deadly strike", "smoke bomb"]
        tier4_skills = ["assassinate", "vanish"]
        
        skill_name = skill_name.lower()
        
        if skill_name in tier1_skills:
            return Skills.TIER1_MIN_LEVEL
        elif skill_name in tier2_skills:
            return Skills.TIER2_MIN_LEVEL
        elif skill_name in tier3_skills:
            return Skills.TIER3_MIN_LEVEL
        elif skill_name in tier4_skills:
            return Skills.TIER4_MIN_LEVEL
        else:
            return Skills.TIER1_MIN_LEVEL  # Default
    
    # Stealth
    STEALTH = Skill(
        name="stealth",
        base_class=CharacterClassRole.ROGUE,
        cooldown_name="stealth",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(60),  # 1 minute
        duration_max_ticks=ticks_from_seconds(60),
        message_prepare="You begin to move silently...",
        message_success_subject="You blend into the shadows!",
        message_success_target=None,
        message_success_room=None,  # Others don't see this
        message_failure_subject="You fail to blend into the shadows!",
        message_failure_target=None,
        message_failure_room="$cap(%a%) attempts to hide but fails!",
        message_apply_subject="You are hidden from view!",
        message_apply_target=None,
        message_apply_room=None,  # Others don't see this
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )
    
    # Backstab
    BACKSTAB = Skill(
        name="backstab",
        base_class=CharacterClassRole.ROGUE,
        cooldown_name="backstab",
        cooldown_ticks=ticks_from_seconds(10),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You prepare to strike from the shadows...",
        message_success_subject="You strike from the shadows!",
        message_success_target="$cap(%a%) strikes you from the shadows!",
        message_success_room="$cap(%a%) strikes %t% from the shadows!",
        message_failure_subject="Your backstab fails!",
        message_failure_target="$cap(%a%) attempts to backstab you but fails!",
        message_failure_room="$cap(%a%) attempts to backstab %t% but fails!",
        message_apply_subject="You backstab %t% for critical damage!",
        message_apply_target="$cap(%a%) backstabs you for critical damage!",
        message_apply_room="$cap(%a%) backstabs %t% for critical damage!",
        message_resist_subject="%t% notices you and evades your backstab!",
        message_resist_target="You notice $cap(%a%) and evade %Q% backstab!",
        message_resist_room="%t% notices $cap(%a%) and evades %Q% backstab!",
        skill_function=None  # Will be implemented later
    )
    
    # Pick Lock
    PICK_LOCK = Skill(
        name="pick lock",
        base_class=CharacterClassRole.ROGUE,
        cooldown_name="pick_lock",
        cooldown_ticks=ticks_from_seconds(5),
        cast_time_ticks=ticks_from_seconds(3.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You examine the lock carefully...",
        message_success_subject="You successfully pick the lock!",
        message_success_target=None,
        message_success_room="$cap(%a%) successfully picks a lock!",
        message_failure_subject="You fail to pick the lock!",
        message_failure_target=None,
        message_failure_room="$cap(%a%) fails to pick a lock!",
        message_apply_subject="The lock clicks open!",
        message_apply_target=None,
        message_apply_room="A lock clicks open as $cap(%a%) works on it!",
        message_resist_subject="This lock is too complex for your skills!",
        message_resist_target=None,
        message_resist_room="$cap(%a%) struggles with a complex lock!",
        skill_function=None  # Will be implemented later
    )
    
    # Detect Traps
    DETECT_TRAPS = Skill(
        name="detect traps",
        base_class=CharacterClassRole.ROGUE,
        cooldown_name="detect_traps",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(300),  # 5 minutes
        duration_max_ticks=ticks_from_seconds(300),
        message_prepare="You scan the area for traps...",
        message_success_subject="Your senses become attuned to hidden dangers!",
        message_success_target=None,
        message_success_room="$cap(%a%) carefully examines the surroundings!",
        message_failure_subject="You fail to detect any traps!",
        message_failure_target=None,
        message_failure_room="$cap(%a%) looks around but seems unsure!",
        message_apply_subject="You can now detect hidden traps!",
        message_apply_target=None,
        message_apply_room="$cap(%a%) seems more aware of the surroundings!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )

    @classmethod
    async def do_rogue_backstab(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Rogue.BACKSTAB
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_rogue_backstab_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_rogue_backstab_finish(cls, actor: Actor, target: Actor, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        BACKSTAB_DAMAGE_MULT = 4
        BACKSTAB_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        cooldown = Cooldown(actor, "backstab", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": BACKSTAB_COOLDOWN_TICKS})
        await cooldown.start(game_tick, BACKSTAB_COOLDOWN_TICKS)
        
        level_mult = actor.levels_by_role[CharacterClassRole.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        
        mhw = actor.equipped_[EquipLocation.MAIN_HAND]
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][Skills_Rogue.BACKSTAB], difficulty_modifier):
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
    async def do_rogue_stealth(cls, actor: Actor, target: Actor, 
                              difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Rogue.STEALTH
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_rogue_stealth_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_rogue_stealth_finish(cls, actor: Actor, target: Actor, 
                                     difficulty_modifier=0, game_tick=0) -> bool:
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
        level_mult = sneaker.levels_by_role[CharacterClassRole.ROGUE] / viewer.total_levels()
        attrib_mod = (sneaker.attributes[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        return cls.do_skill_check(sneaker, sneaker.skills_by_class[CharacterClassRole.ROGUE][Skills_Rogue.STEALTH], difficulty_modifier)
    
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
    async def do_rogue_evade(cls, actor: Actor, target: Actor, 
                            difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Rogue.EVADE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_rogue_evade_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_rogue_evade_finish(cls, actor: Actor, target: Actor, 
                                   difficulty_modifier=0, game_tick=0) -> bool:
        EVADE_DURATION_MIN = ticks_from_seconds(6)
        EVADE_DURATION_MAX = ticks_from_seconds(12)
        EVADE_DODGE_BONUS_MIN = 4
        EVADE_DODGE_BONUS_MAX = 8
        level_mult = actor.levels_by_role[CharacterClassRole.ROGUE] / 4
        duration = random.randint(EVADE_DURATION_MIN, EVADE_DURATION_MAX)
        dodge_bonus = random.randint(EVADE_DODGE_BONUS_MIN, EVADE_DODGE_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][Skills_Rogue.EVADE],
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
    async def do_rogue_pickpocket(cls, actor: Actor, target: Actor, 
                                 difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Pickpocketing is not yet implemented!", cls.game_state)
        return False 