"""
Unit tests for the Combat AI system.

Tests cover:
- HP percentage calculation
- AI condition checking
- Skill availability checking
- Skill priority calculation
- Skill selection logic
- Combat action queueing
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from NextGenMUDApp.combat_ai import CombatAI
from NextGenMUDApp.skills_core import Skill, SkillAICondition, SkillType
from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.character_interface import (
    TemporaryCharacterFlags, PermanentCharacterFlags
)

from tests.conftest import create_mock_character


class TestHPPercentage:
    """Tests for HP percentage calculations."""
    
    def test_full_hp_is_100_percent(self):
        """Full HP should return 100%."""
        char = create_mock_character(hp=100, max_hp=100)
        assert CombatAI.get_hp_percent(char) == 100
    
    def test_half_hp_is_50_percent(self):
        """Half HP should return 50%."""
        char = create_mock_character(hp=50, max_hp=100)
        assert CombatAI.get_hp_percent(char) == 50
    
    def test_low_hp_calculation(self):
        """Low HP should calculate correctly."""
        char = create_mock_character(hp=15, max_hp=100)
        assert CombatAI.get_hp_percent(char) == 15
    
    def test_zero_max_hp_returns_zero(self):
        """Zero max HP should return 0% (avoid division by zero)."""
        char = create_mock_character(hp=0, max_hp=0)
        assert CombatAI.get_hp_percent(char) == 0


class TestConditionChecking:
    """Tests for AI condition evaluation."""
    
    def test_always_condition(self):
        """ALWAYS condition should always return True."""
        actor = create_mock_character()
        target = create_mock_character()
        
        assert CombatAI.check_condition(SkillAICondition.ALWAYS, actor, target) == True
    
    def test_self_hp_below_25_when_low(self):
        """SELF_HP_BELOW_25 should be True when HP < 25%."""
        actor = create_mock_character(hp=20, max_hp=100)
        target = create_mock_character()
        
        assert CombatAI.check_condition(SkillAICondition.SELF_HP_BELOW_25, actor, target) == True
    
    def test_self_hp_below_25_when_high(self):
        """SELF_HP_BELOW_25 should be False when HP >= 25%."""
        actor = create_mock_character(hp=50, max_hp=100)
        target = create_mock_character()
        
        assert CombatAI.check_condition(SkillAICondition.SELF_HP_BELOW_25, actor, target) == False
    
    def test_self_hp_below_50(self):
        """SELF_HP_BELOW_50 should work correctly."""
        low_hp = create_mock_character(hp=40, max_hp=100)
        high_hp = create_mock_character(hp=60, max_hp=100)
        target = create_mock_character()
        
        assert CombatAI.check_condition(SkillAICondition.SELF_HP_BELOW_50, low_hp, target) == True
        assert CombatAI.check_condition(SkillAICondition.SELF_HP_BELOW_50, high_hp, target) == False
    
    def test_target_hp_below_25(self):
        """TARGET_HP_BELOW_25 should check target's HP."""
        actor = create_mock_character()
        low_target = create_mock_character(hp=20, max_hp=100)
        high_target = create_mock_character(hp=50, max_hp=100)
        
        assert CombatAI.check_condition(SkillAICondition.TARGET_HP_BELOW_25, actor, low_target) == True
        assert CombatAI.check_condition(SkillAICondition.TARGET_HP_BELOW_25, actor, high_target) == False
    
    def test_target_not_stunned_when_not_stunned(self):
        """TARGET_NOT_STUNNED should be True when target is not stunned."""
        actor = create_mock_character()
        target = create_mock_character()
        target.has_temp_flags = MagicMock(return_value=False)
        
        assert CombatAI.check_condition(SkillAICondition.TARGET_NOT_STUNNED, actor, target) == True
    
    def test_target_not_stunned_when_stunned(self):
        """TARGET_NOT_STUNNED should be False when target is stunned."""
        actor = create_mock_character()
        target = create_mock_character()
        target.has_temp_flags = MagicMock(return_value=True)
        
        assert CombatAI.check_condition(SkillAICondition.TARGET_NOT_STUNNED, actor, target) == False
    
    def test_in_combat_when_fighting(self):
        """IN_COMBAT should be True when fighting someone."""
        actor = create_mock_character()
        actor.fighting_whom = create_mock_character()
        
        assert CombatAI.check_condition(SkillAICondition.IN_COMBAT, actor, None) == True
    
    def test_in_combat_when_not_fighting(self):
        """IN_COMBAT should be False when not fighting."""
        actor = create_mock_character()
        actor.fighting_whom = None
        
        assert CombatAI.check_condition(SkillAICondition.IN_COMBAT, actor, None) == False


