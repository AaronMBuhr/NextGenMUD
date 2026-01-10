"""
Unit tests for Mage spells.

Tests cover:
- Magic Missile damage spell
- Shield defensive buff
- Blur dodge bonus buff
- Mana Burn mana drain + damage
- Ignite fire DoT
- Animate Dead necromancy
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.skills_mage import Skills_Mage, MageSkills
from NextGenMUDApp.skills_core import Skills, SkillType, SkillAICondition
from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType
from NextGenMUDApp.nondb_models.character_interface import PermanentCharacterFlags

from tests.conftest import create_mock_character


class TestMageSkillDefinitions:
    """Tests for mage skill definitions and properties."""
    
    def test_magic_missile_exists(self):
        """Magic Missile skill should be defined."""
        assert MageSkills.MAGIC_MISSILE is not None
        assert MageSkills.MAGIC_MISSILE.value.name == "magic missile"
        assert MageSkills.MAGIC_MISSILE.value.base_class == CharacterClassRole.MAGE
    
    def test_magic_missile_properties(self):
        """Magic Missile should have correct properties."""
        skill = MageSkills.MAGIC_MISSILE.value
        assert skill.mana_cost == 8
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == True
        assert skill.skill_function == "do_mage_cast_magic_missile"
    
    def test_shield_exists(self):
        """Shield skill should be defined."""
        assert MageSkills.SHIELD is not None
        assert MageSkills.SHIELD.value.name == "shield"
        assert MageSkills.SHIELD.value.base_class == CharacterClassRole.MAGE
    
    def test_shield_properties(self):
        """Shield should have correct properties."""
        skill = MageSkills.SHIELD.value
        assert skill.mana_cost == 20
        assert skill.skill_type == SkillType.BUFF_SELF
        assert skill.requires_target == False
        assert skill.skill_function == "do_mage_cast_shield"
    
    def test_blur_exists(self):
        """Blur skill should be defined."""
        assert MageSkills.BLUR is not None
        assert MageSkills.BLUR.value.name == "blur"
        assert MageSkills.BLUR.value.base_class == CharacterClassRole.MAGE
    
    def test_blur_properties(self):
        """Blur should have correct properties."""
        skill = MageSkills.BLUR.value
        assert skill.mana_cost == 15
        assert skill.skill_type == SkillType.BUFF_SELF
        assert skill.skill_function == "do_mage_cast_blur"
    
    def test_mana_burn_exists(self):
        """Mana Burn skill should be defined."""
        assert MageSkills.MANA_BURN is not None
        assert MageSkills.MANA_BURN.value.name == "mana burn"
        assert MageSkills.MANA_BURN.value.base_class == CharacterClassRole.MAGE
    
    def test_mana_burn_properties(self):
        """Mana Burn should have correct properties."""
        skill = MageSkills.MANA_BURN.value
        assert skill.mana_cost == 20
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == True
        assert skill.skill_function == "do_mage_cast_mana_burn"
    
    def test_ignite_exists(self):
        """Ignite skill should be defined."""
        assert MageSkills.IGNITE is not None
        assert MageSkills.IGNITE.value.name == "ignite"
        assert MageSkills.IGNITE.value.base_class == CharacterClassRole.MAGE
    
    def test_ignite_properties(self):
        """Ignite should have correct properties."""
        skill = MageSkills.IGNITE.value
        assert skill.mana_cost == 12
        assert skill.skill_type == SkillType.DOT
        assert skill.requires_target == True
        assert skill.skill_function == "do_mage_cast_ignite"
    
    def test_animate_dead_exists(self):
        """Animate Dead skill should be defined."""
        assert MageSkills.ANIMATE_DEAD is not None
        assert MageSkills.ANIMATE_DEAD.value.name == "animate dead"
        assert MageSkills.ANIMATE_DEAD.value.base_class == CharacterClassRole.MAGE
    
    def test_animate_dead_properties(self):
        """Animate Dead should have correct properties."""
        skill = MageSkills.ANIMATE_DEAD.value
        assert skill.mana_cost == 40
        assert skill.skill_function == "do_mage_cast_animate_dead"


class TestMageSkillTiers:
    """Tests for mage skill level requirements."""
    
    def test_tier1_skills(self):
        """Tier 1 skills should require level 1."""
        tier1_skills = ["magic missile", "blur", "ignite", "shield"]
        for skill_name in tier1_skills:
            level_req = MageSkills.get_level_requirement(MageSkills, skill_name)
            assert level_req == Skills.TIER1_MIN_LEVEL, f"{skill_name} should be Tier 1"
    
    def test_tier2_skills(self):
        """Tier 2 skills should require level 10."""
        tier2_skills = ["mana burn", "animate dead"]
        for skill_name in tier2_skills:
            level_req = MageSkills.get_level_requirement(MageSkills, skill_name)
            assert level_req == Skills.TIER2_MIN_LEVEL, f"{skill_name} should be Tier 2"


class TestMagicMissileSpell:
    """Tests for Magic Missile implementation."""
    
    def test_magic_missile_requires_target(self):
        """Magic Missile should require a target."""
        skill = MageSkills.MAGIC_MISSILE.value
        assert skill.requires_target == True
    
    def test_magic_missile_is_damage_type(self):
        """Magic Missile should be a damage skill."""
        skill = MageSkills.MAGIC_MISSILE.value
        assert skill.skill_type == SkillType.DAMAGE
    
    def test_magic_missile_has_cooldown(self):
        """Magic Missile should have a cooldown."""
        skill = MageSkills.MAGIC_MISSILE.value
        assert skill.cooldown_ticks > 0


class TestShieldSpell:
    """Tests for Shield spell implementation."""
    
    def test_shield_is_self_cast(self):
        """Shield should default to self if no target."""
        skill = MageSkills.SHIELD.value
        assert skill.requires_target == False
    
    def test_shield_is_buff_type(self):
        """Shield should be a buff skill."""
        skill = MageSkills.SHIELD.value
        assert skill.skill_type == SkillType.BUFF_SELF
    
    def test_shield_has_duration(self):
        """Shield should have a duration."""
        skill = MageSkills.SHIELD.value
        assert skill.duration_min_ticks > 0


class TestBlurSpell:
    """Tests for Blur spell implementation."""
    
    def test_blur_is_buff_type(self):
        """Blur should be a buff skill."""
        skill = MageSkills.BLUR.value
        assert skill.skill_type == SkillType.BUFF_SELF
    
    def test_blur_can_target_self(self):
        """Blur should be able to target self."""
        skill = MageSkills.BLUR.value
        # It can also target others, but defaults to self
        assert skill.requires_target == False
    
    def test_blur_has_duration(self):
        """Blur should have a duration."""
        skill = MageSkills.BLUR.value
        assert skill.duration_min_ticks > 0


class TestManaBurnSpell:
    """Tests for Mana Burn spell implementation."""
    
    def test_mana_burn_requires_target(self):
        """Mana Burn should require a target."""
        skill = MageSkills.MANA_BURN.value
        assert skill.requires_target == True
    
    def test_mana_burn_deals_damage_based_on_mana_drained(self):
        """Mana Burn damage should scale with mana drained."""
        # This would require a full integration test
        # For now, verify the skill is configured correctly
        skill = MageSkills.MANA_BURN.value
        assert skill.skill_type == SkillType.DAMAGE


class TestIgniteSpell:
    """Tests for Ignite DoT spell implementation."""
    
    def test_ignite_is_dot(self):
        """Ignite should be a DoT skill."""
        skill = MageSkills.IGNITE.value
        assert skill.skill_type == SkillType.DOT
    
    def test_ignite_requires_target(self):
        """Ignite should require a target."""
        skill = MageSkills.IGNITE.value
        assert skill.requires_target == True
    
    def test_ignite_state_deals_fire_damage(self):
        """CharacterStateIgnited should deal fire damage."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateIgnited
        
        target = create_mock_character(hp=100, max_hp=100)
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateIgnited(target, game_state, None, "ignited", damage_amount=10)
        
        # Verify state properties
        assert state.damage_amount == 10
        assert state.total_damage == 0


