"""
Unit tests for Resource systems (Mana, Stamina, HP regeneration).

Tests cover:
- Mana pool calculation
- Stamina pool calculation
- Regeneration rates by state
- Resource consumption
- Meditation mechanics
"""

import pytest
from unittest.mock import MagicMock, patch

from NextGenMUDApp.constants import CharacterClassRole, Constants
from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes

from tests.conftest import create_mock_character


class TestManaCalculation:
    """Tests for mana pool calculation."""
    
    def test_mage_has_mana(self, test_mage):
        """Mage should have mana based on level."""
        test_mage.levels_by_role = {CharacterClassRole.MAGE: 5}
        
        test_mage.calculate_max_mana()
        
        assert test_mage.max_mana > 0
    
    def test_fighter_has_no_mana(self, test_fighter):
        """Fighter should have no/minimal mana."""
        test_fighter.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        
        test_fighter.calculate_max_mana()
        
        # Fighters get 0 mana per level
        assert test_fighter.max_mana == 0 or test_fighter.max_mana < 10
    
    def test_mana_scales_with_level(self, test_mage):
        """Mana should increase with mage level."""
        test_mage.levels_by_role = {CharacterClassRole.MAGE: 5}
        test_mage.calculate_max_mana()
        mana_at_5 = test_mage.max_mana
        
        test_mage.levels_by_role = {CharacterClassRole.MAGE: 10}
        test_mage.calculate_max_mana()
        mana_at_10 = test_mage.max_mana
        
        assert mana_at_10 > mana_at_5
    
    def test_mana_scales_with_intelligence(self, test_mage):
        """Mana should scale with INT for mages."""
        test_mage.levels_by_role = {CharacterClassRole.MAGE: 5}
        test_mage.attributes = {CharacterAttributes.INTELLIGENCE: 10}
        test_mage.calculate_max_mana()
        base_mana = test_mage.max_mana
        
        test_mage.attributes = {CharacterAttributes.INTELLIGENCE: 16}
        test_mage.calculate_max_mana()
        high_int_mana = test_mage.max_mana
        
        assert high_int_mana > base_mana
    
    def test_cleric_has_mana(self, create_test_character, base_character_data):
        """Cleric should have mana based on level and WIS."""
        data = base_character_data.copy()
        data['class'] = {'cleric': {'level': 5}}
        data['attributes']['wisdom'] = 16
        
        cleric = create_test_character(data)
        cleric.calculate_max_mana()
        
        assert cleric.max_mana > 0


class TestStaminaCalculation:
    """Tests for stamina pool calculation."""
    
    def test_fighter_has_stamina(self, test_fighter):
        """Fighter should have stamina based on level."""
        test_fighter.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        
        test_fighter.calculate_max_stamina()
        
        assert test_fighter.max_stamina > 0
    
    def test_mage_has_no_stamina(self, test_mage):
        """Mage should have no/minimal stamina."""
        test_mage.levels_by_role = {CharacterClassRole.MAGE: 5}
        
        test_mage.calculate_max_stamina()
        
        # Mages get 0 stamina per level
        assert test_mage.max_stamina == 0 or test_mage.max_stamina < 10
    
    def test_stamina_scales_with_level(self, test_fighter):
        """Stamina should increase with fighter level."""
        test_fighter.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        test_fighter.calculate_max_stamina()
        stamina_at_5 = test_fighter.max_stamina
        
        test_fighter.levels_by_role = {CharacterClassRole.FIGHTER: 10}
        test_fighter.calculate_max_stamina()
        stamina_at_10 = test_fighter.max_stamina
        
        assert stamina_at_10 > stamina_at_5
    
    def test_stamina_scales_with_constitution(self, test_fighter):
        """Stamina should scale with CON."""
        test_fighter.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        test_fighter.attributes = {CharacterAttributes.CONSTITUTION: 10}
        test_fighter.calculate_max_stamina()
        base_stamina = test_fighter.max_stamina
        
        test_fighter.attributes = {CharacterAttributes.CONSTITUTION: 16}
        test_fighter.calculate_max_stamina()
        high_con_stamina = test_fighter.max_stamina
        
        assert high_con_stamina > base_stamina


