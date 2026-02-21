"""
Unit tests for the Character class and related functionality.

Tests cover:
- Character creation and YAML loading
- Class and level management
- Skill assignment (templated and explicit)
- skills_by_class proxy behavior
- Attribute access
- Resource calculations (HP, mana, stamina)
"""

import pytest
from unittest.mock import MagicMock, patch

from NextGenMUDApp.constants import CharacterClassRole, Constants
from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes, PermanentCharacterFlags


class TestCharacterCreation:
    """Tests for basic character creation and initialization."""
    
    def test_character_created_with_name(self, create_test_character, base_character_data):
        """Character should be created with the specified name."""
        char = create_test_character(base_character_data)
        assert char.name == "Test Character"
    
    def test_character_has_attributes(self, create_test_character, base_character_data):
        """Character should have attributes loaded from YAML."""
        char = create_test_character(base_character_data)
        assert CharacterAttributes.STRENGTH in char.attributes
        assert char.attributes[CharacterAttributes.STRENGTH] == 14
    
    def test_character_has_natural_attacks(self, create_test_character, base_character_data):
        """Character should have natural attacks loaded."""
        char = create_test_character(base_character_data)
        assert len(char.natural_attacks) == 1
        assert char.natural_attacks[0].attack_noun == "fist"


class TestCharacterClasses:
    """Tests for class and level management."""
    
    def test_fighter_has_fighter_class(self, test_fighter):
        """Fighter character should have FIGHTER class."""
        assert CharacterClassRole.FIGHTER in test_fighter.levels_by_role
        assert test_fighter.levels_by_role[CharacterClassRole.FIGHTER] == 5
    
    def test_fighter_in_class_priority(self, test_fighter):
        """Fighter class should be in class priority list."""
        assert CharacterClassRole.FIGHTER in test_fighter.class_priority
    
    def test_multiclass_has_both_classes(self, create_test_character, multiclass_character_data):
        """Multiclass character should have both classes."""
        char = create_test_character(multiclass_character_data)
        assert CharacterClassRole.FIGHTER in char.levels_by_role
        assert CharacterClassRole.MAGE in char.levels_by_role
        assert char.levels_by_role[CharacterClassRole.FIGHTER] == 3
        assert char.levels_by_role[CharacterClassRole.MAGE] == 2
    
    def test_multiclass_respects_class_priority(self, create_test_character, multiclass_character_data):
        """Multiclass should respect explicit class priority order."""
        char = create_test_character(multiclass_character_data)
        assert char.class_priority[0] == CharacterClassRole.FIGHTER
        assert char.class_priority[1] == CharacterClassRole.MAGE
    
    def test_total_levels(self, create_test_character, multiclass_character_data):
        """total_levels() should sum all class levels."""
        char = create_test_character(multiclass_character_data)
        assert char.total_levels() == 5  # 3 fighter + 2 mage


class TestSkillAssignment:
    """Tests for automatic and explicit skill assignment."""
    
    def test_fighter_gets_auto_skills(self, test_fighter):
        """Fighter should automatically get fighter skills based on level."""
        # Should have skills appropriate for level 5
        assert CharacterClassRole.FIGHTER in test_fighter.skill_levels_by_role
        skills = test_fighter.skill_levels_by_role[CharacterClassRole.FIGHTER]
        # Should have at least some tier 1 skills
        assert len(skills) > 0
    
    def test_explicit_skill_override(self, create_test_character, fighter_character_data):
        """Explicit skill levels should override auto-populated ones."""
        data = fighter_character_data.copy()
        data['class']['fighter']['skills'] = {
            'mighty_kick': 3  # Override to level 3
        }
        char = create_test_character(data)
        skills = char.skill_levels_by_role[CharacterClassRole.FIGHTER]
        assert skills.get('mighty_kick') == 3
    
    def test_skill_removal_syntax(self, create_test_character, fighter_character_data):
        """Skills can be removed with -skill_name or level: 0 syntax."""
        data = fighter_character_data.copy()
        data['class']['fighter']['skills'] = {
            '-mighty_kick': None  # Remove mighty kick
        }
        char = create_test_character(data)
        skills = char.skill_levels_by_role[CharacterClassRole.FIGHTER]
        assert 'mighty_kick' not in skills
    
    def test_skill_removal_with_zero_level(self, create_test_character, fighter_character_data):
        """Skills can be removed by setting level to 0."""
        data = fighter_character_data.copy()
        data['class']['fighter']['skills'] = {
            'mighty_kick': 0  # Remove by setting to 0
        }
        char = create_test_character(data)
        skills = char.skill_levels_by_role[CharacterClassRole.FIGHTER]
        assert 'mighty_kick' not in skills


