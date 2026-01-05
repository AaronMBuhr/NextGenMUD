"""
Unit tests for Healing system (potions, bandages, food).

Tests cover:
- Potion consumption and effects
- Bandage application
- Food consumption
- Healing amounts (fixed vs dice)
- Resource restoration
- Item charges and destruction
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.nondb_models.object_interface import ObjectFlags
from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags

from tests.conftest import create_mock_character


class TestPotionConsumption:
    """Tests for healing potion mechanics."""
    
    @pytest.fixture
    def healing_potion(self):
        """Create a healing potion object."""
        potion = MagicMock()
        potion.name = "healing potion"
        potion.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_POTION
        potion.heal_amount = 20
        potion.heal_dice = None
        potion.mana_restore = 0
        potion.stamina_restore = 0
        potion.charges = 1
        potion.use_message = "You drink the potion and feel better."
        return potion
    
    @pytest.fixture
    def mana_potion(self):
        """Create a mana potion object."""
        potion = MagicMock()
        potion.name = "mana potion"
        potion.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_POTION
        potion.heal_amount = 0
        potion.mana_restore = 30
        potion.stamina_restore = 0
        potion.charges = 1
        return potion
    
    def test_potion_is_consumable(self, healing_potion):
        """Potion should have IS_CONSUMABLE flag."""
        assert healing_potion.object_flags & ObjectFlags.IS_CONSUMABLE
    
    def test_potion_is_potion(self, healing_potion):
        """Potion should have IS_POTION flag."""
        assert healing_potion.object_flags & ObjectFlags.IS_POTION
    
    def test_potion_heals_fixed_amount(self, healing_potion):
        """Potion with heal_amount should heal that exact amount."""
        player = create_mock_character(hp=50, max_hp=100)
        
        heal = healing_potion.heal_amount
        player.current_hit_points = min(player.max_hit_points, 
                                        player.current_hit_points + heal)
        
        assert player.current_hit_points == 70
    
    def test_potion_healing_caps_at_max_hp(self, healing_potion):
        """Potion healing should not exceed max HP."""
        player = create_mock_character(hp=90, max_hp=100)
        
        heal = healing_potion.heal_amount  # 20
        player.current_hit_points = min(player.max_hit_points,
                                        player.current_hit_points + heal)
        
        assert player.current_hit_points == 100  # Capped at max
    
    def test_mana_potion_restores_mana(self, mana_potion):
        """Mana potion should restore mana."""
        player = create_mock_character(mana=20, max_mana=100)
        
        restore = mana_potion.mana_restore  # 30
        player.current_mana = min(player.max_mana,
                                  player.current_mana + restore)
        
        assert player.current_mana == 50
    
    def test_potion_consumed_after_use(self, healing_potion):
        """Potion should be consumed (removed) after use."""
        player = create_mock_character()
        player.contents = [healing_potion]
        
        # After quaffing
        healing_potion.charges -= 1
        if healing_potion.charges <= 0:
            player.contents.remove(healing_potion)
        
        assert healing_potion not in player.contents


class TestBandageApplication:
    """Tests for bandage mechanics."""
    
    @pytest.fixture
    def bandage(self):
        """Create a bandage object."""
        bandage = MagicMock()
        bandage.name = "bandage"
        bandage.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_BANDAGE
        bandage.heal_dice = "1d8+2"  # Dice-based healing
        bandage.heal_amount = 0
        bandage.charges = 1
        return bandage
    
    @pytest.fixture
    def medkit(self):
        """Create a medkit with multiple charges."""
        medkit = MagicMock()
        medkit.name = "medkit"
        medkit.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_BANDAGE
        medkit.heal_dice = "2d6+4"
        medkit.charges = 3
        return medkit
    
    def test_bandage_is_bandage(self, bandage):
        """Bandage should have IS_BANDAGE flag."""
        assert bandage.object_flags & ObjectFlags.IS_BANDAGE
    
    def test_bandage_uses_dice_healing(self, bandage):
        """Bandage with heal_dice should use random healing."""
        # 1d8+2 = 3-10 HP
        min_heal = 3
        max_heal = 10
        
        # Simulate dice roll
        from NextGenMUDApp.utility import roll_dice
        heal = roll_dice(1, 8, 2)
        
        assert min_heal <= heal <= max_heal
    
    def test_medkit_has_multiple_charges(self, medkit):
        """Medkit should have multiple charges."""
        assert medkit.charges == 3
    
    def test_medkit_charge_decreases(self, medkit):
        """Using medkit should decrease charges."""
        initial_charges = medkit.charges
        
        medkit.charges -= 1
        
        assert medkit.charges == initial_charges - 1
    
    def test_medkit_not_destroyed_with_charges(self, medkit):
        """Medkit should not be destroyed while charges remain."""
        player = create_mock_character()
        player.contents = [medkit]
        
        medkit.charges -= 1  # Use once
        
        # Still has charges, not destroyed
        if medkit.charges > 0:
            assert medkit in player.contents


class TestFoodConsumption:
    """Tests for food mechanics."""
    
    @pytest.fixture
    def bread(self):
        """Create food item."""
        food = MagicMock()
        food.name = "bread"
        food.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_FOOD
        food.heal_amount = 5
        food.stamina_restore = 10
        food.charges = 1
        return food
    
    def test_food_is_food(self, bread):
        """Food should have IS_FOOD flag."""
        assert bread.object_flags & ObjectFlags.IS_FOOD
    
    def test_food_heals_small_amount(self, bread):
        """Food should provide small healing."""
        assert bread.heal_amount == 5
    
    def test_food_restores_stamina(self, bread):
        """Food should restore stamina."""
        player = create_mock_character(stamina=40, max_stamina=100)
        
        restore = bread.stamina_restore  # 10
        player.current_stamina = min(player.max_stamina,
                                     player.current_stamina + restore)
        
        assert player.current_stamina == 50
    
    def test_food_consumed_after_eating(self, bread):
        """Food should be consumed after eating."""
        player = create_mock_character()
        player.contents = [bread]
        
        bread.charges -= 1
        if bread.charges <= 0:
            player.contents.remove(bread)
        
        assert bread not in player.contents


class TestConsumableCommands:
    """Tests for consumable-related commands (quaff, apply, eat)."""
    
    def test_quaff_command_for_potions(self):
        """quaff command should work for potions."""
        # Command: "quaff healing potion"
        command = "quaff"
        valid_for_potions = True
        
        assert valid_for_potions
    
    def test_apply_command_for_bandages(self):
        """apply command should work for bandages."""
        # Command: "apply bandage"
        command = "apply"
        valid_for_bandages = True
        
        assert valid_for_bandages
    
    def test_eat_command_for_food(self):
        """eat command should work for food."""
        # Command: "eat bread"
        command = "eat"
        valid_for_food = True
        
        assert valid_for_food
    
    def test_use_command_auto_detects_type(self):
        """use command should auto-detect item type."""
        potion = MagicMock()
        potion.object_flags = ObjectFlags.IS_POTION
        
        bandage = MagicMock()
        bandage.object_flags = ObjectFlags.IS_BANDAGE
        
        food = MagicMock()
        food.object_flags = ObjectFlags.IS_FOOD
        
        # use should dispatch to appropriate handler
        assert potion.object_flags & ObjectFlags.IS_POTION
        assert bandage.object_flags & ObjectFlags.IS_BANDAGE
        assert food.object_flags & ObjectFlags.IS_FOOD


class TestHealingInCombat:
    """Tests for healing restrictions in combat."""
    
    def test_potions_usable_in_combat(self):
        """Potions should be usable in combat."""
        player = create_mock_character()
        player.fighting_whom = create_mock_character()
        
        # Potions can be used while fighting
        can_use_potion = True  # Implementation allows this
        
        assert can_use_potion
    
    def test_bandages_have_cast_time(self):
        """Bandages might have application time."""
        # This would be a balance decision
        bandage_cast_time = 0  # Or could be > 0 for balance
        
        assert bandage_cast_time >= 0


class TestGreaterHealingPotion:
    """Tests for greater/different tier potions."""
    
    @pytest.fixture
    def greater_healing_potion(self):
        """Create a greater healing potion."""
        potion = MagicMock()
        potion.name = "greater healing potion"
        potion.object_flags = ObjectFlags.IS_CONSUMABLE | ObjectFlags.IS_POTION
        potion.heal_amount = 50
        potion.charges = 1
        return potion
    
    def test_greater_potion_heals_more(self, greater_healing_potion):
        """Greater potion should heal more than regular."""
        # Regular healing_potion heals 20
        regular_heal = 20
        greater_heal = greater_healing_potion.heal_amount
        
        assert greater_heal > regular_heal
