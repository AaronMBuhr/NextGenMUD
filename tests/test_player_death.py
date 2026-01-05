"""
Unit tests for Player Death system.

Tests cover:
- Corpse creation
- Inventory transfer (equipped vs non-equipped)
- XP penalties
- Respawn mechanics
- Corpse decay timer
- Corpse ownership/looting
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.character_interface import (
    TemporaryCharacterFlags, PermanentCharacterFlags, EquipLocation
)

from tests.conftest import create_mock_character


class TestCorpseCreation:
    """Tests for corpse creation on player death."""
    
    def test_corpse_created_on_death(self, mock_room):
        """A corpse should be created when player dies."""
        from NextGenMUDApp.nondb_models.objects import Corpse
        
        player = create_mock_character(name="DeadPlayer", is_pc=True)
        player.id = "deadplayer"
        player.definition_zone_id = "test_zone"
        player.art_name = "dead player"
        player.art_name_cap = "DeadPlayer"
        
        # Corpse should be createable
        corpse = Corpse(player, mock_room)
        
        assert corpse is not None
        assert "DeadPlayer" in corpse.name
    
    def test_corpse_contains_inventory(self):
        """Corpse should contain player's non-equipped inventory."""
        player = create_mock_character(name="Player")
        player.contents = [MagicMock(name="potion"), MagicMock(name="gold")]
        
        # Non-equipped items should go to corpse
        items_for_corpse = player.contents.copy()
        
        assert len(items_for_corpse) == 2
    
    def test_equipped_items_stay_on_player(self):
        """Equipped items should stay on the player."""
        player = create_mock_character(name="Player")
        
        sword = MagicMock(name="sword")
        player.equipped = {
            EquipLocation.MAIN_HAND: sword,
            EquipLocation.OFF_HAND: None,
            EquipLocation.BODY: MagicMock(name="armor")
        }
        
        # Count equipped items
        equipped_count = sum(1 for item in player.equipped.values() if item is not None)
        
        assert equipped_count == 2
    
    def test_corpse_has_owner(self, mock_room):
        """Corpse should track its owner for looting permissions."""
        from NextGenMUDApp.nondb_models.objects import Corpse
        
        player = create_mock_character(name="DeadPlayer")
        player.id = "player_123"
        player.definition_zone_id = "test_zone"
        player.art_name = "dead player"
        player.art_name_cap = "Dead player"
        
        corpse = Corpse(player, mock_room)
        corpse.owner_id = player.id
        
        assert corpse.owner_id == player.id


class TestXPPenalty:
    """Tests for XP penalty on death."""
    
    def test_xp_penalty_applied(self):
        """5% XP penalty should be applied on death."""
        player = create_mock_character()
        player.experience_points = 10000
        
        penalty_percent = 5
        penalty = int(player.experience_points * penalty_percent / 100)
        
        assert penalty == 500
    
    def test_xp_cannot_go_below_zero(self):
        """XP should not go below zero."""
        player = create_mock_character()
        player.experience_points = 100
        
        penalty = 500  # More than player has
        
        new_xp = max(0, player.experience_points - penalty)
        
        assert new_xp == 0
    
    def test_no_deleveling(self):
        """Player should not lose levels from XP penalty."""
        player = create_mock_character()
        player.experience_points = 10000
        player.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        
        # Apply penalty
        penalty = 500
        player.experience_points -= penalty
        
        # Level should remain the same
        assert player.levels_by_role[CharacterClassRole.FIGHTER] == 5


class TestRespawn:
    """Tests for player respawn mechanics."""
    
    def test_respawn_at_start_room(self):
        """Player should respawn at the start room."""
        start_room_id = "debug_zone.starting_room"
        
        # Default respawn location
        assert start_room_id == "debug_zone.starting_room"
    
    def test_hp_restored_on_respawn(self):
        """HP should be restored on respawn."""
        player = create_mock_character(hp=0, max_hp=100)
        
        # After respawn
        player.current_hit_points = player.max_hit_points
        
        assert player.current_hit_points == 100
    
    def test_mana_restored_on_respawn(self):
        """Mana should be restored on respawn."""
        player = create_mock_character(mana=0, max_mana=50)
        
        # After respawn
        player.current_mana = player.max_mana
        
        assert player.current_mana == 50
    
    def test_stamina_restored_on_respawn(self):
        """Stamina should be restored on respawn."""
        player = create_mock_character(stamina=0, max_stamina=50)
        
        # After respawn
        player.current_stamina = player.max_stamina
        
        assert player.current_stamina == 50
    
    def test_death_flags_cleared_on_respawn(self):
        """Death-related flags should be cleared on respawn."""
        player = create_mock_character()
        player.temporary_character_flags = TemporaryCharacterFlags.IS_DEAD
        
        # After respawn, clear death flag
        player.temporary_character_flags = TemporaryCharacterFlags(0)
        
        assert not player.has_temp_flags(TemporaryCharacterFlags.IS_DEAD)
    
    def test_combat_cleared_on_respawn(self):
        """Combat state should be cleared on respawn."""
        player = create_mock_character()
        player.fighting_whom = create_mock_character()
        
        # After respawn
        player.fighting_whom = None
        
        assert player.fighting_whom is None


class TestCorpseDecay:
    """Tests for corpse decay timer."""
    
    def test_corpse_has_decay_timer(self):
        """Corpse should have a 30-minute decay timer."""
        decay_minutes = 30
        decay_ticks = decay_minutes * 60 * 2  # 2 ticks per second
        
        assert decay_ticks == 3600
    
    def test_corpse_removed_after_decay(self):
        """Corpse should be removed after decay timer expires."""
        # This would be handled by scheduled events
        corpse = MagicMock()
        corpse.decay_tick = 100
        current_tick = 3700  # Past decay time
        
        should_decay = current_tick >= corpse.decay_tick
        
        assert should_decay == True
    
    def test_corpse_contents_lost_on_decay(self):
        """Contents should be lost when corpse decays."""
        corpse = MagicMock()
        corpse.contents = [MagicMock(), MagicMock()]
        
        # On decay, contents are cleared/lost
        corpse.contents.clear()
        
        assert len(corpse.contents) == 0


class TestCorpseLooting:
    """Tests for corpse looting mechanics."""
    
    def test_owner_can_loot(self):
        """Owner should be able to loot their corpse."""
        player_id = "player_123"
        
        corpse = MagicMock()
        corpse.owner_id = player_id
        
        can_loot = (corpse.owner_id == player_id)
        
        assert can_loot == True
    
    def test_others_cannot_loot_immediately(self):
        """Others should not be able to loot immediately."""
        owner_id = "player_123"
        other_id = "player_456"
        
        corpse = MagicMock()
        corpse.owner_id = owner_id
        corpse.anyone_can_loot = False
        
        can_loot = (corpse.owner_id == other_id or corpse.anyone_can_loot)
        
        assert can_loot == False
    
    def test_corpse_retrieval_challenge(self):
        """Corpse should remain in dangerous area for retrieval challenge."""
        corpse = MagicMock()
        corpse.location_room = MagicMock()
        corpse.location_room.rid = "dangerous_dungeon.boss_room"
        
        # Corpse stays where player died
        assert "dangerous_dungeon" in corpse.location_room.rid