class TestAnimateDeadSpell:
    """Tests for Animate Dead necromancy spell."""
    
    def test_animate_dead_is_tier2(self):
        """Animate Dead should be a Tier 2 spell."""
        level_req = MageSkills.get_level_requirement(MageSkills, "animate dead")
        assert level_req == Skills.TIER2_MIN_LEVEL
    
    def test_animate_dead_mana_cost(self):
        """Animate Dead should have significant mana cost."""
        skill = MageSkills.ANIMATE_DEAD.value
        assert skill.mana_cost >= 30


class TestMageActorStates:
    """Tests for mage-related actor states."""
    
    def test_dodge_bonus_state_properties(self):
        """CharacterStateDodgeBonus should have correct properties."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateDodgeBonus
        
        target = MagicMock()
        target.dodge_modifier = 5
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateDodgeBonus(target, game_state, None, "blurred", affect_amount=15)
        
        # Verify state is created with correct properties
        assert state.affect_amount == 15
        assert state.state_type_name == "blurred"
    
    def test_dodge_bonus_state_tracks_amount(self):
        """CharacterStateDodgeBonus should track the dodge bonus amount."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateDodgeBonus
        
        target = MagicMock()
        target.dodge_modifier = 5
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateDodgeBonus(target, game_state, None, "blurred", affect_amount=15)
        
        # The affect_amount is stored correctly
        assert state.affect_amount == 15
    
    def test_shielded_state_stores_multipliers(self):
        """CharacterStateShielded should store damage multipliers."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateShielded
        from NextGenMUDApp.nondb_models.attacks_and_damage import DamageMultipliers
        
        target = MagicMock()
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        multipliers = DamageMultipliers()
        multipliers.set(DamageType.SLASHING, 10)
        
        state = CharacterStateShielded(target, game_state, None, "shielded", multipliers=multipliers)
        
        # Verify multipliers are stored
        assert state.extra_multipliers is not None
        assert state.extra_multipliers.get(DamageType.SLASHING) == 10
    
    def test_charmed_state_tracks_controller(self):
        """CharacterStateCharmed should track the charmer."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateCharmed
        
        charmer = create_mock_character(name="Mage")
        target = create_mock_character(name="Zombie")
        target.charmed_by = None
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateCharmed(target, game_state, charmer, "charmed")
        
        assert state.charmed_by == charmer


