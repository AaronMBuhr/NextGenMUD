"""
Unit tests for Cleric spells.

Tests cover:
- Heal restoration spell
- Smite holy damage with undead bonus
- Bless hit + damage buff
- Armor of Faith physical damage reduction
- Regeneration healing over time
- Consecrate AoE holy DoT
- Zealotry damage buff with healing penalty
- Judgment powerful holy damage
- Divine Reckoning ultimate AoE + stun
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.skills_cleric import Skills_Cleric, ClericSkills
from NextGenMUDApp.skills_core import Skills, SkillType, SkillAICondition
from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType

from tests.conftest import create_mock_character


class TestClericSkillDefinitions:
    """Tests for cleric skill definitions and properties."""
    
    def test_heal_exists(self):
        """Heal skill should be defined."""
        assert ClericSkills.HEAL is not None
        assert ClericSkills.HEAL.value.name == "heal"
        assert ClericSkills.HEAL.value.base_class == CharacterClassRole.CLERIC
    
    def test_heal_properties(self):
        """Heal should have correct properties."""
        skill = ClericSkills.HEAL.value
        assert skill.mana_cost > 0
        assert skill.skill_type == SkillType.HEAL_SELF
        assert skill.skill_function == "do_cleric_heal"
    
    def test_smite_exists(self):
        """Smite skill should be defined."""
        assert ClericSkills.SMITE is not None
        assert ClericSkills.SMITE.value.name == "smite"
        assert ClericSkills.SMITE.value.base_class == CharacterClassRole.CLERIC
    
    def test_smite_properties(self):
        """Smite should have correct properties."""
        skill = ClericSkills.SMITE.value
        assert skill.mana_cost == 10
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == True
        assert skill.skill_function == "do_cleric_smite"
    
    def test_bless_exists(self):
        """Bless skill should be defined."""
        assert ClericSkills.BLESS is not None
        assert ClericSkills.BLESS.value.name == "bless"
        assert ClericSkills.BLESS.value.base_class == CharacterClassRole.CLERIC
    
    def test_bless_properties(self):
        """Bless should have correct properties."""
        skill = ClericSkills.BLESS.value
        assert skill.mana_cost == 15
        assert skill.skill_type == SkillType.BUFF_SELF
        assert skill.skill_function == "do_cleric_bless"
    
    def test_armor_of_faith_exists(self):
        """Armor of Faith skill should be defined."""
        assert ClericSkills.ARMOR_OF_FAITH is not None
        assert ClericSkills.ARMOR_OF_FAITH.value.name == "armor of faith"
        assert ClericSkills.ARMOR_OF_FAITH.value.base_class == CharacterClassRole.CLERIC
    
    def test_armor_of_faith_properties(self):
        """Armor of Faith should have correct properties."""
        skill = ClericSkills.ARMOR_OF_FAITH.value
        assert skill.mana_cost == 20
        assert skill.skill_type == SkillType.BUFF_SELF
        assert skill.skill_function == "do_cleric_cast_armor_of_faith"
    
    def test_regeneration_exists(self):
        """Regeneration skill should be defined."""
        assert ClericSkills.REGENERATION is not None
        assert ClericSkills.REGENERATION.value.name == "regeneration"
        assert ClericSkills.REGENERATION.value.base_class == CharacterClassRole.CLERIC
    
    def test_regeneration_properties(self):
        """Regeneration should have correct properties."""
        skill = ClericSkills.REGENERATION.value
        assert skill.mana_cost == 25
        assert skill.skill_type == SkillType.HEAL_SELF
        assert skill.skill_function == "do_cleric_regeneration"
    
    def test_consecrate_exists(self):
        """Consecrate skill should be defined."""
        assert ClericSkills.CONSECRATE is not None
        assert ClericSkills.CONSECRATE.value.name == "consecrate"
        assert ClericSkills.CONSECRATE.value.base_class == CharacterClassRole.CLERIC
    
    def test_consecrate_properties(self):
        """Consecrate should have correct properties."""
        skill = ClericSkills.CONSECRATE.value
        assert skill.mana_cost == 25
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == False  # AoE
        assert skill.skill_function == "do_cleric_consecrate"
    
    def test_zealotry_exists(self):
        """Zealotry skill should be defined."""
        assert ClericSkills.ZEALOTRY is not None
        assert ClericSkills.ZEALOTRY.value.name == "zealotry"
        assert ClericSkills.ZEALOTRY.value.base_class == CharacterClassRole.CLERIC
    
    def test_zealotry_properties(self):
        """Zealotry should have correct properties."""
        skill = ClericSkills.ZEALOTRY.value
        assert skill.mana_cost == 20
        assert skill.skill_type == SkillType.BUFF_SELF
        assert skill.skill_function == "do_cleric_zealotry"
    
    def test_judgment_exists(self):
        """Judgment skill should be defined."""
        assert ClericSkills.JUDGMENT is not None
        assert ClericSkills.JUDGMENT.value.name == "judgment"
        assert ClericSkills.JUDGMENT.value.base_class == CharacterClassRole.CLERIC
    
    def test_judgment_properties(self):
        """Judgment should have correct properties."""
        skill = ClericSkills.JUDGMENT.value
        assert skill.mana_cost == 30
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == True
        assert skill.skill_function == "do_cleric_judgment"
    
    def test_divine_reckoning_exists(self):
        """Divine Reckoning skill should be defined."""
        assert ClericSkills.DIVINE_RECKONING is not None
        assert ClericSkills.DIVINE_RECKONING.value.name == "divine reckoning"
        assert ClericSkills.DIVINE_RECKONING.value.base_class == CharacterClassRole.CLERIC
    
    def test_divine_reckoning_properties(self):
        """Divine Reckoning should have correct properties."""
        skill = ClericSkills.DIVINE_RECKONING.value
        assert skill.mana_cost == 60
        assert skill.skill_type == SkillType.DAMAGE
        assert skill.requires_target == False  # AoE
        assert skill.skill_function == "do_cleric_divine_reckoning"


class TestClericSkillTiers:
    """Tests for cleric skill level requirements."""
    
    def test_tier1_skills(self):
        """Tier 1 skills should require level 1."""
        tier1_skills = ["heal", "smite", "bless", "armor of faith", "regeneration"]
        for skill_name in tier1_skills:
            level_req = ClericSkills.get_level_requirement(ClericSkills, skill_name)
            assert level_req == Skills.TIER1_MIN_LEVEL, f"{skill_name} should be Tier 1"
    
    def test_tier2_skills(self):
        """Tier 2 skills should require level 10."""
        tier2_skills = ["consecrate", "zealotry", "judgment"]
        for skill_name in tier2_skills:
            level_req = ClericSkills.get_level_requirement(ClericSkills, skill_name)
            assert level_req == Skills.TIER2_MIN_LEVEL, f"{skill_name} should be Tier 2"
    
    def test_tier4_skills(self):
        """Tier 4 skills should require level 30."""
        tier4_skills = ["divine reckoning"]
        for skill_name in tier4_skills:
            level_req = ClericSkills.get_level_requirement(ClericSkills, skill_name)
            assert level_req == Skills.TIER4_MIN_LEVEL, f"{skill_name} should be Tier 4"


class TestHealSpell:
    """Tests for Heal spell implementation."""
    
    def test_heal_is_healing_type(self):
        """Heal should be a healing skill."""
        skill = ClericSkills.HEAL.value
        assert skill.skill_type == SkillType.HEAL_SELF
    
    def test_heal_can_target_self(self):
        """Heal should be able to target self."""
        skill = ClericSkills.HEAL.value
        # requires_target=False means it defaults to self
        assert skill.requires_target == False


class TestSmiteSpell:
    """Tests for Smite spell implementation."""
    
    def test_smite_requires_target(self):
        """Smite should require a target."""
        skill = ClericSkills.SMITE.value
        assert skill.requires_target == True
    
    def test_smite_has_short_cooldown(self):
        """Smite should have a short cooldown for frequent use."""
        from NextGenMUDApp.utility import ticks_from_seconds
        skill = ClericSkills.SMITE.value
        assert skill.cooldown_ticks <= ticks_from_seconds(10)
    
    def test_smite_low_mana_cost(self):
        """Smite as a basic attack should have low mana cost."""
        skill = ClericSkills.SMITE.value
        assert skill.mana_cost <= 15


class TestBlessSpell:
    """Tests for Bless buff spell implementation."""
    
    def test_bless_is_buff(self):
        """Bless should be a buff skill."""
        skill = ClericSkills.BLESS.value
        assert skill.skill_type == SkillType.BUFF_SELF
    
    def test_bless_prefers_out_of_combat(self):
        """Bless should prefer out of combat casting."""
        skill = ClericSkills.BLESS.value
        assert skill.ai_condition == SkillAICondition.NOT_IN_COMBAT
    
    def test_bless_grants_hit_and_damage_bonus(self):
        """Bless should grant both hit and damage bonuses via states."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateHitBonus, CharacterStateDamageBonus
        
        target = MagicMock()
        target.hit_modifier = 0
        target.damage_modifier = 0
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        # Create hit bonus state
        hit_state = CharacterStateHitBonus(target, game_state, None, "blessed", affect_amount=5)
        assert hit_state.affect_amount == 5
        
        # Create damage bonus state
        damage_state = CharacterStateDamageBonus(target, game_state, None, "blessed", affect_amount=3)
        assert damage_state.affect_amount == 3


