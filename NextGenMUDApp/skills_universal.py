"""
Universal skills available to all characters regardless of class.
These include saving throw skills used in the opposed check system.
"""
from .skills_core import SkillsRegistry, Skill, SkillType


class Skills_Universal:
    """
    Universal skills available to all characters.
    
    Save skills (Fortitude, Reflex, Will) are passive skills that determine
    resistance to various effects. They are used in opposed saving throw checks:
    
    SaveChance = clamp(50 + (Defender_Save - Attacker_Penetration) + mods, 5, 95)
    
    Where Defender_Save = Save_Skill + (Attribute × ATTRIBUTE_SAVE_MODIFIER)
    
    Attribute mappings:
        Fortitude -> Constitution (physical resilience)
        Reflex -> Dexterity (agility, evasion)
        Will -> Wisdom (mental fortitude)
    """
    
    # Level requirements for universal skills (all available at level 1)
    SKILL_LEVEL_REQUIREMENTS = {
        "fortitude": 1,
        "reflex": 1,
        "will": 1,
    }
    
    # Saving throw skills - passive resistance skills
    # These use UTILITY type as they're passive and don't require targets
    fortitude = Skill(
        name="Fortitude",
        base_class=None,  # Universal skill, not tied to a class
        skill_type=SkillType.UTILITY,
        requires_target=False,
        mana_cost=0,
        stamina_cost=0,
    )
    
    reflex = Skill(
        name="Reflex",
        base_class=None,  # Universal skill, not tied to a class
        skill_type=SkillType.UTILITY,
        requires_target=False,
        mana_cost=0,
        stamina_cost=0,
    )
    
    will = Skill(
        name="Will",
        base_class=None,  # Universal skill, not tied to a class
        skill_type=SkillType.UTILITY,
        requires_target=False,
        mana_cost=0,
        stamina_cost=0,
    )
    
    @classmethod
    def get_skills(cls):
        """Return all universal skills as a dictionary."""
        return {
            "fortitude": cls.fortitude,
            "reflex": cls.reflex,
            "will": cls.will,
        }
    
    @classmethod
    def get_level_requirement(cls, skill_name: str) -> int:
        """Get the level requirement for a universal skill."""
        normalized = skill_name.lower().replace(' ', '_').replace('-', '_')
        return cls.SKILL_LEVEL_REQUIREMENTS.get(normalized, 1)


# Register universal skills
SkillsRegistry.register_skill_class("universal", Skills_Universal.get_skills())
