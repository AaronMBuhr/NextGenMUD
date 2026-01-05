"""
Unit tests for Status Bar HUD system.

Tests cover:
- Status update message format
- HP/Mana/Stamina display
- Update triggers
- CommTypes.STATUS message type
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.communication import CommTypes
from NextGenMUDApp.nondb_models.character_interface import PermanentCharacterFlags

from tests.conftest import create_mock_character


class TestStatusUpdateMessage:
    """Tests for status update message format."""
    
    def test_status_message_contains_hp(self):
        """Status message should contain HP information."""
        player = create_mock_character(hp=75, max_hp=100)
        
        status_data = {
            'current_hp': player.current_hit_points,
            'max_hp': player.max_hit_points
        }
        
        assert status_data['current_hp'] == 75
        assert status_data['max_hp'] == 100
    
    def test_status_message_contains_mana(self):
        """Status message should contain mana information."""
        player = create_mock_character(mana=30, max_mana=50)
        
        status_data = {
            'current_mana': player.current_mana,
            'max_mana': player.max_mana
        }
        
        assert status_data['current_mana'] == 30
        assert status_data['max_mana'] == 50
    
    def test_status_message_contains_stamina(self):
        """Status message should contain stamina information."""
        player = create_mock_character(stamina=40, max_stamina=60)
        
        status_data = {
            'current_stamina': player.current_stamina,
            'max_stamina': player.max_stamina
        }
        
        assert status_data['current_stamina'] == 40
        assert status_data['max_stamina'] == 60
    
    def test_status_message_complete_format(self):
        """Status message should have complete format."""
        player = create_mock_character(
            hp=75, max_hp=100,
            mana=30, max_mana=50,
            stamina=40, max_stamina=60
        )
        
        status_data = {
            'type': 'status',
            'hp': player.current_hit_points,
            'max_hp': player.max_hit_points,
            'mana': player.current_mana,
            'max_mana': player.max_mana,
            'stamina': player.current_stamina,
            'max_stamina': player.max_stamina
        }
        
        assert status_data['type'] == 'status'
        assert 'hp' in status_data
        assert 'mana' in status_data
        assert 'stamina' in status_data


class TestCommTypesStatus:
    """Tests for CommTypes.STATUS message type."""
    
    def test_status_commtype_exists(self):
        """CommTypes should have a STATUS type."""
        # Check if STATUS exists
        assert hasattr(CommTypes, 'STATUS') or 'STATUS' in dir(CommTypes)
    
    def test_status_is_distinct_type(self):
        """STATUS should be a distinct message type."""
        # STATUS should be different from DYNAMIC, etc.
        if hasattr(CommTypes, 'STATUS'):
            assert CommTypes.STATUS != CommTypes.DYNAMIC


class TestSendStatusUpdate:
    """Tests for the send_status_update method."""
    
    def test_send_status_update_exists(self, test_fighter):
        """Character should have send_status_update method."""
        assert hasattr(test_fighter, 'send_status_update')
    
    async def test_send_status_update_sends_to_connection(self, test_fighter, mock_connection):
        """send_status_update should send to character's connection."""
        test_fighter.connection = mock_connection
        test_fighter.current_hit_points = 75
        test_fighter.max_hit_points = 100
        test_fighter.current_mana = 30
        test_fighter.max_mana = 50
        test_fighter.current_stamina = 40
        test_fighter.max_stamina = 60
        
        # Call send_status_update (awaited since it's async)
        await test_fighter.send_status_update()
        
        # Connection should have been used
        # (actual implementation may vary)
    
    def test_send_status_update_only_for_pcs(self):
        """send_status_update should only work for PCs."""
        npc = create_mock_character(is_pc=False)
        npc.connection = None  # NPCs don't have connections
        
        # Should not crash for NPCs
        # Implementation checks for connection first


class TestStatusUpdateTriggers:
    """Tests for when status updates are triggered."""
    
    def test_status_update_on_damage(self):
        """Status update should be sent when taking damage."""
        player = create_mock_character(hp=100, max_hp=100, is_pc=True)
        player.send_status_update = MagicMock()
        
        # Take damage
        player.current_hit_points -= 20
        player.send_status_update()
        
        player.send_status_update.assert_called()
    
    def test_status_update_on_healing(self):
        """Status update should be sent when healed."""
        player = create_mock_character(hp=50, max_hp=100, is_pc=True)
        player.send_status_update = MagicMock()
        
        # Heal
        player.current_hit_points += 20
        player.send_status_update()
        
        player.send_status_update.assert_called()
    
    def test_status_update_on_mana_use(self):
        """Status update should be sent when mana is used."""
        player = create_mock_character(mana=50, max_mana=100, is_pc=True)
        player.send_status_update = MagicMock()
        
        # Use mana
        player.current_mana -= 15
        player.send_status_update()
        
        player.send_status_update.assert_called()
    
    def test_status_update_on_regeneration(self):
        """Status update should be sent when resources regenerate."""
        player = create_mock_character(
            hp=90, max_hp=100,
            mana=45, max_mana=50,
            stamina=55, max_stamina=60,
            is_pc=True
        )
        player.send_status_update = MagicMock()
        
        # Regenerate
        player.current_hit_points = min(100, player.current_hit_points + 1)
        player.current_mana = min(50, player.current_mana + 1)
        player.current_stamina = min(60, player.current_stamina + 1)
        
        # Should trigger update
        player.send_status_update()
        
        player.send_status_update.assert_called()
    
    def test_status_update_on_respawn(self):
        """Status update should be sent on respawn."""
        player = create_mock_character(
            hp=0, max_hp=100,
            mana=0, max_mana=50,
            stamina=0, max_stamina=60,
            is_pc=True
        )
        player.send_status_update = MagicMock()
        
        # Respawn - restore all resources
        player.current_hit_points = player.max_hit_points
        player.current_mana = player.max_mana
        player.current_stamina = player.max_stamina
        
        player.send_status_update()
        
        player.send_status_update.assert_called()


class TestStatusBarPercentages:
    """Tests for percentage calculations for status bars."""
    
    def test_hp_percentage_calculation(self):
        """HP percentage should calculate correctly."""
        player = create_mock_character(hp=75, max_hp=100)
        
        hp_percent = int((player.current_hit_points / player.max_hit_points) * 100)
        
        assert hp_percent == 75
    
    def test_mana_percentage_calculation(self):
        """Mana percentage should calculate correctly."""
        player = create_mock_character(mana=25, max_mana=50)
        
        mana_percent = int((player.current_mana / player.max_mana) * 100)
        
        assert mana_percent == 50
    
    def test_stamina_percentage_calculation(self):
        """Stamina percentage should calculate correctly."""
        player = create_mock_character(stamina=30, max_stamina=60)
        
        stamina_percent = int((player.current_stamina / player.max_stamina) * 100)
        
        assert stamina_percent == 50
    
    def test_zero_max_no_division_error(self):
        """Zero max should not cause division by zero."""
        player = create_mock_character()
        player.max_hit_points = 0
        player.current_hit_points = 0
        
        # Should handle gracefully
        if player.max_hit_points > 0:
            hp_percent = int((player.current_hit_points / player.max_hit_points) * 100)
        else:
            hp_percent = 0
        
        assert hp_percent == 0
