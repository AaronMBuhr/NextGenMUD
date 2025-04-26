from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill
from .skills_interface import Skill
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBleeding, CharacterStateHitBonus, Cooldown
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances
from .nondb_models.characters import CharacterSkill
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
    async def do_spell_fizzle(actor: Actor, target: Actor, spell_name: str, vars: dict=None,
                               game_state: 'ComprehensiveGameState'=None):
        msg = f"Your {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, game_state)
        msg = f"{actor.art_name_cap}'s {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=game_state)

    @classmethod
    async def do_mage_cast_fireball(cls, actor: Actor, target: Actor, 
                                   difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.FIREBALL
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_fireball_finish(actor, target, difficulty_modifier, game_tick)
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
    async def do_mage_cast_fireball_finish(cls, actor: Actor, target: Actor, 
                                          difficulty_modifier=0, game_tick=0) -> bool:
        FIREBALL_DMG_DICE_LEVEL_MULT = 1/4
        FIREBALL_DMG_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * FIREBALL_DMG_DICE_LEVEL_MULT
        FIREBALL_DMG_DICE_SIZE = 6
        FIREBALL_COOLDOWN_TICKS = ticks_from_seconds(30)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        FIREBALL_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 8

        cooldown = Cooldown(actor, "fireball", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": FIREBALL_COOLDOWN_TICKS})
        await cooldown.start(game_tick, FIREBALL_COOLDOWN_TICKS)

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_FIREBALL],
                              difficulty_modifier - attrib_mod):
            damage = roll_dice(FIREBALL_DMG_DICE_NUM, FIREBALL_DMG_DICE_SIZE) + FIREBALL_DMG_BONUS
            msg = f"You cast a fireball at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a fireball at you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a fireball at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.FIRE)
            for c in actor.location_room:
                if c != actor and c != target:
                    msg = f"Your fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits you!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    c.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c], game_state=cls.game_state)
                    await CoreActionsInterface.get_instance().do_calculated_damage(actor, c, damage, DamageType.FIRE)
            return True
        else:
            await cls.do_spell_fizzle(actor, target, "fireball", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_magic_missile(cls, actor: Actor, target: Actor, 
                                        difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.MAGIC_MISSILE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_magic_missile_finish(actor, target, difficulty_modifier, game_tick)
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
    async def do_mage_cast_magic_missile_finish(cls, actor: Actor, target: Actor, 
                                               difficulty_modifier=0, game_tick=0) -> bool:
        MAGIC_MISSILE_DMG_DICE_LEVEL_MULT = 1/4
        MAGIC_MISSILE_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * MAGIC_MISSILE_DMG_DICE_LEVEL_MULT
        MAGIC_MISSILE__DMG_DICE_SIZE = 6
        MAGIC_MISSILE_COOLDOWN_TICKS = ticks_from_seconds(10)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        MAGIC_MISSILE_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 4

        cooldown = Cooldown(actor, "magic_missile", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": MAGIC_MISSILE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, MAGIC_MISSILE_COOLDOWN_TICKS)

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_FIREBALL],
                              difficulty_modifier - attrib_mod):
            damage = roll_dice(MAGIC_MISSILE_DICE_NUM, MAGIC_MISSILE__DMG_DICE_SIZE) + MAGIC_MISSILE_DMG_BONUS
            msg = f"You cast a magic missile at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a magic missile at you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a magic missile at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.ARCANE)
            return True
        else:
            await cls.do_spell_fizzle(actor, target, "magic missile", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_light(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting light is not yet implemented!", cls.game_state)
        pass

    @classmethod
    async def do_mage_cast_arcane_barrier(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = MageSkills.ARCANE_BARRIER
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_mage_cast_arcane_barrier_finish(actor, target, difficulty_modifier, game_tick)
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
    async def do_mage_cast_arcane_barrier_finish(cls, actor: Actor, target: Actor, 
                                               difficulty_modifier=0, game_tick=0) -> bool:
        DAMAGE_REDUCTION_AMOUNT = actor.levels_[CharacterClassRole.MAGE]
        ARCANE_BARRIER_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        cooldown = Cooldown(actor, "arcane_barrier", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": ARCANE_BARRIER_COOLDOWN_TICKS})
        await cooldown.start(game_tick, ARCANE_BARRIER_COOLDOWN_TICKS)
        
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_ARCANE_BARRIER],
                              difficulty_modifier):
            msg = f"You cast arcane barrier on yourself!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts arcane barrier on you! You feel shielded!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts arcane barrier on {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
            reductions = DamageReduction(reductions_by_type={
                DamageType.BLUDGEONING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.PIERCING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.SLASHING: DAMAGE_REDUCTION_AMOUNT
            })
            new_state = CharacterStateShielded(target, actor, "magic barrier", resistances=None, reductions=reductions,
                                               tick_created=game_tick)
            new_state.apply_state(game_tick, 0)
            return True
        else:
            await cls.do_spell_fizzle(actor, target, "arcane barrier", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_sleep(cls, actor: Actor, target: Actor, 
                                difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting sleep is not yet implemented!", cls.game_state) 


class MageSkills(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["magic missile", "shield", "detect magic", "light"]
        tier2_skills = ["fireball", "ice bolt", "arcane armor", "invisibility"]
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
    
    # Basic attack spell
    MAGIC_MISSILE = Skill(
        name="magic missile",
        base_class=CharacterClassRole.MAGE,
        cooldown_name="magic_missile",
        cooldown_ticks=ticks_from_seconds(3),
        cast_time_ticks=ticks_from_seconds(1.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
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
        skill_function=None  # Will be implemented later
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
        message_prepare="You begin to weave protective magic...",
        message_success_subject="A shimmering arcane shield forms around you!",
        message_success_target=None,
        message_success_room="A shimmering arcane shield forms around $cap(%a%)!",
        message_failure_subject="Your shield spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s shield spell fizzles!",
        message_apply_subject="An arcane shield protects you from harm!",
        message_apply_target=None,
        message_apply_room="An arcane shield protects $cap(%a%) from harm!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
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