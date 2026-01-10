"""
Unit tests for the Skills system.

Tests cover:
- Skill registration and lookup
- Skill name parsing
- Skill invocation
- Resource consumption
- Cooldown handling
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.skills_core import (
    Skills, SkillsRegistry, Skill, SkillAICondition, SkillType
)
from NextGenMUDApp.constants import CharacterClassRole


class TestSkillsRegistry:
    """Tests for the SkillsRegistry class."""
    
    def test_register_skill_class(self):
        """Should be able to register a skill class."""
        test_skill = Skill(
            name="test skill",
            base_class=CharacterClassRole.FIGHTER
        )
        skills_dict = {"test skill": test_skill}
        
        SkillsRegistry.register_skill_class("test_class", skills_dict)
        
        assert SkillsRegistry.get_class_skills("test_class") == skills_dict
    
    def test_get_skill_by_name(self):
        """Should be able to get a skill by name."""
        test_skill = Skill(
            name="lookup test",
            base_class=CharacterClassRole.FIGHTER
        )
        SkillsRegistry.register_skill_class("lookup_class", {"lookup test": test_skill})
        
        # Skills are also registered by name
        result = SkillsRegistry._skills_by_name.get("lookup test")
        assert result is not None
    
    def test_get_class_skills_returns_dict(self):
        """get_class_skills should return a dictionary."""
        skills = SkillsRegistry.get_class_skills("fighter")
        assert isinstance(skills, dict)
    
    def test_get_class_skills_for_unknown_class(self):
        """get_class_skills should return empty dict for unknown class."""
        skills = SkillsRegistry.get_class_skills("nonexistent_class")
        assert skills == {}


class TestSkillNameParsing:
    """Tests for parsing skill names from input."""
    
    def test_parse_exact_match(self):
        """Should match exact skill names."""
        # Register a test skill
        test_skill = Skill(name="fire bolt", base_class=CharacterClassRole.MAGE)
        SkillsRegistry._skills_by_name["fire bolt"] = test_skill
        
        skill_name, remainder = SkillsRegistry.parse_skill_name_from_input("fire bolt")
        
        assert skill_name == "fire bolt"
        assert remainder == ""
    
    def test_parse_with_target(self):
        """Should parse skill name and return remainder for target."""
        test_skill = Skill(name="magic missile", base_class=CharacterClassRole.MAGE)
        SkillsRegistry._skills_by_name["magic missile"] = test_skill
        
        skill_name, remainder = SkillsRegistry.parse_skill_name_from_input("magic missile goblin")
        
        # The skill should be found
        assert skill_name is not None
    
    def test_parse_unknown_skill(self):
        """Should return None for unknown skills."""
        skill_name, remainder = SkillsRegistry.parse_skill_name_from_input("xyzzy_nonexistent")
        
        assert skill_name is None


class TestSkillClass:
    """Tests for the Skill class itself."""
    
    def test_skill_creation(self):
        """Should be able to create a Skill with all properties."""
        skill = Skill(
            name="Test Skill",
            base_class=CharacterClassRole.FIGHTER,
            cooldown_name="test_cooldown",
            cooldown_ticks=100,
            cast_time_ticks=10,
            mana_cost=20,
            stamina_cost=15,
            ai_priority=70,
            ai_condition=SkillAICondition.ALWAYS,
            skill_type=SkillType.DAMAGE,
            requires_target=True
        )
        
        assert skill.name == "Test Skill"
        assert skill.base_class == CharacterClassRole.FIGHTER
        assert skill.cooldown_name == "test_cooldown"
        assert skill.cooldown_ticks == 100
        assert skill.mana_cost == 20
        assert skill.stamina_cost == 15
        assert skill.ai_priority == 70
        assert skill.ai_condition == SkillAICondition.ALWAYS
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == True
    
    def test_skill_default_values(self):
        """Skill should have sensible defaults."""
        skill = Skill(
            name="Minimal Skill",
            base_class=CharacterClassRole.ROGUE
        )
        
        assert skill.cooldown_name is None
        assert skill.cooldown_ticks == 0
        assert skill.mana_cost == 0
        assert skill.stamina_cost == 0
        assert skill.ai_priority == 50  # Default
        assert skill.ai_condition == SkillAICondition.ALWAYS  # Default
        assert skill.skill_type == SkillType.DAMAGE  # Default
        assert skill.requires_target == True  # Default


class TestSkillAIConditions:
    """Tests for SkillAICondition values."""
    
    def test_condition_values(self):
        """All condition values should be strings."""
        assert isinstance(SkillAICondition.ALWAYS, str)
        assert isinstance(SkillAICondition.SELF_HP_BELOW_25, str)
        assert isinstance(SkillAICondition.SELF_HP_BELOW_50, str)
        assert isinstance(SkillAICondition.TARGET_HP_BELOW_25, str)
        assert isinstance(SkillAICondition.TARGET_NOT_STUNNED, str)
        assert isinstance(SkillAICondition.IN_COMBAT, str)


class TestSkillTypes:
    """Tests for SkillType values."""
    
    def test_type_values(self):
        """All skill types should be strings."""
        assert isinstance(SkillType.DAMAGE, str)
        assert isinstance(SkillType.DOT, str)
        assert isinstance(SkillType.HEAL_SELF, str)
        assert isinstance(SkillType.HEAL_OTHER, str)
        assert isinstance(SkillType.BUFF_SELF, str)
        assert isinstance(SkillType.DEBUFF, str)
        assert isinstance(SkillType.STUN, str)
        assert isinstance(SkillType.STANCE, str)


class TestSkillsBaseClass:
    """Tests for the Skills base class methods."""
    
    def test_tier_levels_defined(self):
        """Tier level constants should be defined."""
        assert Skills.TIER1_MIN_LEVEL == 1
        assert Skills.TIER2_MIN_LEVEL == 10
        assert Skills.TIER3_MIN_LEVEL == 20
    
    def test_attribute_constants(self):
        """Attribute constants should be defined."""
        assert Skills.ATTRIBUTE_AVERAGE == 10
        assert Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT > 0


class TestSkillCapCalculation:
    """Tests for the dynamic skill cap calculation system.
    
    The skill cap system works as follows:
    - Level 1 skills (treated as level 0): cap of ~32 at level 1, reaches 100 at level 10
    - Level 10 skills: cap of 25 at level 10, reaches 100 at level 20
    - Level 20 skills: cap of 25 at level 20, reaches 100 at level 30
    - And so on (75 points over 10 levels = 7.5 per level)
    """
    
    def test_skill_cap_constants(self):
        """Skill cap constants should be defined."""
        assert Skills.SKILL_CAP_BASE == 25
        assert Skills.SKILL_CAP_MAX == 100
        assert Skills.SKILL_CAP_LEVELS_TO_MAX == 10
        assert Skills.SKILL_CAP_PER_LEVEL == 7.5
    
    def test_level1_skills_at_level1(self):
        """Level 1 skills at character level 1 should have cap of 32 (25 + 1*7.5)."""
        cap = Skills.calculate_skill_cap(character_level=1, skill_requirement_level=1)
        assert cap == 32
    
    def test_level1_skills_at_level10(self):
        """Level 1 skills at character level 10 should have cap of 100."""
        cap = Skills.calculate_skill_cap(character_level=10, skill_requirement_level=1)
        assert cap == 100
    
    def test_level1_skills_at_level5(self):
        """Level 1 skills at character level 5 should have cap of 62 (25 + 5*7.5)."""
        cap = Skills.calculate_skill_cap(character_level=5, skill_requirement_level=1)
        assert cap == 62
    
    def test_level10_skills_at_level10(self):
        """Level 10 skills at character level 10 should have cap of 25."""
        cap = Skills.calculate_skill_cap(character_level=10, skill_requirement_level=10)
        assert cap == 25
    
    def test_level10_skills_at_level20(self):
        """Level 10 skills at character level 20 should have cap of 100."""
        cap = Skills.calculate_skill_cap(character_level=20, skill_requirement_level=10)
        assert cap == 100
    
    def test_level10_skills_at_level15(self):
        """Level 10 skills at character level 15 should have cap of 62 (25 + 5*7.5)."""
        cap = Skills.calculate_skill_cap(character_level=15, skill_requirement_level=10)
        assert cap == 62
    
    def test_level20_skills_at_level20(self):
        """Level 20 skills at character level 20 should have cap of 25."""
        cap = Skills.calculate_skill_cap(character_level=20, skill_requirement_level=20)
        assert cap == 25
    
    def test_level20_skills_at_level30(self):
        """Level 20 skills at character level 30 should have cap of 100."""
        cap = Skills.calculate_skill_cap(character_level=30, skill_requirement_level=20)
        assert cap == 100
    
    def test_level30_skills_at_level30(self):
        """Level 30 skills at character level 30 should have cap of 25."""
        cap = Skills.calculate_skill_cap(character_level=30, skill_requirement_level=30)
        assert cap == 25
    
    def test_level30_skills_at_level40(self):
        """Level 30 skills at character level 40 should have cap of 100."""
        cap = Skills.calculate_skill_cap(character_level=40, skill_requirement_level=30)
        assert cap == 100
    
    def test_skill_below_requirement_returns_zero(self):
        """Skills at character levels below requirement should have cap of 0."""
        cap = Skills.calculate_skill_cap(character_level=5, skill_requirement_level=10)
        assert cap == 0
    
    def test_override_cap(self):
        """YAML override cap should take precedence."""
        cap = Skills.calculate_skill_cap(character_level=1, skill_requirement_level=1, override_cap=50)
        assert cap == 50
    
    def test_override_cap_clamped_to_max(self):
        """YAML override cap should not exceed MAX_SKILL_LEVEL."""
        cap = Skills.calculate_skill_cap(character_level=1, skill_requirement_level=1, override_cap=150)
        assert cap == 100
    
    def test_cap_does_not_exceed_max(self):
        """Cap should never exceed MAX_SKILL_LEVEL even with high character levels."""
        cap = Skills.calculate_skill_cap(character_level=50, skill_requirement_level=1)
        assert cap == 100


@pytest.mark.asyncio
class TestSkillInvocation:
    """Tests for skill invocation via the registry."""
    
    async def test_invoke_unknown_skill_returns_false(self, mock_game_state):
        """Invoking an unknown skill should return False."""
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        GameStateInterface.set_instance(mock_game_state)
        
        actor = MagicMock()
        actor.fighting_whom = None
        
        result = await SkillsRegistry.invoke_skill_by_name(
            mock_game_state, actor, "completely_unknown_skill", ""
        )
        
        assert result == False
    
    async def test_invoke_skill_without_function_returns_false(self, mock_game_state):
        """Invoking a skill without a function should return False."""
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        GameStateInterface.set_instance(mock_game_state)
        
        # Register a skill without a function
        no_func_skill = Skill(
            name="no_function_skill",
            base_class=CharacterClassRole.FIGHTER,
            skill_function=None
        )
        SkillsRegistry._skills_by_name["no_function_skill"] = no_func_skill
        
        actor = MagicMock()
        actor.fighting_whom = None
        
        result = await SkillsRegistry.invoke_skill_by_name(
            mock_game_state, actor, "no_function_skill", ""
        )
        
        assert result == False
