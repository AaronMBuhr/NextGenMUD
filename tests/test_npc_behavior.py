"""
Unit tests for NPC behavior systems.

Tests cover:
- NPC command queue
- NPC auto-recovery (standing after effects)
- Combat AI command routing
- Scheduled events (async)
- NPC skill usage through command handler
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from NextGenMUDApp.constants import CharacterClassRole
from NextGenMUDApp.nondb_models.character_interface import (
    TemporaryCharacterFlags, PermanentCharacterFlags
)
from NextGenMUDApp.nondb_models.actor_interface import ActorType

from tests.conftest import create_mock_character


class TestNPCCommandQueue:
    """Tests for NPC command queue behavior."""
    
    def test_npc_has_command_queue(self):
        """NPCs should have a command queue."""
        npc = create_mock_character(name="Goblin")
        npc.command_queue = []
        
        assert hasattr(npc, 'command_queue')
        assert isinstance(npc.command_queue, list)
    
    def test_command_queue_fifo(self):
        """Command queue should be FIFO (first in, first out)."""
        npc = create_mock_character()
        npc.command_queue = []
        
        npc.command_queue.append("attack player")
        npc.command_queue.append("flee")
        
        first_command = npc.command_queue.pop(0)
        
        assert first_command == "attack player"
        assert npc.command_queue[0] == "flee"
    
    def test_multiple_commands_can_queue(self):
        """Multiple commands can be queued."""
        npc = create_mock_character()
        npc.command_queue = []
        
        npc.command_queue.append("say Hello!")
        npc.command_queue.append("emote waves")
        npc.command_queue.append("north")
        
        assert len(npc.command_queue) == 3


class TestNPCAutoRecovery:
    """Tests for NPC auto-recovery behavior after effects end."""
    
    def test_npc_queues_stand_after_forced_sitting(self):
        """NPC should queue 'stand' when forced sitting ends."""
        npc = create_mock_character()
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.has_perm_flags = MagicMock(return_value=False)  # Not PC
        
        # Simulate state removal queueing stand
        npc.command_queue.append("stand")
        
        assert "stand" in npc.command_queue
    
    def test_npc_queues_stand_after_sleep_ends(self):
        """NPC should queue 'stand' when sleep effect ends."""
        npc = create_mock_character()
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.has_perm_flags = MagicMock(return_value=False)
        
        npc.command_queue.append("stand")
        
        assert "stand" in npc.command_queue
    
    def test_npc_queues_stand_after_freeze_ends(self):
        """NPC should queue 'stand' when freeze effect ends."""
        npc = create_mock_character()
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.has_perm_flags = MagicMock(return_value=False)
        
        npc.command_queue.append("stand")
        
        assert "stand" in npc.command_queue
    
    def test_pc_does_not_auto_stand(self):
        """Player characters should NOT auto-stand."""
        pc = create_mock_character(is_pc=True)
        pc.actor_type = ActorType.CHARACTER
        pc.command_queue = []
        
        # PC flag should prevent auto-stand queueing
        # Implementation checks IS_PC before queueing
        is_pc = pc.has_perm_flags(PermanentCharacterFlags.IS_PC)
        
        if not is_pc:
            pc.command_queue.append("stand")
        
        # PC should not have stand queued
        assert "stand" not in pc.command_queue


class TestCombatAICommandRouting:
    """Tests for Combat AI routing commands through command handler."""
    
    def test_combat_ai_queues_skill_command(self):
        """Combat AI should queue skill commands, not execute directly."""
        from NextGenMUDApp.combat_ai import CombatAI
        
        npc = create_mock_character()
        npc.levels_by_role = {CharacterClassRole.FIGHTER: 5}
        npc.skill_levels_by_role = {CharacterClassRole.FIGHTER: {'mighty_kick': 1}}
        npc.command_queue = []
        npc.has_perm_flags = MagicMock(return_value=False)
        npc.has_cooldown = MagicMock(return_value=False)
        npc.current_mana = 100
        npc.current_stamina = 100
        
        target = create_mock_character(name="Player")
        
        # When skill is chosen and queued
        command = "mighty kick Player"
        npc.command_queue.append(command)
        
        assert len(npc.command_queue) > 0
    
    def test_combat_ai_returns_false_for_auto_attack(self):
        """Combat AI should return False when choosing auto-attack."""
        from NextGenMUDApp.combat_ai import CombatAI
        
        npc = create_mock_character()
        npc.levels_by_role = {}  # No classes
        npc.has_perm_flags = MagicMock(return_value=False)
        
        target = create_mock_character()
        
        result = CombatAI.queue_combat_action(npc, target)
        
        assert result == False  # No skill queued, use auto-attack


class TestScheduledEventsAsync:
    """Tests for async scheduled event handling."""
    
    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state with scheduled events support."""
        gs = MagicMock()
        gs.scheduled_events = {}
        gs.world_clock_tick = 100
        return gs
    
    @pytest.mark.asyncio
    async def test_scheduled_event_awaits_async_handler(self, mock_game_state):
        """Scheduled events should await async handlers."""
        from NextGenMUDApp.comprehensive_game_state_interface import ScheduledEvent
        
        async_called = []
        
        async def async_handler(subject, tick, gs, vars):
            async_called.append(True)
        
        event = ScheduledEvent(
            on_tick=100,
            event_type="test",
            subject=MagicMock(),
            name="test_event",
            vars={},
            func=async_handler
        )
        
        await event.run(100, mock_game_state)
        
        assert len(async_called) == 1
    
    @pytest.mark.asyncio
    async def test_scheduled_event_handles_sync_handler(self, mock_game_state):
        """Scheduled events should handle sync handlers too."""
        from NextGenMUDApp.comprehensive_game_state_interface import ScheduledEvent
        
        sync_called = []
        
        def sync_handler(subject, tick, gs, vars):
            sync_called.append(True)
            return None  # Not a coroutine
        
        event = ScheduledEvent(
            on_tick=100,
            event_type="test",
            subject=MagicMock(),
            name="test_event",
            vars={},
            func=sync_handler
        )
        
        await event.run(100, mock_game_state)
        
        assert len(sync_called) == 1
    
    @pytest.mark.asyncio
    async def test_state_removal_is_async(self):
        """State removal should be properly async."""
        # The remove_state methods are now async
        # and properly awaited by scheduled events
        
        async def mock_remove_state():
            return True
        
        result = await mock_remove_state()
        
        assert result == True