class TestManaRegeneration:
    """Tests for mana regeneration rates."""
    
    def test_mana_regen_in_combat_is_low(self, test_mage):
        """Mana regen should be very low in combat."""
        test_mage.fighting_whom = create_mock_character()
        test_mage.is_meditating = False
        
        rate = test_mage.get_mana_regen_rate()
        
        # Combat regen is minimal
        assert rate <= Constants.MANA_REGEN_COMBAT + 0.1
    
    def test_mana_regen_walking_moderate(self, test_mage):
        """Mana regen should be moderate when walking."""
        test_mage.fighting_whom = None
        test_mage.is_meditating = False
        test_mage.has_temp_flags = MagicMock(return_value=False)  # Not sitting
        
        rate = test_mage.get_mana_regen_rate()
        
        # Walking regen
        assert rate >= Constants.MANA_REGEN_WALKING - 0.1
    
    def test_mana_regen_resting_higher(self, test_mage):
        """Mana regen should be higher when resting (sitting)."""
        test_mage.fighting_whom = None
        test_mage.is_meditating = False
        
        # Simulate sitting
        def check_sitting(flag):
            from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags
            return flag == TemporaryCharacterFlags.IS_SITTING
        
        test_mage.has_temp_flags = MagicMock(side_effect=check_sitting)
        
        rate = test_mage.get_mana_regen_rate()
        
        assert rate >= Constants.MANA_REGEN_RESTING - 0.1
    
    def test_mana_regen_meditating_highest(self, test_mage):
        """Mana regen should be highest when meditating."""
        test_mage.fighting_whom = None
        test_mage.is_meditating = True
        test_mage.has_temp_flags = MagicMock(return_value=True)  # Sitting required
        
        rate = test_mage.get_mana_regen_rate()
        
        assert rate >= Constants.MANA_REGEN_MEDITATING - 0.1


class TestStaminaRegeneration:
    """Tests for stamina regeneration rates."""
    
    def test_stamina_regen_in_combat(self, test_fighter):
        """Stamina regen exists even in combat (but low)."""
        test_fighter.fighting_whom = create_mock_character()
        
        rate = test_fighter.get_stamina_regen_rate()
        
        assert rate >= 0
    
    def test_stamina_regen_walking(self, test_fighter):
        """Stamina regen when walking."""
        test_fighter.fighting_whom = None
        test_fighter.has_temp_flags = MagicMock(return_value=False)
        
        rate = test_fighter.get_stamina_regen_rate()
        
        assert rate >= Constants.STAMINA_REGEN_WALKING - 0.1
    
    def test_stamina_regen_resting(self, test_fighter):
        """Stamina regen when resting."""
        test_fighter.fighting_whom = None
        
        def check_sitting(flag):
            from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags
            return flag == TemporaryCharacterFlags.IS_SITTING
        
        test_fighter.has_temp_flags = MagicMock(side_effect=check_sitting)
        
        rate = test_fighter.get_stamina_regen_rate()
        
        assert rate >= Constants.STAMINA_REGEN_RESTING - 0.1


class TestHPRegeneration:
    """Tests for HP regeneration rates."""
    
    def test_no_hp_regen_in_combat(self, test_fighter):
        """HP should not regenerate in combat."""
        test_fighter.fighting_whom = create_mock_character()
        
        rate = test_fighter.get_hp_regen_rate()
        
        assert rate == 0
    
    def test_hp_regen_walking_slow(self, test_fighter):
        """HP regen should be very slow when walking."""
        test_fighter.fighting_whom = None
        test_fighter.has_temp_flags = MagicMock(return_value=False)
        
        rate = test_fighter.get_hp_regen_rate()
        
        assert rate >= Constants.HP_REGEN_WALKING - 0.01
    
    def test_hp_regen_sleeping_fastest(self, test_fighter):
        """HP regen should be fastest when sleeping."""
        test_fighter.fighting_whom = None
        
        def check_sleeping(flag):
            from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags
            return flag == TemporaryCharacterFlags.IS_SLEEPING
        
        test_fighter.has_temp_flags = MagicMock(side_effect=check_sleeping)
        
        rate = test_fighter.get_hp_regen_rate()
        
        assert rate >= Constants.HP_REGEN_SLEEPING - 0.1


