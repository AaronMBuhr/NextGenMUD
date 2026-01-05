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

from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes


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