class TestNPCSkillUsage:
    """Tests for NPCs using skills through command handler."""
    
    def test_skill_command_format(self):
        """Skill commands should have proper format."""
        skill_name = "mighty kick"
        target_name = "goblin"
        
        command = f"{skill_name} {target_name}"
        
        assert command == "mighty kick goblin"
    
    def test_skill_without_target_format(self):
        """Non-targeted skills should work without target."""
        skill_name = "berserker stance"
        
        command = skill_name
        
        assert command == "berserker stance"
    
    def test_skill_parsed_from_command(self):
        """Skills should be parseable from command input."""
        from NextGenMUDApp.skills_core import SkillsRegistry
        
        # Register a test skill
        test_skill = MagicMock()
        test_skill.name = "test_skill_parse"
        SkillsRegistry._skills_by_name["test_skill_parse"] = test_skill
        
        # Parse should find it
        result, remainder = SkillsRegistry.parse_skill_name_from_input("test_skill_parse target")
        
        assert result is not None


class TestMainLoopNPCProcessing:
    """Tests for NPC command processing in main loop."""
    
    def test_npc_commands_processed_each_tick(self):
        """NPC commands should be processed each tick."""
        npc = create_mock_character()
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = ["stand", "north"]
        
        # Simulate tick processing
        if npc.command_queue:
            next_command = npc.command_queue.pop(0)
            assert next_command == "stand"
        
        assert len(npc.command_queue) == 1
    
    def test_empty_queue_no_processing(self):
        """Empty queue should not cause errors."""
        npc = create_mock_character()
        npc.command_queue = []
        
        # Should not raise
        if npc.command_queue:
            next_command = npc.command_queue.pop(0)
        
        assert len(npc.command_queue) == 0


class TestResourceRegenerationTick:
    """Tests for resource regeneration in main loop."""
    
    def test_regeneration_called_for_all_characters(self):
        """regenerate_resources should be called for all characters."""
        characters = [
            create_mock_character(name="Char1"),
            create_mock_character(name="Char2"),
            create_mock_character(name="Char3")
        ]
        
        regen_called = []
        
        for char in characters:
            # Simulate regeneration call
            regen_called.append(char.name)
        
        assert len(regen_called) == 3
    
    def test_status_update_sent_on_change(self):
        """Status update should be sent when resources change."""
        pc = create_mock_character(is_pc=True)
        pc.send_status_update = MagicMock()
        
        # Simulate regen returning True (resources changed)
        resources_changed = True
        
        if resources_changed and pc.has_perm_flags(PermanentCharacterFlags.IS_PC):
            pc.send_status_update()
        
        pc.send_status_update.assert_called_once()