class TestSkillsByClassProxy:
    """Tests for the skills_by_class property and proxy behavior."""
    
    def test_skills_by_class_returns_proxy(self, test_fighter):
        """skills_by_class should return a proxy object."""
        proxy = test_fighter.skills_by_class
        assert proxy is not None
    
    def test_skills_by_class_access_by_role(self, test_fighter):
        """Can access skills by CharacterClassRole."""
        class_skills = test_fighter.skills_by_class[CharacterClassRole.FIGHTER]
        assert class_skills is not None
    
    def test_skills_by_class_returns_character_skill(self, test_fighter):
        """Accessing a skill returns a CharacterSkill object."""
        from NextGenMUDApp.nondb_models.characters import CharacterSkill
        
        # First ensure the character has the skill
        test_fighter.skill_levels_by_role[CharacterClassRole.FIGHTER]['mighty_kick'] = 2
        
        skill = test_fighter.skills_by_class[CharacterClassRole.FIGHTER]['mighty_kick']
        assert isinstance(skill, CharacterSkill)
        assert skill.skill_level == 2
    
    def test_skills_by_class_normalizes_skill_names(self, test_fighter):
        """Skill names should be normalized (spaces, underscores, case)."""
        test_fighter.skill_levels_by_role[CharacterClassRole.FIGHTER]['mighty_kick'] = 1
        
        # All these should access the same skill
        skill1 = test_fighter.skills_by_class[CharacterClassRole.FIGHTER]['mighty_kick']
        skill2 = test_fighter.skills_by_class[CharacterClassRole.FIGHTER]['mighty kick']
        skill3 = test_fighter.skills_by_class[CharacterClassRole.FIGHTER]['MIGHTY_KICK']
        
        assert skill1.skill_level == skill2.skill_level == skill3.skill_level
    
    def test_skills_by_class_accepts_skill_object(self, test_fighter):
        """skills_by_class should accept Skill objects as keys."""
        from NextGenMUDApp.skills_fighter import Skills_Fighter
        
        test_fighter.skill_levels_by_role[CharacterClassRole.FIGHTER]['mighty_kick'] = 3
        
        skill = test_fighter.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK]
        assert skill.skill_level == 3


class TestCharacterResources:
    """Tests for HP, mana, and stamina calculations."""
    
    def test_fighter_has_stamina(self, test_fighter):
        """Fighter should have stamina based on class and level."""
        # After initialization, calculate resources
        test_fighter.calculate_max_stamina()
        test_fighter.current_stamina = test_fighter.max_stamina
        
        assert test_fighter.max_stamina > 0
    
    def test_mage_has_mana(self, test_mage):
        """Mage should have mana based on class and level."""
        test_mage.calculate_max_mana()
        test_mage.current_mana = test_mage.max_mana
        
        assert test_mage.max_mana > 0
    
    def test_use_mana_reduces_current(self, test_mage):
        """use_mana should reduce current mana."""
        test_mage.max_mana = 100
        test_mage.current_mana = 100
        
        result = test_mage.use_mana(20)
        
        assert result == True
        assert test_mage.current_mana == 80
    
    def test_use_mana_fails_if_insufficient(self, test_mage):
        """use_mana should fail if not enough mana."""
        test_mage.max_mana = 100
        test_mage.current_mana = 10
        
        result = test_mage.use_mana(20)
        
        assert result == False
        assert test_mage.current_mana == 10  # Unchanged
    
    def test_use_stamina_reduces_current(self, test_fighter):
        """use_stamina should reduce current stamina."""
        test_fighter.max_stamina = 100
        test_fighter.current_stamina = 100
        
        result = test_fighter.use_stamina(15)
        
        assert result == True
        assert test_fighter.current_stamina == 85


