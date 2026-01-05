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