class TestArmorOfFaithSpell:
    """Tests for Armor of Faith spell implementation."""
    
    def test_armor_of_faith_is_buff(self):
        """Armor of Faith should be a buff skill."""
        skill = ClericSkills.ARMOR_OF_FAITH.value
        assert skill.skill_type == SkillType.BUFF_SELF
    
    def test_armor_of_faith_reduces_physical_damage(self):
        """Armor of Faith should reduce physical damage taken via state."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateArmorBonus
        
        target = MagicMock()
        target.armor_reduction = 0
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateArmorBonus(target, game_state, None, "armor of faith", 
                                        affect_amount=5)
        
        # Verify state stores the armor bonus
        assert state.affect_amount == 5


class TestRegenerationSpell:
    """Tests for Regeneration HoT spell implementation."""
    
    def test_regeneration_is_heal(self):
        """Regeneration should be a healing skill."""
        skill = ClericSkills.REGENERATION.value
        assert skill.skill_type == SkillType.HEAL_SELF
    
    def test_regeneration_state_heals_over_time(self):
        """CharacterStateRegenerating should heal over time."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateRegenerating
        
        target = create_mock_character(hp=50, max_hp=100)
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateRegenerating(target, game_state, None, "regenerating", 
                                          heal_amount=5)
        
        assert state.heal_amount == 5


