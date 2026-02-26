from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill, SkillType, SkillAICondition, SkillsRegistry
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation, PermanentCharacterFlags
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBleeding, CharacterStateHitBonus, CharacterStateIgnited, 
    CharacterStateCharmed, Cooldown
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageMultipliers
from .nondb_models.objects import Corpse
from .nondb_models.characters import Character
# CharacterSkill import removed - not used in this file
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, firstcap
from .core_actions_interface import CoreActionsInterface


        # CharacterClassRole.MAGE: {
        #     # Tier 1 (Levels 1-9)
        #     MageSkills.MAGIC_MISSILE: SkillsInterface.TIER1_MIN_LEVEL,
        #     MageSkills.ARCANE_BARRIER: SkillsInterface.TIER1_MIN_LEVEL,
        #     MageSkills.BURNING_HANDS: SkillsInterface.TIER1_MIN_LEVEL,
        #     MageSkills.MANA_SHIELD: SkillsInterface.TIER1_MIN_LEVEL,
        #     MageSkills.DISPEL_MAGIC: SkillsInterface.TIER1_MIN_LEVEL,
            
        #     # Tier 2 (Levels 10-19)
        #     MageSkills.DETECT_MAGIC: SkillsInterface.TIER2_MIN_LEVEL,
        #     MageSkills.IDENTIFY: SkillsInterface.TIER2_MIN_LEVEL,
        #     MageSkills.ARCANE_INTELLECT: SkillsInterface.TIER2_MIN_LEVEL,
        #     MageSkills.BLINK: SkillsInterface.TIER2_MIN_LEVEL,
        #     MageSkills.FROST_NOVA: SkillsInterface.TIER2_MIN_LEVEL
        # },
        # CharacterClassRole.EVOKER: {
        #     # Tier 3 (Levels 20-29)
        #     MageSkills.EVOKER_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.EVOKER_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.EVOKER_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     MageSkills.EVOKER_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     MageSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Mage specialization: Conjurer (Tiers 3-7)
        # CharacterClassRole.CONJURER: {
        #     # Tier 3 (Levels 20-29)
        #     MageSkills.CONJURER_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.CONJURER_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.CONJURER_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     MageSkills.CONJURER_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     MageSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Mage specialization: Enchanter (Tiers 3-7)
        # CharacterClassRole.ENCHANTER: {
        #     # Tier 3 (Levels 20-29)
        #     MageSkills.ENCHANTER_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     MageSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.ENCHANTER_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.ENCHANTER_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     MageSkills.ENCHANTER_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     MageSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     MageSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },



