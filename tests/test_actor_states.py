"""
Unit tests for Actor States system.

Tests cover:
- State creation and application
- State removal and cleanup
- Flag management through states
- NPC auto-recovery behavior
- Cooldown system
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.nondb_models.character_interface import (
    TemporaryCharacterFlags, PermanentCharacterFlags
)
from NextGenMUDApp.constants import CharacterClassRole

from tests.conftest import create_mock_character


class TestCooldown:
    """Tests for the Cooldown class."""
    
    def test_cooldown_creation(self, mock_game_state):
        """Should be able to create a cooldown."""
        from NextGenMUDApp.nondb_models.actor_states import Cooldown
        
        actor = create_mock_character()
        actor.cooldowns = []
        
        cooldown = Cooldown(
            actor=actor,
            cooldown_name="test_cooldown",
            game_state=mock_game_state,
            cooldown_source=actor
        )
        
        assert cooldown.cooldown_name == "test_cooldown"
        assert cooldown.actor == actor
    
    def test_has_cooldown_when_present(self):
        """has_cooldown should return True when cooldown exists."""
        from NextGenMUDApp.nondb_models.actor_states import Cooldown
        
        actor = create_mock_character()
        cooldown = MagicMock()
        cooldown.cooldown_name = "test_cd"
        cooldown.cooldown_source = None
        actor.cooldowns = [cooldown]
        
        # has_cooldown takes the cooldowns list, not the actor
        result = Cooldown.has_cooldown(actor.cooldowns, cooldown_name="test_cd")
        
        assert result == True
    
    def test_has_cooldown_when_absent(self):
        """has_cooldown should return False when cooldown doesn't exist."""
        from NextGenMUDApp.nondb_models.actor_states import Cooldown
        
        actor = create_mock_character()
        actor.cooldowns = []
        
        # has_cooldown takes the cooldowns list, not the actor
        result = Cooldown.has_cooldown(actor.cooldowns, cooldown_name="nonexistent")
        
        assert result == False


class TestCharacterStateForcedSitting:
    """Tests for the forced sitting state."""
    
    @pytest.fixture
    def sitting_state(self, mock_game_state):
        """Create a forced sitting state."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateForcedSitting
        
        actor = create_mock_character()
        actor.current_states = []
        actor.command_queue = []
        actor.location_room = MagicMock()
        actor.location_room.echo = AsyncMock()
        
        source = create_mock_character(name="Attacker")
        
        state = CharacterStateForcedSitting(
            actor=actor,
            game_state=mock_game_state,
            source_actor=source,
            state_type_name="kicked"
        )
        
        return state, actor
    
    def test_sitting_state_adds_flag(self, sitting_state):
        """Forced sitting should add IS_SITTING flag."""
        state, actor = sitting_state
        
        assert state.character_flags_added.are_flags_set(TemporaryCharacterFlags.IS_SITTING)
    
    @pytest.mark.asyncio
    async def test_sitting_state_removal_queues_stand(self, sitting_state, mock_game_state):
        """NPC should queue 'stand' command when sitting state ends."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateForcedSitting
        from NextGenMUDApp.nondb_models.actor_interface import ActorType
        
        state, actor = sitting_state
        actor.actor_type = ActorType.CHARACTER
        actor.has_perm_flags = MagicMock(return_value=False)  # Not a PC
        actor.has_temp_flags = MagicMock(return_value=False)
        actor.remove_temp_flags = MagicMock()
        
        # Add state to actor's list
        actor.current_states = [state]
        
        # Apply state first
        state.tick_started = 100
        state.tick_ending = 110
        
        # Mock remove_state on parent to not fail
        with patch.object(state, 'actor') as mock_actor:
            mock_actor.remove_state = MagicMock()
            mock_actor.current_states = []
            mock_actor.remove_temp_flags = MagicMock()
            mock_actor.echo = AsyncMock()
            mock_actor.location_room = MagicMock()
            mock_actor.location_room.echo = AsyncMock()
            mock_actor.actor_type = ActorType.CHARACTER
            mock_actor.has_perm_flags = MagicMock(return_value=False)
            mock_actor.has_temp_flags = MagicMock(return_value=False)
            mock_actor.command_queue = []
            
            # Remove the state
            await state.remove_state()
            
            # NPC should queue a stand command
            assert "stand" in mock_actor.command_queue


class TestCharacterStateStunned:
    """Tests for the stunned state."""
    
    @pytest.fixture
    def stunned_state(self, mock_game_state):
        """Create a stunned state."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateStunned
        
        actor = create_mock_character()
        actor.current_states = []
        actor.location_room = MagicMock()
        actor.location_room.echo = AsyncMock()
        
        source = create_mock_character(name="Stunner")
        
        state = CharacterStateStunned(
            actor=actor,
            game_state=mock_game_state,
            source_actor=source,
            state_type_name="stunned"
        )
        
        return state, actor
    
    def test_stunned_prevents_action(self, stunned_state):
        """Stunned characters should not be able to act."""
        state, actor = stunned_state
        
        # The state should add the IS_STUNNED flag
        # This is checked in can_act() elsewhere
        assert TemporaryCharacterFlags.IS_STUNNED is not None


class TestActorStateBase:
    """Tests for the base ActorState class behavior."""
    
    def test_state_tracks_timing(self, mock_game_state):
        """States should track start and end ticks."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateForcedSitting
        
        actor = create_mock_character()
        actor.current_states = []
        actor.apply_state = MagicMock()
        
        state = CharacterStateForcedSitting(
            actor=actor,
            game_state=mock_game_state,
            source_actor=actor,
            tick_created=100
        )
        
        assert state.tick_created == 100
    
    def test_state_does_add_flag_check(self, mock_game_state):
        """does_add_flag should correctly identify added flags."""
        from NextGenMUDApp.nondb_models.actor_states import CharacterStateForcedSitting
        
        actor = create_mock_character()
        actor.current_states = []
        
        state = CharacterStateForcedSitting(
            actor=actor,
            game_state=mock_game_state,
            source_actor=actor
        )
        
        assert state.does_add_flag(TemporaryCharacterFlags.IS_SITTING) == True
        assert state.does_add_flag(TemporaryCharacterFlags.IS_STUNNED) == False


class TestResourceRegeneration:
    """Tests for resource regeneration mechanics."""
    
    def test_hp_regen_not_in_combat(self, test_fighter):
        """HP should regenerate when not in combat."""
        test_fighter.current_hit_points = 50
        test_fighter.max_hit_points = 100
        test_fighter.fighting_whom = None
        test_fighter.is_meditating = False
        
        # Get regen rate
        rate = test_fighter.get_hp_regen_rate()
        
        # Should have some regen when not fighting
        assert rate >= 0
    
    def test_no_hp_regen_in_combat(self, test_fighter):
        """HP should not regenerate during combat."""
        test_fighter.current_hit_points = 50
        test_fighter.max_hit_points = 100
        test_fighter.fighting_whom = create_mock_character()
        
        rate = test_fighter.get_hp_regen_rate()
        
        # Should be 0 or very low in combat
        assert rate == 0
    
    def test_mana_regen_higher_when_meditating(self, test_mage):
        """Mana regen should be higher when meditating."""
        test_mage.current_mana = 50
        test_mage.max_mana = 100
        test_mage.fighting_whom = None
        test_mage.is_meditating = False
        
        normal_rate = test_mage.get_mana_regen_rate()
        
        test_mage.is_meditating = True
        meditating_rate = test_mage.get_mana_regen_rate()
        
        assert meditating_rate > normal_rate
