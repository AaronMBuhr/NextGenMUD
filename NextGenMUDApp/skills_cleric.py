from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills
from .skills_interface import Skill
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes

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