class Skills_Mage(Skills):
    @classmethod
    async def _send_skill_message(cls, actor: Actor, target: Actor, message: str, game_state: 'ComprehensiveGameState'=None):
        """Helper to send a skill message with proper variable processing."""
        if message:
            vars = set_vars(actor, actor, target, message)
            await actor.echo(CommTypes.DYNAMIC, message, vars, game_state=game_state)
    
    @classmethod
    async def _send_skill_message_to_target(cls, actor: Actor, target: Actor, message: str, game_state: 'ComprehensiveGameState'=None):
        """Helper to send a skill message to target with proper variable processing."""
        if message and target:
            vars = set_vars(actor, actor, target, message)
            await target.echo(CommTypes.DYNAMIC, message, vars, game_state=game_state)
    
    @classmethod
    async def _send_skill_message_to_room(cls, actor: Actor, target: Actor, message: str, exceptions: list=None, game_state: 'ComprehensiveGameState'=None):
        """Helper to send a skill message to room with proper variable processing."""
        if message and actor.location_room:
            vars = set_vars(actor, actor, target, message)
            await actor.location_room.echo(CommTypes.DYNAMIC, message, vars, exceptions=exceptions or [], game_state=game_state)
    
    @classmethod
    async def do_spell_fizzle(actor: Actor, target: Actor, spell_name: str, vars: dict=None,
                               game_state: 'ComprehensiveGameState'=None):
        msg = f"Your {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=game_state)
        msg = f"{actor.art_name_cap}'s {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=game_state)

    @classmethod
    async def do_mage_cast_fireball(cls, actor: Actor, target: Actor, 
                                   difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.FIREBALL
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_fireball_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_fireball_finish(cls, actor: Actor, target: Actor, 
                                          difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = MageSkills.FIREBALL
        if not await cls.check_valid_finish(actor, target):
            return False
        FIREBALL_DMG_DICE_LEVEL_MULT = 1/4
        FIREBALL_DMG_DICE_NUM = actor.levels_by_role[CharacterClassRole.MAGE] * FIREBALL_DMG_DICE_LEVEL_MULT
        FIREBALL_DMG_DICE_SIZE = 6
        
        attrib_mod = (actor.attributes[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        FIREBALL_DMG_BONUS = attrib_mod * actor.levels_by_role[CharacterClassRole.MAGE] / 8

        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.FIREBALL],
                              difficulty_modifier - attrib_mod):
            if THIS_SKILL_DATA.save_type:
                save_chance, saved = target.attempt_save(
                    THIS_SKILL_DATA.save_type, actor, THIS_SKILL_DATA,
                    attacker_attribute=CharacterAttributes.INTELLIGENCE)
                if saved:
                    await cls.send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
                    return True
            damage = roll_dice(FIREBALL_DMG_DICE_NUM, FIREBALL_DMG_DICE_SIZE) + FIREBALL_DMG_BONUS
            
            # Send success messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
            
            await CoreActionsInterface.get_instance().trigger_group_aggro(actor, target)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.FIRE)
            
            # Handle area effect - fireball hits others in room
            for c in actor.location_room:
                if c != actor and c != target:
                    msg = f"Your fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits you!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    c.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c], game_state=cls._game_state)
                    await CoreActionsInterface.get_instance().do_calculated_damage(actor, c, damage, DamageType.FIRE)
            
            await Skills.consume_resources(actor, THIS_SKILL_DATA)
            return True
        else:
            # Send failure messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_failure_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_failure_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_failure_room, [actor], cls._game_state)
            return False

    @classmethod
    async def do_mage_cast_magic_missile(cls, actor: Actor, target: Actor, 
                                        difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.MAGIC_MISSILE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            await actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_magic_missile_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            await actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_magic_missile_finish(cls, actor: Actor, target: Actor, 
                                               difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = MageSkills.MAGIC_MISSILE
        if not await cls.check_valid_finish(actor, target):
            return False
        MAGIC_MISSILE_DMG_DICE_LEVEL_MULT = 1/4
        MAGIC_MISSILE_DICE_NUM = int(actor.levels_by_role[CharacterClassRole.MAGE] * MAGIC_MISSILE_DMG_DICE_LEVEL_MULT)
        MAGIC_MISSILE__DMG_DICE_SIZE = 6
        
        attrib_mod = (actor.attributes[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        
        # Get skill level for both success check and damage calculation
        magic_missile_skill = actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.MAGIC_MISSILE]
        skill_level = magic_missile_skill.skill_level
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        
        # Skill determines chance of success
        if Skills.do_skill_check(actor, magic_missile_skill,
                              difficulty_modifier - attrib_mod):
            if THIS_SKILL_DATA.save_type:
                save_chance, saved = target.attempt_save(
                    THIS_SKILL_DATA.save_type, actor, THIS_SKILL_DATA,
                    attacker_attribute=CharacterAttributes.INTELLIGENCE)
                if saved:
                    await cls.send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
                    return True
            # Damage calculation: base dice + attribute bonus + skill bonus + level bonus
            # Keep damage relatively low - skill adds small bonus (skill/20 for low scaling)
            MAGIC_MISSILE_DMG_BONUS = int(attrib_mod * actor.levels_by_role[CharacterClassRole.MAGE] / 4)
            MAGIC_MISSILE_SKILL_DMG_BONUS = int(skill_level / 20)  # Small skill-based damage bonus
            MAGIC_MISSILE_LEVEL_DMG_BONUS = int(actor.levels_by_role[CharacterClassRole.MAGE] / 8)  # Level-based bonus
            
            damage = roll_dice(MAGIC_MISSILE_DICE_NUM, MAGIC_MISSILE__DMG_DICE_SIZE) + MAGIC_MISSILE_DMG_BONUS + MAGIC_MISSILE_SKILL_DMG_BONUS + MAGIC_MISSILE_LEVEL_DMG_BONUS
            
            # Send success messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
            
            await CoreActionsInterface.get_instance().trigger_group_aggro(actor, target)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.ARCANE)
            
            await Skills.consume_resources(actor, THIS_SKILL_DATA)
            return True
        else:
            # Send failure messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_failure_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_failure_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_failure_room, [actor], cls._game_state)
            return False

    @classmethod
    async def do_mage_cast_light(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting light is not yet implemented!", cls._game_state)
        pass

    @classmethod
    async def do_mage_cast_arcane_barrier(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.ARCANE_BARRIER
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_arcane_barrier_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_arcane_barrier_finish(cls, actor: Actor, target: Actor, 
                                               difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = MageSkills.ARCANE_BARRIER
        if not await cls.check_valid_finish(actor, target):
            return False
        DAMAGE_REDUCTION_AMOUNT = actor.levels_by_role[CharacterClassRole.MAGE]
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.ARCANE_BARRIER],
                              difficulty_modifier):
            # Send success messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
            
            reductions = DamageReduction(reductions_by_type={
                DamageType.BLUDGEONING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.PIERCING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.SLASHING: DAMAGE_REDUCTION_AMOUNT
            })
            new_state = CharacterStateShielded(target, actor, "magic barrier", multipliers=None, reductions=reductions,
                                               tick_created=game_tick)
            await new_state.apply_state(game_tick, THIS_SKILL_DATA.duration_min_ticks)
            
            await Skills.consume_resources(actor, THIS_SKILL_DATA)
            return True
        else:
            # Send failure messages from skill definition
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_failure_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_failure_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_failure_room, [actor], cls._game_state)
            return False

    @classmethod
    async def do_mage_cast_sleep(cls, actor: Actor, target: Actor, 
                                difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting sleep is not yet implemented!", cls._game_state)

    @classmethod
    async def do_mage_cast_shield(cls, actor: Actor, target: Actor, 
                                 difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast shield on self or target, granting damage multipliers."""
        THIS_SKILL_DATA = MageSkills.SHIELD
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        
        # Default to self if no target
        if target is None:
            target = actor
            
        continue_func = lambda: cls.do_mage_cast_shield_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_shield_finish(cls, actor: Actor, target: Actor, 
                                        difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the shield spell, applying damage multipliers."""
        from .nondb_models.attacks_and_damage import DamageMultipliers
        
        THIS_SKILL_DATA = MageSkills.SHIELD
        if not await cls.check_valid_finish(actor, target):
            return False
        SHIELD_RESIST_BASE = 10  # Base multiplier value for shield (note: value may need adjustment to 0-2 range)
        SHIELD_RESIST_PER_LEVEL = 0.5
        
        # Calculate multiplier based on caster's mage level
        mage_level = actor.levels_by_role.get(CharacterClassRole.MAGE, 1)
        multiplier_value = int(SHIELD_RESIST_BASE + (mage_level * SHIELD_RESIST_PER_LEVEL))
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.cooldown_ticks)

        # Send success messages from skill definition
        if target == actor:
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor], cls._game_state)
        else:
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
        
        # Create multiplier profile for all damage types
        multipliers = DamageMultipliers()
        for dt in DamageType:
            multipliers.set(dt, multiplier_value)
        
        new_state = CharacterStateShielded(target, cls._game_state, actor, "arcane shield", 
                                          multipliers=multipliers, tick_created=game_tick)
        await new_state.apply_state(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.duration_min_ticks)
        
        # Consume mana
        await Skills.consume_resources(actor, THIS_SKILL_DATA)
        return True

    @classmethod
    async def do_mage_cast_blur(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast blur on self or target, granting a dodge bonus."""
        THIS_SKILL_DATA = MageSkills.BLUR
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        
        # Default to self if no target
        if target is None:
            target = actor
            
        continue_func = lambda: cls.do_mage_cast_blur_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_blur_finish(cls, actor: Actor, target: Actor, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the blur spell, applying the dodge bonus."""
        THIS_SKILL_DATA = MageSkills.BLUR
        if not await cls.check_valid_finish(actor, target):
            return False
        BLUR_DODGE_BONUS_BASE = 10
        BLUR_DODGE_BONUS_PER_LEVEL = 0.5
        
        # Calculate dodge bonus based on caster's mage level
        mage_level = actor.levels_by_role.get(CharacterClassRole.MAGE, 1)
        dodge_bonus = int(BLUR_DODGE_BONUS_BASE + (mage_level * BLUR_DODGE_BONUS_PER_LEVEL))
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.cooldown_ticks)

        # Send success messages from skill definition
        if target == actor:
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor], cls._game_state)
        else:
            await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
            await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
            await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
        
        new_state = CharacterStateDodgeBonus(target, cls._game_state, actor, "blurred", 
                                             affect_amount=dodge_bonus, tick_created=game_tick)
        await new_state.apply_state(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.duration_min_ticks)
        
        # Consume mana
        await Skills.consume_resources(actor, THIS_SKILL_DATA)
        return True

    @classmethod
    async def do_mage_cast_mana_burn(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast mana burn on target, draining their mana and dealing damage based on mana drained."""
        THIS_SKILL_DATA = MageSkills.MANA_BURN
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        
        if target is None:
            msg = "Who do you want to burn the mana of?"
            actor.echo(CommTypes.DYNAMIC, msg, {}, game_state=cls._game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_mana_burn_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_mana_burn_finish(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the mana burn spell, draining mana and dealing damage."""
        THIS_SKILL_DATA = MageSkills.MANA_BURN
        if not await cls.check_valid_finish(actor, target):
            return False
        MANA_BURN_BASE = 10
        MANA_BURN_PER_LEVEL = 2
        MANA_BURN_DAMAGE_MULTIPLIER = 0.5  # Damage = mana_drained * multiplier
        
        # Calculate mana to drain based on caster's mage level
        mage_level = actor.levels_by_role.get(CharacterClassRole.MAGE, 1)
        mana_drain = int(MANA_BURN_BASE + (mage_level * MANA_BURN_PER_LEVEL))
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.cooldown_ticks)

        # Check if target has mana
        if not hasattr(target, 'current_mana') or target.max_mana <= 0:
            msg = f"{target.art_name_cap} has no magical energy to burn!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            await Skills.consume_resources(actor, THIS_SKILL_DATA)
            return False
        
        if THIS_SKILL_DATA.save_type:
            save_chance, saved = target.attempt_save(
                THIS_SKILL_DATA.save_type, actor, THIS_SKILL_DATA,
                attacker_attribute=CharacterAttributes.INTELLIGENCE)
            if saved:
                await cls.send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
                return True
        
        # Calculate actual mana drained (can't drain more than they have)
        actual_mana_drained = target.decrease_mana(mana_drain)
        
        # Calculate damage based on mana drained
        damage = int(actual_mana_drained * MANA_BURN_DAMAGE_MULTIPLIER)
        
        # Send success messages from skill definition
        await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
        await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
        await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)
        
        # Trigger group aggro
        await CoreActionsInterface.get_instance().trigger_group_aggro(actor, target)
        
        # Deal damage if any mana was drained
        if damage > 0:
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.ARCANE)
        
        # Consume mana
        await Skills.consume_resources(actor, THIS_SKILL_DATA)
        return True

    @classmethod
    async def do_mage_cast_ignite(cls, actor: Actor, target: Actor, 
                                 difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast ignite on target, dealing fire damage over time."""
        THIS_SKILL_DATA = MageSkills.IGNITE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        
        if target is None:
            msg = "Who do you want to set on fire?"
            actor.echo(CommTypes.DYNAMIC, msg, {}, game_state=cls._game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_ignite_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_ignite_finish(cls, actor: Actor, target: Actor, 
                                        difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the ignite spell, applying burning damage over time."""
        THIS_SKILL_DATA = MageSkills.IGNITE
        if not await cls.check_valid_finish(actor, target):
            return False
        IGNITE_DAMAGE_BASE = 3
        IGNITE_DAMAGE_PER_LEVEL = 0.5
        IGNITE_PULSE_TICKS = ticks_from_seconds(3)  # Damage every 3 seconds
        
        # Calculate damage per tick based on caster's mage level
        mage_level = actor.levels_by_role.get(CharacterClassRole.MAGE, 1)
        damage_per_tick = int(IGNITE_DAMAGE_BASE + (mage_level * IGNITE_DAMAGE_PER_LEVEL))
        
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": THIS_SKILL_DATA.cooldown_ticks})
        await cooldown.start(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.cooldown_ticks)

        if THIS_SKILL_DATA.save_type:
            save_chance, saved = target.attempt_save(
                THIS_SKILL_DATA.save_type, actor, THIS_SKILL_DATA,
                attacker_attribute=CharacterAttributes.INTELLIGENCE)
            if saved:
                await cls.send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
                return True

        # Send success messages from skill definition
        await cls._send_skill_message(actor, target, THIS_SKILL_DATA.message_success_subject, cls._game_state)
        await cls._send_skill_message_to_target(actor, target, THIS_SKILL_DATA.message_success_target, cls._game_state)
        await cls._send_skill_message_to_room(actor, target, THIS_SKILL_DATA.message_success_room, [actor, target], cls._game_state)

        # Apply the ignite effect
        new_state = CharacterStateIgnited(target, cls._game_state, actor, "ignited", 
                                         damage_amount=damage_per_tick, tick_created=game_tick)
        await new_state.apply_state(game_tick or cls._game_state.get_current_tick(), THIS_SKILL_DATA.duration_min_ticks,
                             pulse_period_ticks=IGNITE_PULSE_TICKS)
        
        # Consume mana
        await Skills.consume_resources(actor, THIS_SKILL_DATA)
        return True

    @classmethod
    async def do_mage_cast_animate_dead(cls, actor: Actor, target: Actor, 
                                       difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast animate dead on a corpse in the room, raising it as a zombie."""
        THIS_SKILL_DATA = MageSkills.ANIMATE_DEAD
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            return False
        
        # Find an NPC corpse in the room
        corpse = None
        for obj in actor.location_room.contents:
            if isinstance(obj, Corpse) and obj.owner_id is None:  # NPC corpse only
                corpse = obj
                break
        
        if corpse is None:
            msg = "There is no corpse here to animate!"
            actor.echo(CommTypes.DYNAMIC, msg, {}, game_state=cls._game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_animate_dead_finish(actor, corpse, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls._game_state.get_current_tick()) + actor.recovery_ticks
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, None, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, game_state=cls._game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_animate_dead_finish(cls, actor: Actor, corpse: Corpse, 
                                              difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the animate dead spell, raising the corpse as a zombie."""
        from .comprehensive_game_state_interface import GameStateInterface
        
        if not await cls.check_valid_finish(actor, corpse):
            return False
        ANIMATE_DEAD_COOLDOWN_TICKS = ticks_from_seconds(120)  # 2 minute cooldown
        
        cooldown = Cooldown(actor, "animate_dead", cls._game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": ANIMATE_DEAD_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls._game_state.get_current_tick(), ANIMATE_DEAD_COOLDOWN_TICKS)

        # Get skill level for both success check and duration calculation
        animate_dead_skill = actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.ANIMATE_DEAD]
        
        THIS_SKILL_DATA = MageSkills.ANIMATE_DEAD
        
        # Skill determines chance of success
        if not cls.do_skill_check(actor, animate_dead_skill, difficulty_modifier):
            # Send failure messages from skill definition
            await cls._send_skill_message(actor, None, THIS_SKILL_DATA.message_failure_subject, cls._game_state)
            await cls._send_skill_message_to_room(actor, None, THIS_SKILL_DATA.message_failure_room, [actor], cls._game_state)
            await Skills.consume_resources(actor, THIS_SKILL_DATA)
            return False

        # Get the original character definition
        original_id = corpse.original_id
        char_def = cls._game_state.world_definition.characters.get(original_id)
        
        if not char_def:
            msg = "The dark magic fails - the spirit has fled too far!"
            vars = set_vars(actor, actor, None, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls._game_state)
            await Skills.consume_resources(actor, MageSkills.ANIMATE_DEAD)
            return False
        
        # Create the zombie from the definition
        zombie = Character.create_from_definition(char_def, cls._game_state, include_items=False)
        
        # Store original name for the zombie name
        original_name = corpse.character.name if hasattr(corpse, 'character') and corpse.character else char_def.name
        
        # Store original level (before halving) for duration calculation
        # Get the highest level from the zombie's classes (primary class level)
        original_zombie_level = max(zombie.levels_by_role.values()) if zombie.levels_by_role else 1
        caster_level = actor.levels_by_role.get(CharacterClassRole.MAGE, 1)
        
        # Modify the zombie - half strength
        # Halve all levels
        for role in zombie.levels_by_role:
            zombie.levels_by_role[role] = max(1, zombie.levels_by_role[role] // 2)
        
        # Recalculate level-based stats
        zombie._update_class_features()
        
        # Halve HP
        zombie.max_hit_points = max(1, zombie.max_hit_points // 2)
        zombie.set_hp_to_max()
        
        # Halve damage on natural attacks
        for attack in zombie.natural_attacks:
            for potential_damage in attack.potential_damage_:
                potential_damage.damage_dice_number = max(1, potential_damage.damage_dice_number // 2)
                potential_damage.damage_dice_bonus = potential_damage.damage_dice_bonus // 2
        
        # Reduce combat stats
        zombie.hit_modifier = zombie.hit_modifier // 2
        zombie.dodge_modifier = zombie.dodge_modifier // 2
        
        # Change the name to "a <name> zombie"
        zombie.name = f"{original_name} zombie"
        zombie.article = "a"
        zombie.description_ = f"A shambling undead {original_name}, animated by dark magic. Its eyes glow with unholy light."
        
        # Make it friendly to the caster (so it doesn't attack them)
        # Set the zombie to follow/fight for the caster
        zombie.permanent_character_flags = zombie.permanent_character_flags.add_flags(
            PermanentCharacterFlags.IS_FRIENDLY
        )
        zombie.group_id = actor.group_id or actor.id  # Same group as caster
        
        # Transfer all items from the corpse to the zombie's inventory
        for obj in corpse.contents[:]:
            corpse.remove_object(obj)
            zombie.add_object(obj)
        
        # Remove the corpse from the room
        room = actor.location_room
        room.remove_object(corpse)
        corpse.is_deleted = True
        
        # Add the zombie to the room
        room.add_character(zombie)
        zombie.location_room = room
        cls._game_state.characters.append(zombie)
        
        # Calculate duration based on skill level and level difference
        # Base duration: 5 minutes
        BASE_DURATION_SECONDS = 300
        skill_level = animate_dead_skill.skill_level
        
        # Skill modifier: +1 second per skill level (max +100 seconds at skill 100)
        skill_duration_bonus = skill_level
        
        # Level difference modifier: 
        # Same level = standard (1.0x)
        # Higher caster vs lower NPC = longer duration
        # Lower caster vs higher NPC = shorter duration
        level_diff = caster_level - original_zombie_level
        if level_diff >= 0:
            # Caster is same or higher level - bonus duration
            level_modifier = 1.0 + (level_diff * 0.1)  # +10% per level above
        else:
            # Caster is lower level - reduced duration
            level_modifier = max(0.5, 1.0 + (level_diff * 0.05))  # -5% per level below, min 50%
        
        # Calculate final duration
        duration_seconds = int((BASE_DURATION_SECONDS + skill_duration_bonus) * level_modifier)
        CHARM_DURATION_TICKS = ticks_from_seconds(duration_seconds)
        
        # Apply the charmed state - zombie is controlled by caster
        charmed_state = CharacterStateCharmed(zombie, cls._game_state, actor, "charmed", 
                                              tick_created=game_tick)
        await charmed_state.apply_state(game_tick or cls._game_state.get_current_tick(), CHARM_DURATION_TICKS)
        
        # Send success messages from skill definition
        THIS_SKILL_DATA = MageSkills.ANIMATE_DEAD
        await cls._send_skill_message(actor, zombie, THIS_SKILL_DATA.message_success_subject, cls._game_state)
        await cls._send_skill_message_to_room(actor, zombie, THIS_SKILL_DATA.message_success_room, [actor], cls._game_state)
        
        # Consume mana
        await Skills.consume_resources(actor, THIS_SKILL_DATA)
        return True


class MageSkills(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["magic missile", "shield", "detect magic", "light", "blur", "ignite"]
        tier2_skills = ["fireball", "ice bolt", "arcane armor", "invisibility", "arcane barrier", "mana burn", "animate dead"]
        tier3_skills = ["lightning bolt", "teleport", "polymorph"]
        tier4_skills = ["meteor swarm", "time stop"]
        
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
    
    # Fireball - area damage spell
    FIREBALL = Skill(
        name="fireball",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="fireball",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=25,
        message_prepare="You begin gathering fire energy...",
        message_success_subject="You cast a fireball at %t%!",
        message_success_target="$cap(%a%) casts a fireball at you!",
        message_success_room="$cap(%a%) casts a fireball at %t%!",
        message_failure_subject="Your fireball spell fizzles!",
        message_failure_target="$cap(%a%)'s fireball spell fizzles!",
        message_failure_room="$cap(%a%)'s fireball spell fizzles!",
        message_apply_subject="Your fireball strikes %t%!",
        message_apply_target="$cap(%a%)'s fireball strikes you!",
        message_apply_room="$cap(%a%)'s fireball strikes %t%!",
        message_resist_subject="%t% resists your fireball!",
        message_resist_target="You resist $cap(%a%)'s fireball!",
        message_resist_room="%t% resists $cap(%a%)'s fireball!",
        save_type="reflex",
        save_difficulty=0,
        skill_function="do_mage_cast_fireball",
        ai_priority=60,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=True
    )
    
    # Arcane Barrier - defensive spell
    ARCANE_BARRIER = Skill(
        name="arcane barrier",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="arcane_barrier",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(120),  # 2 minutes
        duration_max_ticks=ticks_from_seconds(120),
        mana_cost=25,
        message_prepare="You begin weaving protective arcane energy...",
        message_success_subject="You cast arcane barrier on yourself!",
        message_success_target="$cap(%a%) casts arcane barrier on you! You feel shielded!",
        message_success_room="$cap(%a%) casts arcane barrier on %t%!",
        message_failure_subject="Your arcane barrier spell fizzles!",
        message_failure_target="$cap(%a%)'s arcane barrier spell fizzles!",
        message_failure_room="$cap(%a%)'s arcane barrier spell fizzles!",
        message_apply_subject="An arcane barrier protects you from harm!",
        message_apply_target="An arcane barrier protects you from harm!",
        message_apply_room="An arcane barrier protects $cap(%a%) from harm!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_mage_cast_arcane_barrier",
        ai_priority=60,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Basic attack spell
    MAGIC_MISSILE = Skill(
        name="magic missile",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="magic_missile",
        cooldown_ticks=ticks_from_seconds(10),
        cast_time_ticks=ticks_from_seconds(1),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=8,
        message_prepare="You begin to channel arcane energy...",
        message_success_subject="Arcane bolts form at your fingertips!",
        message_success_target="$cap(%a%) forms arcane bolts at %Q% fingertips!",
        message_success_room="$cap(%a%) forms arcane bolts at %Q% fingertips!",
        message_failure_subject="Your spell fizzles!",
        message_failure_target="$cap(%a%)'s spell fizzles!",
        message_failure_room="$cap(%a%)'s spell fizzles!",
        message_apply_subject="Your magic missiles strike %t%!",
        message_apply_target="$cap(%a%)'s magic missiles strike you!",
        message_apply_room="$cap(%a%)'s magic missiles strike %t%!",
        message_resist_subject="%t% resists your magic missiles!",
        message_resist_target="You resist $cap(%a%)'s magic missiles!",
        message_resist_room="%t% resists $cap(%a%)'s magic missiles!",
        save_type="reflex",
        save_difficulty=-10,
        skill_function="do_mage_cast_magic_missile",
        ai_priority=50,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=True
    )
    
    # Defensive spell
    SHIELD = Skill(
        name="shield",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="shield",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(120),  # 2 minutes
        duration_max_ticks=ticks_from_seconds(120),
        mana_cost=20,
        message_prepare="You begin to weave protective magic...",
        message_success_subject="A shimmering arcane shield forms around you!",
        message_success_target="$cap(%a%) casts shield on you!",
        message_success_room="A shimmering arcane shield forms around $cap(%a%)!",
        message_failure_subject="Your shield spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s shield spell fizzles!",
        message_apply_subject="An arcane shield protects you from harm!",
        message_apply_target="An arcane shield protects you from harm!",
        message_apply_room="An arcane shield protects $cap(%a%) from harm!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_mage_cast_shield",
        ai_priority=60,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Utility spell
    DETECT_MAGIC = Skill(
        name="detect magic",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="detect_magic",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(300),  # 5 minutes
        duration_max_ticks=ticks_from_seconds(300),
        message_prepare="You attune your senses to magical energies...",
        message_success_subject="Your senses become attuned to magical energies!",
        message_success_target=None,
        message_success_room="$cap(%a%)'s eyes glow with arcane insight!",
        message_failure_subject="Your detect magic spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s detect magic spell fizzles!",
        message_apply_subject="You can now sense magical auras!",
        message_apply_target=None,
        message_apply_room="$cap(%a%) seems to perceive things others cannot!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )
    
    # Illumination spell
    LIGHT = Skill(
        name="light",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="light",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(300),  # 5 minutes
        duration_max_ticks=ticks_from_seconds(300),
        message_prepare="You begin to conjure magical light...",
        message_success_subject="You conjure a floating orb of light!",
        message_success_target=None,
        message_success_room="$cap(%a%) conjures a floating orb of light!",
        message_failure_subject="Your light spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s light spell fizzles!",
        message_apply_subject="An orb of magical light hovers near you!",
        message_apply_target=None,
        message_apply_room="An orb of magical light hovers near $cap(%a%)!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )
    
    # Blur - defensive spell that increases dodge
    BLUR = Skill(
        name="blur",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="blur",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(120),  # 2 minutes
        duration_max_ticks=ticks_from_seconds(120),
        mana_cost=15,
        message_prepare="You weave illusory magic around yourself...",
        message_success_subject="Your form becomes blurred and indistinct!",
        message_success_target="$cap(%a%) casts blur on you! Your form becomes indistinct!",
        message_success_room="$cap(%a%)'s form becomes blurred and indistinct!",
        message_failure_subject="Your blur spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s blur spell fizzles!",
        message_apply_subject="You are harder to hit while blurred!",
        message_apply_target="You are harder to hit while blurred!",
        message_apply_room=None,
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_mage_cast_blur",
        ai_priority=60,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Mana Burn - drain enemy mana and deal damage based on mana drained
    MANA_BURN = Skill(
        name="mana burn",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="mana_burn",
        cooldown_ticks=ticks_from_seconds(15),
        cast_time_ticks=ticks_from_seconds(1.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=20,
        message_prepare="You reach out to siphon your enemy's magical energy...",
        message_success_subject="You burn $cap(%t%)'s magical reserves!",
        message_success_target="$cap(%a%) burns your magical reserves!",
        message_success_room="$cap(%a%) burns $cap(%t%)'s magical reserves!",
        message_failure_subject="Your mana burn fizzles!",
        message_failure_target="$cap(%a%)'s mana burn fizzles!",
        message_failure_room="$cap(%a%)'s mana burn fizzles!",
        message_apply_subject="You drain mana from %t% and convert it to damage!",
        message_apply_target="$cap(%a%) drains your mana and converts it to damage!",
        message_apply_room="$cap(%a%) drains mana from %t%!",
        message_resist_subject="%t% resists your mana burn!",
        message_resist_target="You resist $cap(%a%)'s mana burn!",
        message_resist_room="%t% resists $cap(%a%)'s mana burn!",
        save_type="will",
        save_difficulty=5,
        skill_function="do_mage_cast_mana_burn",
        ai_priority=55,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=True
    )
    
    # Ignite - fire damage over time
    IGNITE = Skill(
        name="ignite",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="ignite",
        cooldown_ticks=ticks_from_seconds(10),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(12),
        duration_max_ticks=ticks_from_seconds(12),
        mana_cost=12,
        message_prepare="You conjure flames to engulf your enemy...",
        message_success_subject="You set %t% ablaze!",
        message_success_target="$cap(%a%) sets you ablaze!",
        message_success_room="$cap(%a%) sets %t% ablaze!",
        message_failure_subject="Your ignite spell fizzles!",
        message_failure_target="$cap(%a%)'s ignite spell fizzles!",
        message_failure_room="$cap(%a%)'s ignite spell fizzles!",
        message_apply_subject="%t% burns!",
        message_apply_target="You burn!",
        message_apply_room="%t% burns!",
        message_resist_subject="%t% resists your flames!",
        message_resist_target="You resist $cap(%a%)'s flames!",
        message_resist_room="%t% resists $cap(%a%)'s flames!",
        save_type="reflex",
        save_difficulty=0,
        skill_function="do_mage_cast_ignite",
        ai_priority=60,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DOT,
        requires_target=True
    )
    
    # Animate Dead - raise a corpse as a zombie minion
    ANIMATE_DEAD = Skill(
        name="animate dead",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="animate_dead",
        cooldown_ticks=ticks_from_seconds(120),
        cast_time_ticks=ticks_from_seconds(4.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=40,
        message_prepare="You begin channeling dark necromantic energy into the corpse...",
        message_success_subject="Dark energy swirls as you raise the dead!",
        message_success_target=None,
        message_success_room="$cap(%a%) channels dark energy into a corpse!",
        message_failure_subject="The corpse refuses to rise!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s dark magic fails!",
        message_apply_subject="The corpse rises as your undead servant!",
        message_apply_target=None,
        message_apply_room="A corpse rises as an undead servant!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_mage_cast_animate_dead",
        ai_priority=40,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.UTILITY,
        requires_target=False
    ) 


SkillsRegistry.register_skill_class("mage", {
    attr_name.lower(): getattr(Skills_Mage, attr_name)
    for attr_name in dir(Skills_Mage)
    if not attr_name.startswith('_') and isinstance(getattr(Skills_Mage, attr_name), Skill)
})