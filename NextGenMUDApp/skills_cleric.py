from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill
from .skills_interface import Skill
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBleeding, CharacterStateHitBonus
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, firstcap
import random

        # CharacterClassRole.CLERIC: {
        #     # Tier 1 (Levels 1-9)
        #     ClericSkills.CURE_LIGHT_WOUNDS: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.BLESS: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.DIVINE_FAVOR: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.RADIANT_LIGHT: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.SANCTUARY: SkillsInterface.TIER1_MIN_LEVEL,
            
        #     # Tier 2 (Levels 10-19)
        #     ClericSkills.CURE_MODERATE_WOUNDS: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.REMOVE_CURSE: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.DIVINE_PROTECTION: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.SMITE: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.DIVINE_GUIDANCE: SkillsInterface.TIER2_MIN_LEVEL
        # },
        # CharacterClassRole.WARPRIEST: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Cleric specialization: Restorer (Tiers 3-7)
        # CharacterClassRole.RESTORER: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Cleric specialization: Ritualist (Tiers 3-7)
        # CharacterClassRole.RITUALIST: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # }



class Skills_Cleric(Skills):
    @classmethod
    async def do_cleric_cure_light_wounds(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure light wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_serious_wounds(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure serious wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_critical_wounds(cls, actor: Actor, target: Actor, 
                                            difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure critical wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_heal(cls, actor: Actor, target: Actor, 
                            difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Heal is not yet implemented!", cls.game_state)
        return False


class ClericSkills(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["heal", "light", "cure poison", "bless"]
        tier2_skills = ["mass heal", "divine protection", "smite", "holy shield"]
        tier3_skills = ["resurrection", "divine intervention"]
        tier4_skills = ["miracle"]
        
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
    
    # Basic healing spell
    HEAL = Skill(
        name="heal",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="heal",
        cooldown_ticks=ticks_from_seconds(5),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You begin to channel divine energy...",
        message_success_subject="Divine light flows through your hands!",
        message_success_target="$cap(%a%) channels divine light toward you!",
        message_success_room="$cap(%a%) channels divine light toward %t%!",
        message_failure_subject="Your healing spell fizzles!",
        message_failure_target="$cap(%a%)'s healing spell fizzles!",
        message_failure_room="$cap(%a%)'s healing spell fizzles!",
        message_apply_subject="Your divine power heals %t%!",
        message_apply_target="$cap(%a%)'s divine power heals you!",
        message_apply_room="$cap(%a%)'s divine power heals %t%!",
        message_resist_subject="%t% resists your healing spell!",
        message_resist_target="You resist $cap(%a%)'s healing spell!",
        message_resist_room="%t% resists $cap(%a%)'s healing spell!",
        skill_function=None  # Will be implemented later
    )
    
    # Create light
    LIGHT = Skill(
        name="light",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="light",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(300),  # 5 minutes
        duration_max_ticks=ticks_from_seconds(300),
        message_prepare="You begin to summon divine light...",
        message_success_subject="You summon a globe of divine light!",
        message_success_target=None,
        message_success_room="$cap(%a%) summons a globe of divine light!",
        message_failure_subject="Your light spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s light spell fizzles!",
        message_apply_subject="A glowing orb of light follows you!",
        message_apply_target=None,
        message_apply_room="A glowing orb of light follows $cap(%a%)!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )
    
    # Cure poison
    CURE_POISON = Skill(
        name="cure poison",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="cure_poison",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You channel cleansing energy...",
        message_success_subject="Cleansing energy flows through your hands!",
        message_success_target="$cap(%a%) channels cleansing energy toward you!",
        message_success_room="$cap(%a%) channels cleansing energy toward %t%!",
        message_failure_subject="Your cure poison spell fizzles!",
        message_failure_target="$cap(%a%)'s cure poison spell fizzles!",
        message_failure_room="$cap(%a%)'s cure poison spell fizzles!",
        message_apply_subject="Your cleansing power purges poison from %t%!",
        message_apply_target="$cap(%a%)'s cleansing power purges poison from you!",
        message_apply_room="$cap(%a%)'s cleansing power purges poison from %t%!",
        message_resist_subject="%t% is too heavily poisoned for your spell!",
        message_resist_target="You are too heavily poisoned for $cap(%a%)'s spell!",
        message_resist_room="%t% is too heavily poisoned for $cap(%a%)'s spell!",
        skill_function=None  # Will be implemented later
    )
    
    # Bless
    BLESS = Skill(
        name="bless",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="bless",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(120),  # 2 minutes
        duration_max_ticks=ticks_from_seconds(120),
        message_prepare="You call upon divine blessings...",
        message_success_subject="Divine favor surrounds you!",
        message_success_target="$cap(%a%) calls upon divine blessings for you!",
        message_success_room="$cap(%a%) calls upon divine blessings for %t%!",
        message_failure_subject="Your blessing fades quickly!",
        message_failure_target="$cap(%a%)'s blessing for you fades quickly!",
        message_failure_room="$cap(%a%)'s blessing for %t% fades quickly!",
        message_apply_subject="You bestow divine blessings upon %t%!",
        message_apply_target="$cap(%a%) bestows divine blessings upon you!",
        message_apply_room="$cap(%a%) bestows divine blessings upon %t%!",
        message_resist_subject="%t% resists your divine blessing!",
        message_resist_target="You resist $cap(%a%)'s divine blessing!",
        message_resist_room="%t% resists $cap(%a%)'s divine blessing!",
        skill_function=None  # Will be implemented later
    ) 