class TestCharacterFlags:
    """Tests for permanent and temporary character flags."""
    
    def test_add_perm_flag(self, test_fighter):
        """Should be able to add permanent flags."""
        from NextGenMUDApp.nondb_models.character_interface import PermanentCharacterFlags
        
        test_fighter.add_perm_flags(PermanentCharacterFlags.IS_PC)
        assert test_fighter.has_perm_flags(PermanentCharacterFlags.IS_PC)
    
    def test_add_temp_flag(self, test_fighter):
        """Should be able to add temporary flags."""
        from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags
        
        test_fighter.add_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        assert test_fighter.has_temp_flags(TemporaryCharacterFlags.IS_SITTING)
    
    def test_remove_temp_flag(self, test_fighter):
        """Should be able to remove temporary flags."""
        from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags
        
        test_fighter.add_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        test_fighter.remove_temp_flags(TemporaryCharacterFlags.IS_SITTING)
        assert not test_fighter.has_temp_flags(TemporaryCharacterFlags.IS_SITTING)
    
    def test_load_permanent_flags_from_yaml(self, create_test_character, base_character_data):
        """Permanent flags should be loaded from YAML. is_aggressive sets attitude=HOSTILE."""
        from NextGenMUDApp.nondb_models.actor_attitudes import ActorAttitude
        data = base_character_data.copy()
        data['permanent_flags'] = ['is_aggressive', 'is_undead']
        
        char = create_test_character(data)
        
        assert char.attitude == ActorAttitude.HOSTILE
        assert char.has_perm_flags(PermanentCharacterFlags.IS_UNDEAD)
    
    def test_new_permanent_flags_available(self, test_fighter):
        """All new permanent flags should be available."""
        # Test that new flags exist and can be added
        test_fighter.add_perm_flags(PermanentCharacterFlags.NO_WANDER)
        assert test_fighter.has_perm_flags(PermanentCharacterFlags.NO_WANDER)
        
        test_fighter.add_perm_flags(PermanentCharacterFlags.IS_SENTINEL)
        assert test_fighter.has_perm_flags(PermanentCharacterFlags.IS_SENTINEL)
        
        test_fighter.add_perm_flags(PermanentCharacterFlags.QUEST_GIVER)
        assert test_fighter.has_perm_flags(PermanentCharacterFlags.QUEST_GIVER)


class TestDamageMultipliers:
    """Tests for damage multiplier loading and usage."""
    
    def test_load_damage_multipliers_from_yaml(self, create_test_character, base_character_data):
        """Damage multipliers should be loaded from YAML."""
        from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType
        
        data = base_character_data.copy()
        data['damage_multipliers'] = {
            'fire': 0.5,
            'poison': 0,
            'cold': 2
        }
        
        char = create_test_character(data)
        
        assert char.damage_multipliers.profile[DamageType.FIRE] == 0.5
        assert char.damage_multipliers.profile[DamageType.POISON] == 0  # Immune
        assert char.damage_multipliers.profile[DamageType.COLD] == 2  # Vulnerable
    
    def test_immune_poison_flag_converts_to_multiplier(self, create_test_character, base_character_data):
        """Legacy immune_poison flag should convert to damage multiplier."""
        from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType
        
        data = base_character_data.copy()
        data['permanent_flags'] = ['immune_poison']
        
        char = create_test_character(data)
        
        # Should be immune (0 damage multiplier)
        assert char.damage_multipliers.profile[DamageType.POISON] == 0


class TestSavingThrowBonuses:
    """Tests for saving throw bonus system."""
    
    def test_load_saving_throw_bonuses_from_yaml(self, create_test_character, base_character_data):
        """Saving throw bonuses should be loaded from YAML."""
        data = base_character_data.copy()
        data['saving_throw_bonuses'] = {
            'will': 100,
            'fortitude': 50
        }
        
        char = create_test_character(data)
        
        assert char.saving_throw_bonuses.get('will') == 100
        assert char.saving_throw_bonuses.get('fortitude') == 50
        assert char.saving_throw_bonuses.get('reflex', 0) == 0  # Not set
    
    def test_saving_throw_bonus_dict_access(self, create_test_character, base_character_data):
        """saving_throw_bonuses dict should return correct values with case-insensitive keys."""
        data = base_character_data.copy()
        data['saving_throw_bonuses'] = {'will': 75}
        
        char = create_test_character(data)
        
        assert char.saving_throw_bonuses.get('will', 0) == 75
        assert char.saving_throw_bonuses.get('fortitude', 0) == 0  # Not set
    
    def test_immune_charm_converts_to_will_bonus(self, create_test_character, base_character_data):
        """Legacy immune_charm flag should convert to will save bonus."""
        data = base_character_data.copy()
        data['permanent_flags'] = ['immune_charm']
        
        char = create_test_character(data)
        
        assert char.saving_throw_bonuses.get('will') == 100
    
    def test_immune_fear_converts_to_will_bonus(self, create_test_character, base_character_data):
        """Legacy immune_fear flag should convert to will save bonus."""
        data = base_character_data.copy()
        data['permanent_flags'] = ['immune_fear']
        
        char = create_test_character(data)
        
        assert char.saving_throw_bonuses.get('will') == 100
    
    def test_multiple_immunity_flags_combine(self, create_test_character, base_character_data):
        """Multiple immunity flags should work together."""
        from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType
        
        data = base_character_data.copy()
        data['permanent_flags'] = ['immune_poison', 'immune_charm', 'immune_fear', 'is_undead']
        
        char = create_test_character(data)
        
        # Should have poison immunity
        assert char.damage_multipliers.profile[DamageType.POISON] == 0
        # Should have will save bonus
        assert char.saving_throw_bonuses.get('will') == 100
        # Should have undead flag
        assert char.has_perm_flags(PermanentCharacterFlags.IS_UNDEAD)