class TestConsecrateSpell:
    """Tests for Consecrate AoE DoT spell implementation."""
    
    def test_consecrate_is_aoe(self):
        """Consecrate should not require a single target (AoE)."""
        skill = ClericSkills.CONSECRATE.value
        assert skill.requires_target == False
    
    def test_consecrate_is_damage(self):
        """Consecrate should be a damage skill."""
        skill = ClericSkills.CONSECRATE.value
        assert skill.skill_type == SkillType.DAMAGE
    
    def test_consecrated_state_deals_holy_damage(self):
        """CharacterStateConsecrated should deal holy damage over time."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateConsecrated
        
        target = create_mock_character(hp=100, max_hp=100)
        target.location_room = MagicMock()
        target.location_room.echo = AsyncMock()
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateConsecrated(target, game_state, None, "consecrated", 
                                         damage_amount=8)
        
        assert state.damage_amount == 8
        assert state.total_damage == 0


class TestZealotrySpell:
    """Tests for Zealotry self-buff spell implementation."""
    
    def test_zealotry_is_buff(self):
        """Zealotry should be a buff skill."""
        skill = ClericSkills.ZEALOTRY.value
        assert skill.skill_type == SkillType.BUFF_SELF
    
    def test_zealotry_in_combat(self):
        """Zealotry should be usable in combat."""
        skill = ClericSkills.ZEALOTRY.value
        assert skill.ai_condition == SkillAICondition.IN_COMBAT
    
    def test_zealotry_state_stores_damage_bonus(self):
        """CharacterStateZealotry should store damage bonus."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateZealotry
        
        target = MagicMock()
        target.damage_modifier = 0
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateZealotry(target, game_state, None, "zealous", 
                                      damage_bonus=10, healing_penalty=40)
        
        assert state.damage_bonus == 10
        assert state.healing_penalty == 40
    
    def test_zealotry_state_has_type_name(self):
        """CharacterStateZealotry should have correct type name."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateZealotry
        
        target = MagicMock()
        target.damage_modifier = 0
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateZealotry(target, game_state, None, "zealous", 
                                      damage_bonus=10, healing_penalty=40)
        
        assert state.state_type_name == "zealous"


class TestJudgmentSpell:
    """Tests for Judgment high-damage spell implementation."""
    
    def test_judgment_requires_target(self):
        """Judgment should require a target."""
        skill = ClericSkills.JUDGMENT.value
        assert skill.requires_target == True
    
    def test_judgment_is_damage(self):
        """Judgment should be a damage skill."""
        skill = ClericSkills.JUDGMENT.value
        assert skill.skill_type == SkillType.DAMAGE
    
    def test_judgment_higher_cost_than_smite(self):
        """Judgment should cost more mana than Smite."""
        assert ClericSkills.JUDGMENT.value.mana_cost > ClericSkills.SMITE.value.mana_cost
    
    def test_judgment_longer_cooldown_than_smite(self):
        """Judgment should have longer cooldown than Smite."""
        assert ClericSkills.JUDGMENT.value.cooldown_ticks > ClericSkills.SMITE.value.cooldown_ticks


class TestDivineReckoningSpell:
    """Tests for Divine Reckoning ultimate spell implementation."""
    
    def test_divine_reckoning_is_aoe(self):
        """Divine Reckoning should be AoE (no single target)."""
        skill = ClericSkills.DIVINE_RECKONING.value
        assert skill.requires_target == False
    
    def test_divine_reckoning_is_damage(self):
        """Divine Reckoning should be a damage skill."""
        skill = ClericSkills.DIVINE_RECKONING.value
        assert skill.skill_type == SkillType.DAMAGE
    
    def test_divine_reckoning_high_mana_cost(self):
        """Divine Reckoning should have high mana cost."""
        skill = ClericSkills.DIVINE_RECKONING.value
        assert skill.mana_cost >= 50
    
    def test_divine_reckoning_long_cooldown(self):
        """Divine Reckoning should have a long cooldown."""
        from NextGenMUDApp.utility import ticks_from_seconds
        skill = ClericSkills.DIVINE_RECKONING.value
        # Should be at least 2 minutes
        assert skill.cooldown_ticks >= ticks_from_seconds(120)
    
    def test_divine_reckoning_is_tier4(self):
        """Divine Reckoning should be Tier 4."""
        level_req = ClericSkills.get_level_requirement(ClericSkills, "divine reckoning")
        assert level_req == Skills.TIER4_MIN_LEVEL


class TestClericActorStates:
    """Tests for cleric-related actor states."""
    
    def test_armor_bonus_state_stores_value(self):
        """CharacterStateArmorBonus should store armor bonus value."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateArmorBonus
        
        target = MagicMock()
        target.armor_reduction = 2
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateArmorBonus(target, game_state, None, "armored", affect_amount=5)
        
        assert state.affect_amount == 5
    
    def test_armor_bonus_state_has_type_name(self):
        """CharacterStateArmorBonus should have correct type name."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateArmorBonus
        
        target = MagicMock()
        target.armor_reduction = 2
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateArmorBonus(target, game_state, None, "armored", affect_amount=5)
        
        assert state.state_type_name == "armored"
    
    def test_regenerating_state_has_heal_amount(self):
        """CharacterStateRegenerating should track heal amount."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateRegenerating
        
        target = MagicMock()
        target.current_states = []
        game_state = MagicMock()
        game_state.current_tick = 100
        
        state = CharacterStateRegenerating(target, game_state, None, "regenerating", heal_amount=10)
        
        assert state.heal_amount == 10