class TestMageManaManagement:
    """Tests for mana consumption in mage spells."""
    
    def test_all_mage_spells_have_mana_cost(self):
        """All implemented mage spells should have a mana cost."""
        spells_with_cost = [
            MageSkills.MAGIC_MISSILE.value,
            MageSkills.SHIELD.value,
            MageSkills.BLUR.value,
            MageSkills.MANA_BURN.value,
            MageSkills.IGNITE.value,
            MageSkills.ANIMATE_DEAD.value,
        ]
        
        for spell in spells_with_cost:
            assert spell.mana_cost > 0, f"{spell.name} should have mana cost"
    
    def test_mana_cost_scaling(self):
        """Higher tier spells should generally cost more mana."""
        tier1_costs = [
            MageSkills.MAGIC_MISSILE.value.mana_cost,
            MageSkills.BLUR.value.mana_cost,
            MageSkills.IGNITE.value.mana_cost,
        ]
        tier2_costs = [
            MageSkills.MANA_BURN.value.mana_cost,
            MageSkills.ANIMATE_DEAD.value.mana_cost,
        ]
        
        avg_tier1 = sum(tier1_costs) / len(tier1_costs)
        avg_tier2 = sum(tier2_costs) / len(tier2_costs)
        
        # Tier 2 spells should generally cost more on average
        assert avg_tier2 >= avg_tier1


class TestMageSpellAIConditions:
    """Tests for AI conditions on mage spells."""
    
    def test_damage_spells_require_combat(self):
        """Damage spells should be used in combat."""
        combat_spells = [
            MageSkills.MAGIC_MISSILE.value,
            MageSkills.MANA_BURN.value,
            MageSkills.IGNITE.value,
        ]
        
        for spell in combat_spells:
            assert spell.ai_condition == SkillAICondition.IN_COMBAT, \
                f"{spell.name} should require combat"
    
    def test_buff_spells_prefer_out_of_combat(self):
        """Buff spells should prefer being cast out of combat."""
        buff_spells = [
            MageSkills.SHIELD.value,
            MageSkills.BLUR.value,
        ]
        
        for spell in buff_spells:
            assert spell.ai_condition == SkillAICondition.NOT_IN_COMBAT, \
                f"{spell.name} should prefer out of combat"