class TestClassBasedSaves:
    """Tests for the class-based saving throw system."""

    def test_get_class_base_save_fighter(self, create_test_character, base_character_data):
        """Fighter should have high fortitude, low will base save."""
        from NextGenMUDApp.constants import Constants
        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 5}}
        char = create_test_character(data)

        assert char.get_class_base_save('fortitude') == Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['fortitude']
        assert char.get_class_base_save('will') == Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['will']

    def test_get_class_base_save_mage(self, create_test_character, base_character_data):
        """Mage should have high will, low fortitude base save."""
        from NextGenMUDApp.constants import Constants
        data = base_character_data.copy()
        data['class'] = {'mage': {'level': 5}}
        char = create_test_character(data)

        assert char.get_class_base_save('will') == Constants.SAVING_THROW_BASES[CharacterClassRole.MAGE]['will']
        assert char.get_class_base_save('fortitude') == Constants.SAVING_THROW_BASES[CharacterClassRole.MAGE]['fortitude']

    def test_get_class_base_save_multiclass_takes_best(self, create_test_character, base_character_data):
        """Multiclass character should use the best base save across classes."""
        from NextGenMUDApp.constants import Constants
        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 5}, 'mage': {'level': 3}}
        data['class_priority'] = ['fighter', 'mage']
        char = create_test_character(data)

        fighter_fort = Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['fortitude']
        mage_fort = Constants.SAVING_THROW_BASES[CharacterClassRole.MAGE]['fortitude']
        assert char.get_class_base_save('fortitude') == max(fighter_fort, mage_fort)

        fighter_will = Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['will']
        mage_will = Constants.SAVING_THROW_BASES[CharacterClassRole.MAGE]['will']
        assert char.get_class_base_save('will') == max(fighter_will, mage_will)

    def test_get_save_attribute_maps_correctly(self, create_test_character, base_character_data):
        """get_save_attribute should return CON for fort, DEX for ref, WIS for will."""
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 5}}
        data['attributes'] = {
            'strength': 10, 'dexterity': 14, 'constitution': 16,
            'intelligence': 10, 'wisdom': 18, 'charisma': 10
        }
        char = create_test_character(data)

        assert char.get_save_attribute('fortitude') == 16   # CON
        assert char.get_save_attribute('reflex') == 14      # DEX
        assert char.get_save_attribute('will') == 18        # WIS

    def test_get_best_level(self, create_test_character, base_character_data):
        """get_best_level should return highest single class level."""
        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 8}, 'rogue': {'level': 3}}
        data['class_priority'] = ['fighter', 'rogue']
        char = create_test_character(data)

        assert char.get_best_level() == 8

    def test_attempt_save_equal_combatants(self, create_test_character, base_character_data):
        """Equal-level, equal-attr combatants should get class base save chance."""
        from NextGenMUDApp.constants import Constants
        from NextGenMUDApp.skills_core import Skill
        from unittest.mock import patch

        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 5}}
        data['attributes'] = {
            'strength': 10, 'dexterity': 10, 'constitution': 10,
            'intelligence': 10, 'wisdom': 10, 'charisma': 10
        }
        defender = create_test_character(data)

        attacker_data = base_character_data.copy()
        attacker_data['class'] = {'mage': {'level': 5}}
        attacker_data['attributes'] = data['attributes'].copy()
        attacker = create_test_character(attacker_data)

        skill = Skill(name='test_spell', base_class=CharacterClassRole.MAGE, save_difficulty=0)

        with patch('random.randint', return_value=1):
            save_chance, _ = defender.attempt_save('fortitude', attacker, skill, CharacterAttributes.INTELLIGENCE)
        expected = Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['fortitude']
        assert save_chance == expected

    def test_attempt_save_with_100_bonus_always_saves(self, create_test_character, base_character_data):
        """A 100% saving throw bonus should result in max save chance."""
        from NextGenMUDApp.constants import Constants
        from NextGenMUDApp.skills_core import Skill
        from unittest.mock import patch

        data = base_character_data.copy()
        data['saving_throw_bonuses'] = {'will': 100}
        data['class'] = {'fighter': {'level': 1}}
        defender = create_test_character(data)

        attacker_data = base_character_data.copy()
        attacker_data['class'] = {'mage': {'level': 10}}
        attacker = create_test_character(attacker_data)

        skill = Skill(name='dominate', base_class=CharacterClassRole.MAGE, save_difficulty=0)

        with patch('random.randint', return_value=1):
            save_chance, saved = defender.attempt_save('will', attacker, skill, CharacterAttributes.INTELLIGENCE)
        assert save_chance == Constants.SAVE_CHANCE_MAX
        assert saved is True

    def test_attempt_save_clamped_to_min(self, create_test_character, base_character_data):
        """Save chance should not drop below SAVE_CHANCE_MIN."""
        from NextGenMUDApp.constants import Constants
        from NextGenMUDApp.skills_core import Skill
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        from unittest.mock import patch

        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 1}}
        data['attributes'] = {
            'strength': 10, 'dexterity': 10, 'constitution': 1,
            'intelligence': 10, 'wisdom': 1, 'charisma': 10
        }
        defender = create_test_character(data)

        attacker_data = base_character_data.copy()
        attacker_data['class'] = {'mage': {'level': 50}}
        attacker_data['attributes'] = {
            'strength': 10, 'dexterity': 10, 'constitution': 10,
            'intelligence': 25, 'wisdom': 25, 'charisma': 10
        }
        attacker = create_test_character(attacker_data)

        skill = Skill(name='nuke', base_class=CharacterClassRole.MAGE, save_difficulty=20)

        with patch('random.randint', return_value=100):
            save_chance, _ = defender.attempt_save('will', attacker, skill, CharacterAttributes.INTELLIGENCE)
        assert save_chance == Constants.SAVE_CHANCE_MIN

    def test_attempt_save_clamped_to_max(self, create_test_character, base_character_data):
        """Save chance should not exceed SAVE_CHANCE_MAX (without bonus)."""
        from NextGenMUDApp.constants import Constants
        from NextGenMUDApp.skills_core import Skill
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        from unittest.mock import patch

        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 50}}
        data['attributes'] = {
            'strength': 25, 'dexterity': 25, 'constitution': 25,
            'intelligence': 25, 'wisdom': 25, 'charisma': 25
        }
        defender = create_test_character(data)

        attacker_data = base_character_data.copy()
        attacker_data['class'] = {'mage': {'level': 1}}
        attacker_data['attributes'] = {
            'strength': 1, 'dexterity': 1, 'constitution': 1,
            'intelligence': 1, 'wisdom': 1, 'charisma': 1
        }
        attacker = create_test_character(attacker_data)

        skill = Skill(name='cantrip', base_class=CharacterClassRole.MAGE, save_difficulty=0)

        with patch('random.randint', return_value=1):
            save_chance, _ = defender.attempt_save('fortitude', attacker, skill, CharacterAttributes.INTELLIGENCE)
        assert save_chance == Constants.SAVE_CHANCE_MAX

    def test_attempt_save_level_difference_matters(self, create_test_character, base_character_data):
        """Higher defender level should increase save chance via LEVEL_DIFF_MULTIPLIER."""
        from NextGenMUDApp.constants import Constants
        from NextGenMUDApp.skills_core import Skill
        from unittest.mock import patch

        base_attrs = {
            'strength': 10, 'dexterity': 10, 'constitution': 10,
            'intelligence': 10, 'wisdom': 10, 'charisma': 10
        }

        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 10}}
        data['attributes'] = base_attrs.copy()
        defender = create_test_character(data)

        attacker_data = base_character_data.copy()
        attacker_data['class'] = {'mage': {'level': 5}}
        attacker_data['attributes'] = base_attrs.copy()
        attacker = create_test_character(attacker_data)

        skill = Skill(name='test_spell', base_class=CharacterClassRole.MAGE, save_difficulty=0)

        with patch('random.randint', return_value=1):
            save_chance, _ = defender.attempt_save('fortitude', attacker, skill, CharacterAttributes.INTELLIGENCE)
        level_bonus = (10 - 5) * Constants.LEVEL_DIFF_MULTIPLIER  # 15
        expected = Constants.SAVING_THROW_BASES[CharacterClassRole.FIGHTER]['fortitude'] + level_bonus
        expected = max(Constants.SAVE_CHANCE_MIN, min(Constants.SAVE_CHANCE_MAX, expected))
        assert save_chance == expected