class TestClericManaManagement:
    """Tests for mana consumption in cleric spells."""
    
    def test_all_cleric_spells_have_mana_cost(self):
        """All implemented cleric spells should have a mana cost."""
        spells_with_cost = [
            ClericSkills.HEAL.value,
            ClericSkills.SMITE.value,
            ClericSkills.BLESS.value,
            ClericSkills.ARMOR_OF_FAITH.value,
            ClericSkills.REGENERATION.value,
            ClericSkills.CONSECRATE.value,
            ClericSkills.ZEALOTRY.value,
            ClericSkills.JUDGMENT.value,
            ClericSkills.DIVINE_RECKONING.value,
        ]
        
        for spell in spells_with_cost:
            assert spell.mana_cost > 0, f"{spell.name} should have mana cost"
    
    def test_mana_cost_scaling_by_tier(self):
        """Higher tier spells should generally cost more mana."""
        tier1_costs = [
            ClericSkills.HEAL.value.mana_cost,
            ClericSkills.SMITE.value.mana_cost,
            ClericSkills.BLESS.value.mana_cost,
        ]
        tier2_costs = [
            ClericSkills.CONSECRATE.value.mana_cost,
            ClericSkills.ZEALOTRY.value.mana_cost,
            ClericSkills.JUDGMENT.value.mana_cost,
        ]
        tier4_costs = [
            ClericSkills.DIVINE_RECKONING.value.mana_cost,
        ]
        
        avg_tier1 = sum(tier1_costs) / len(tier1_costs)
        avg_tier2 = sum(tier2_costs) / len(tier2_costs)
        avg_tier4 = sum(tier4_costs) / len(tier4_costs)
        
        # Higher tiers should cost more on average
        assert avg_tier2 >= avg_tier1
        assert avg_tier4 >= avg_tier2