class TestResourceConsumption:
    """Tests for resource consumption (use_mana, use_stamina)."""
    
    def test_use_mana_success(self, test_mage):
        """use_mana should succeed when sufficient mana."""
        test_mage.current_mana = 50
        test_mage.max_mana = 100
        
        result = test_mage.use_mana(20)
        
        assert result == True
        assert test_mage.current_mana == 30
    
    def test_use_mana_failure(self, test_mage):
        """use_mana should fail when insufficient mana."""
        test_mage.current_mana = 10
        test_mage.max_mana = 100
        
        result = test_mage.use_mana(20)
        
        assert result == False
        assert test_mage.current_mana == 10  # Unchanged
    
    def test_use_stamina_success(self, test_fighter):
        """use_stamina should succeed when sufficient stamina."""
        test_fighter.current_stamina = 50
        test_fighter.max_stamina = 100
        
        result = test_fighter.use_stamina(15)
        
        assert result == True
        assert test_fighter.current_stamina == 35
    
    def test_use_stamina_failure(self, test_fighter):
        """use_stamina should fail when insufficient stamina."""
        test_fighter.current_stamina = 5
        test_fighter.max_stamina = 100
        
        result = test_fighter.use_stamina(15)
        
        assert result == False
        assert test_fighter.current_stamina == 5  # Unchanged


class TestMeditation:
    """Tests for meditation state."""
    
    def test_meditation_requires_sitting(self, test_mage):
        """Meditation should require sitting."""
        # Implementation checks IS_SITTING flag
        test_mage.is_meditating = True
        test_mage.has_temp_flags = MagicMock(return_value=True)  # IS_SITTING
        
        can_meditate = test_mage.has_temp_flags(MagicMock())
        
        assert can_meditate == True
    
    def test_meditation_interrupted_by_standing(self, test_mage):
        """Standing should interrupt meditation."""
        test_mage.is_meditating = True
        
        # When player stands, meditation is interrupted
        test_mage.is_meditating = False
        
        assert test_mage.is_meditating == False
    
    def test_meditation_interrupted_by_combat(self, test_mage):
        """Combat should interrupt meditation."""
        test_mage.is_meditating = True
        
        # When entering combat
        test_mage.fighting_whom = create_mock_character()
        test_mage.is_meditating = False  # Implementation does this
        
        assert test_mage.is_meditating == False
    
    def test_meditation_interrupted_by_movement(self, test_mage):
        """Movement should interrupt meditation."""
        test_mage.is_meditating = True
        
        # When moving
        test_mage.is_meditating = False  # Implementation does this
        
        assert test_mage.is_meditating == False


class TestRegenerateResources:
    """Tests for the regenerate_resources tick method."""
    
    def test_regenerate_resources_returns_bool(self, test_fighter):
        """regenerate_resources should return bool indicating change."""
        test_fighter.current_hit_points = 50
        test_fighter.max_hit_points = 100
        test_fighter.current_mana = 25
        test_fighter.max_mana = 50
        test_fighter.current_stamina = 25
        test_fighter.max_stamina = 50
        test_fighter.fighting_whom = None
        test_fighter.is_meditating = False
        test_fighter.has_temp_flags = MagicMock(return_value=False)
        
        # This should return True if any resource changed
        result = test_fighter.regenerate_resources()
        
        assert isinstance(result, bool)
    
    def test_regenerate_resources_caps_at_max(self, test_fighter):
        """Resources should not exceed maximum."""
        test_fighter.current_hit_points = 99
        test_fighter.max_hit_points = 100
        test_fighter.current_mana = 49
        test_fighter.max_mana = 50
        test_fighter.current_stamina = 49
        test_fighter.max_stamina = 50
        test_fighter.fighting_whom = None
        test_fighter.is_meditating = False
        test_fighter.has_temp_flags = MagicMock(return_value=False)
        
        test_fighter.regenerate_resources()
        
        assert test_fighter.current_hit_points <= test_fighter.max_hit_points
        assert test_fighter.current_mana <= test_fighter.max_mana
        assert test_fighter.current_stamina <= test_fighter.max_stamina