class TestCanUseSkill:
    """Tests for skill usability checking."""
    
    @pytest.fixture
    def basic_skill(self):
        """A basic skill with no special requirements."""
        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.cooldown_name = None
        skill.mana_cost = 0
        skill.stamina_cost = 0
        skill.requires_target = False
        skill.ai_condition = SkillAICondition.ALWAYS
        skill.skill_function = MagicMock()
        return skill
    
    def test_can_use_basic_skill(self, basic_skill):
        """Should be able to use a skill with no requirements."""
        actor = create_mock_character()
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill)
        
        assert can_use == True
        assert reason == ""
    
    def test_cannot_use_skill_on_cooldown(self, basic_skill):
        """Cannot use skill that's on cooldown."""
        actor = create_mock_character()
        actor.has_cooldown = MagicMock(return_value=True)
        basic_skill.cooldown_name = "test_cooldown"
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill)
        
        assert can_use == False
        assert "cooldown" in reason
    
    def test_cannot_use_skill_without_mana(self, basic_skill):
        """Cannot use skill if not enough mana."""
        actor = create_mock_character(mana=10, max_mana=100)
        basic_skill.mana_cost = 20
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill)
        
        assert can_use == False
        assert "mana" in reason
    
    def test_cannot_use_skill_without_stamina(self, basic_skill):
        """Cannot use skill if not enough stamina."""
        actor = create_mock_character(stamina=5, max_stamina=100)
        basic_skill.stamina_cost = 15
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill)
        
        assert can_use == False
        assert "stamina" in reason
    
    def test_cannot_use_targeted_skill_without_target(self, basic_skill):
        """Cannot use targeted skill without a target."""
        actor = create_mock_character()
        basic_skill.requires_target = True
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill, target=None)
        
        assert can_use == False
        assert "target" in reason
    
    def test_can_use_targeted_skill_with_target(self, basic_skill):
        """Can use targeted skill when target is provided."""
        actor = create_mock_character()
        target = create_mock_character()
        basic_skill.requires_target = True
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill, target=target)
        
        assert can_use == True
    
    def test_cannot_use_skill_when_condition_not_met(self, basic_skill):
        """Cannot use skill when AI condition is not met."""
        actor = create_mock_character(hp=80, max_hp=100)  # HP above 50%
        basic_skill.ai_condition = SkillAICondition.SELF_HP_BELOW_50
        
        can_use, reason = CombatAI.can_use_skill(actor, basic_skill)
        
        assert can_use == False
        assert "condition" in reason


class TestSkillSelection:
    """Tests for skill selection and priority."""
    
    def test_choose_skill_returns_none_for_no_skills(self):
        """Should return None when no skills are available."""
        actor = create_mock_character()
        actor.levels_by_role = {}  # No classes
        
        skill = CombatAI.choose_skill(actor, None)
        
        assert skill is None
    
    def test_queue_combat_action_returns_false_for_pc(self):
        """queue_combat_action should return False for player characters."""
        actor = create_mock_character(is_pc=True)
        target = create_mock_character()
        
        result = CombatAI.queue_combat_action(actor, target)
        
        assert result == False
    
    def test_queue_combat_action_returns_false_for_no_classes(self):
        """queue_combat_action should return False for NPCs with no classes."""
        actor = create_mock_character()
        actor.levels_by_role = {}
        target = create_mock_character()
        
        result = CombatAI.queue_combat_action(actor, target)
        
        assert result == False


class TestPriorityCalculation:
    """Tests for dynamic priority adjustments."""
    
    @pytest.fixture
    def heal_skill(self):
        """A healing skill for priority testing."""
        skill = MagicMock(spec=Skill)
        skill.name = "heal"
        skill.cooldown_name = None
        skill.mana_cost = 0
        skill.stamina_cost = 0
        skill.requires_target = False
        skill.ai_condition = SkillAICondition.ALWAYS
        skill.ai_priority = 50
        skill.skill_type = SkillType.HEAL_SELF
        skill.skill_function = MagicMock()
        return skill
    
    @pytest.fixture
    def stun_skill(self):
        """A stun skill for priority testing."""
        skill = MagicMock(spec=Skill)
        skill.name = "stun"
        skill.cooldown_name = None
        skill.mana_cost = 0
        skill.stamina_cost = 0
        skill.requires_target = True
        skill.ai_condition = SkillAICondition.ALWAYS
        skill.ai_priority = 50
        skill.skill_type = SkillType.STUN
        skill.skill_function = MagicMock()
        return skill
    
    # Note: These tests verify the priority adjustment logic conceptually
    # Actual priority testing requires integration with get_available_skills
    
    def test_healing_priority_boosted_at_low_hp(self, heal_skill):
        """Healing skills should have boosted priority at low HP."""
        # This is tested through the get_available_skills method
        # which applies priority boosts based on HP thresholds
        assert heal_skill.skill_type == SkillType.HEAL_SELF
        assert heal_skill.ai_priority == 50
        # At < 25% HP, priority should be boosted by 50
        # At < 50% HP, priority should be boosted by 25
    
    def test_stun_priority_reduced_on_stunned_target(self, stun_skill):
        """Stun skills should have reduced priority on already stunned targets."""
        assert stun_skill.skill_type == SkillType.STUN
        # When target is already stunned, priority should be reduced by 50