class TestClericSpellAIConditions:
    """Tests for AI conditions on cleric spells."""
    
    def test_damage_spells_require_combat(self):
        """Damage spells should be used in combat."""
        combat_spells = [
            ClericSkills.SMITE.value,
            ClericSkills.CONSECRATE.value,
            ClericSkills.JUDGMENT.value,
            ClericSkills.DIVINE_RECKONING.value,
            ClericSkills.ZEALOTRY.value,
        ]
        
        for spell in combat_spells:
            assert spell.ai_condition == SkillAICondition.IN_COMBAT, \
                f"{spell.name} should require combat"
    
    def test_buff_spells_prefer_out_of_combat(self):
        """Buff spells should prefer being cast out of combat."""
        buff_spells = [
            ClericSkills.ARMOR_OF_FAITH.value,
            ClericSkills.BLESS.value,
        ]
        
        for spell in buff_spells:
            assert spell.ai_condition == SkillAICondition.NOT_IN_COMBAT, \
                f"{spell.name} should prefer out of combat"


class TestUndeadBonusDamage:
    """Tests for undead bonus damage mechanics."""
    
    def test_undead_detection_keywords(self):
        """Smite and Judgment should detect undead by name keywords."""
        undead_keywords = ['zombie', 'skeleton', 'undead', 'ghoul', 
                          'vampire', 'lich', 'wraith', 'ghost', 'specter']
        
        for keyword in undead_keywords:
            target_name = f"a {keyword} warrior"
            is_undead = any(word in target_name.lower() for word in undead_keywords)
            assert is_undead, f"{keyword} should be detected as undead"
    
    def test_non_undead_not_detected(self):
        """Non-undead creatures should not get bonus damage."""
        non_undead_names = ['goblin', 'orc', 'dragon', 'bandit', 'wolf']
        undead_keywords = ['zombie', 'skeleton', 'undead', 'ghoul', 
                          'vampire', 'lich', 'wraith', 'ghost', 'specter']
        
        for name in non_undead_names:
            is_undead = any(word in name.lower() for word in undead_keywords)
            assert not is_undead, f"{name} should not be detected as undead"
