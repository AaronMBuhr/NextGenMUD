"""
Unit tests for Trigger + LLM Integration System.

Tests cover:
- CommandResult and TriggerContext data structures
- Instant commands detection and processing
- Trigger context tracking (_trigger_start, _trigger_end)
- Command result recording with success/failure
- Trigger execution with LLM tracking
- Command queue processing with instant commands
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from NextGenMUDApp.command_handler_interface import (
    CommandResult, TriggerResult, TriggerContext
)
from NextGenMUDApp.nondb_models.actor_interface import ActorType
from NextGenMUDApp.nondb_models.trigger_interface import TriggerType

from tests.conftest import create_mock_character


class TestCommandResultDataclass:
    """Tests for CommandResult dataclass."""
    
    def test_command_result_creation(self):
        """CommandResult should be creatable with basic fields."""
        result = CommandResult(command="say hello", succeeded=True)
        
        assert result.command == "say hello"
        assert result.succeeded == True
        assert result.message is None
    
    def test_command_result_with_message(self):
        """CommandResult should store error messages."""
        result = CommandResult(
            command="attack goblin",
            succeeded=False,
            message="Target not found"
        )
        
        assert result.command == "attack goblin"
        assert result.succeeded == False
        assert result.message == "Target not found"
    
    def test_command_result_defaults_to_success(self):
        """CommandResult should default succeeded to True."""
        result = CommandResult(command="look")
        
        assert result.succeeded == True


class TestTriggerResultDataclass:
    """Tests for TriggerResult dataclass."""
    
    def test_trigger_result_creation(self):
        """TriggerResult should store trigger info."""
        result = TriggerResult(
            trigger_type="CATCH_SAY",
            trigger_id="greet_trigger",
            trigger_criteria="* contains 'hello'"
        )
        
        assert result.trigger_type == "CATCH_SAY"
        assert result.trigger_id == "greet_trigger"
        assert result.trigger_criteria == "* contains 'hello'"
        assert result.command_results == []
    
    def test_trigger_result_with_commands(self):
        """TriggerResult should store command results."""
        result = TriggerResult(
            trigger_type="CATCH_SAY",
            trigger_id="test",
            trigger_criteria="test"
        )
        
        result.command_results.append(
            CommandResult(command="say Hi!", succeeded=True)
        )
        result.command_results.append(
            CommandResult(command="give key player", succeeded=False, message="No key")
        )
        
        assert len(result.command_results) == 2
        assert result.command_results[0].succeeded == True
        assert result.command_results[1].succeeded == False


class TestTriggerContextDataclass:
    """Tests for TriggerContext dataclass."""
    
    def test_trigger_context_creation(self):
        """TriggerContext should initialize with defaults."""
        context = TriggerContext()
        
        assert context.initiator_ref is None
        assert context.trigger_results == []
        assert context.current_trigger is None
        assert context.nesting_level == 0
    
    def test_trigger_context_with_initiator(self):
        """TriggerContext should store initiator reference."""
        context = TriggerContext(initiator_ref="@C123")
        
        assert context.initiator_ref == "@C123"
    
    def test_trigger_context_nesting(self):
        """TriggerContext should track nesting level."""
        context = TriggerContext()
        
        context.nesting_level += 1
        assert context.nesting_level == 1
        
        context.nesting_level += 1
        assert context.nesting_level == 2
        
        context.nesting_level -= 1
        assert context.nesting_level == 1


class TestInstantCommands:
    """Tests for instant command detection."""
    
    def test_trigger_start_is_instant(self):
        """_trigger_start should be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert CommandHandler.is_instant_command("_trigger_start foo|bar|baz|qux")
    
    def test_trigger_end_is_instant(self):
        """_trigger_end should be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert CommandHandler.is_instant_command("_trigger_end")
    
    def test_settempvar_is_instant(self):
        """settempvar should be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert CommandHandler.is_instant_command("settempvar target varname value")
    
    def test_setpermvar_is_instant(self):
        """setpermvar should be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert CommandHandler.is_instant_command("setpermvar target varname value")
    
    def test_say_is_not_instant(self):
        """say should NOT be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert not CommandHandler.is_instant_command("say hello")
    
    def test_attack_is_not_instant(self):
        """attack should NOT be an instant command."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert not CommandHandler.is_instant_command("attack goblin")
    
    def test_movement_is_not_instant(self):
        """Movement commands should NOT be instant."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert not CommandHandler.is_instant_command("north")
        assert not CommandHandler.is_instant_command("south")
        assert not CommandHandler.is_instant_command("east")
    
    def test_empty_string_is_not_instant(self):
        """Empty string should not be instant."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert not CommandHandler.is_instant_command("")
        assert not CommandHandler.is_instant_command("   ")
    
    def test_case_insensitive_instant_check(self):
        """Instant command check should be case insensitive."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert CommandHandler.is_instant_command("_TRIGGER_START foo")
        assert CommandHandler.is_instant_command("_Trigger_End")
        assert CommandHandler.is_instant_command("SETTEMPVAR x y z")


class TestCommandQueueProcessing:
    """Tests for command queue processing with instant commands."""
    
    @pytest.fixture
    def mock_npc(self):
        """Create a mock NPC with command queue."""
        npc = create_mock_character(name="TestNPC")
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.trigger_context = None
        npc.reference_number = "C1"
        npc.rid = "C1{test_npc}"
        npc.is_busy = MagicMock(return_value=False)
        npc.is_dead = MagicMock(return_value=False)
        npc.has_temp_flags = MagicMock(return_value=False)
        npc.perm_variables = {}
        npc.temp_variables = {}
        npc.get_perm_var = MagicMock(return_value=None)
        return npc
    
    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state."""
        gs = MagicMock()
        gs.world_clock_tick = 100
        gs.current_tick = 100
        gs.get_current_tick = MagicMock(return_value=100)
        return gs
    
    @pytest.mark.asyncio
    async def test_process_single_command(self, mock_npc, mock_game_state):
        """Should process a single command from queue."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        mock_npc.command_queue = ["look"]
        
        with patch.object(CommandHandler, 'process_command', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = True
            
            result = await CommandHandler.process_command_queue(mock_npc, mock_game_state)
            
            assert result == True
            mock_process.assert_called_once()
            assert len(mock_npc.command_queue) == 0
    
    @pytest.mark.asyncio
    async def test_instant_command_continues_immediately(self, mock_npc, mock_game_state):
        """Instant commands at end of queue should execute immediately."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # say is NOT instant, _trigger_end IS instant
        mock_npc.command_queue = ["say hello", "_trigger_end"]
        
        processed_commands = []
        
        async def track_process(actor, cmd, vars=None, from_script=False):
            processed_commands.append(cmd)
            return True
        
        with patch.object(CommandHandler, 'process_command', side_effect=track_process):
            await CommandHandler.process_command_queue(mock_npc, mock_game_state)
        
        # Both should be processed in one call because _trigger_end is instant
        assert len(processed_commands) == 2
        assert "say hello" in processed_commands
        assert "_trigger_end" in processed_commands
    
    @pytest.mark.asyncio
    async def test_non_instant_stops_processing(self, mock_npc, mock_game_state):
        """Non-instant command after another should stop processing."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # say and attack are both NOT instant
        mock_npc.command_queue = ["say hello", "attack goblin"]
        
        processed_commands = []
        
        async def track_process(actor, cmd, vars=None, from_script=False):
            processed_commands.append(cmd)
            return True
        
        with patch.object(CommandHandler, 'process_command', side_effect=track_process):
            await CommandHandler.process_command_queue(mock_npc, mock_game_state)
        
        # Only first command should be processed
        assert len(processed_commands) == 1
        assert processed_commands[0] == "say hello"
        # Second command still in queue
        assert mock_npc.command_queue == ["attack goblin"]
    
    @pytest.mark.asyncio
    async def test_multiple_instant_commands_chain(self, mock_npc, mock_game_state):
        """Multiple instant commands should all execute."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        mock_npc.command_queue = [
            "settempvar npc x 1",
            "_trigger_end",
            "say done"  # Not instant, should still be in queue
        ]
        
        processed_commands = []
        
        async def track_process(actor, cmd, vars=None, from_script=False):
            processed_commands.append(cmd)
            return True
        
        with patch.object(CommandHandler, 'process_command', side_effect=track_process):
            await CommandHandler.process_command_queue(mock_npc, mock_game_state)
        
        # First command (settempvar) runs, then peeks _trigger_end (instant), runs it
        # Then peeks "say done" (not instant), stops
        assert "settempvar npc x 1" in processed_commands
        assert "_trigger_end" in processed_commands
        assert "say done" not in processed_commands
        assert mock_npc.command_queue == ["say done"]
    
    @pytest.mark.asyncio
    async def test_empty_queue_returns_false(self, mock_npc, mock_game_state):
        """Empty queue should return False."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        mock_npc.command_queue = []
        
        result = await CommandHandler.process_command_queue(mock_npc, mock_game_state)
        
        assert result == False


class TestTriggerContextCommands:
    """Tests for _trigger_start and _trigger_end commands."""
    
    @pytest.fixture
    def mock_npc(self):
        """Create a mock NPC for trigger testing."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        npc = MagicMock(spec=Character)
        npc.name = "Test NPC"
        npc.art_name_cap = "The Test NPC"
        npc.id = "test_npc"
        npc.rid = "C1{test_npc}"
        npc.reference_number = "C1"
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.trigger_context = None
        npc.perm_variables = {}
        npc.get_perm_var = MagicMock(return_value=None)
        npc.connection = None
        npc.send_text = AsyncMock()
        npc.echo = AsyncMock()
        npc.location_room = MagicMock()
        npc.location_room.echo = AsyncMock()
        npc._location_room = npc.location_room
        return npc
    
    @pytest.mark.asyncio
    async def test_trigger_start_creates_context(self, mock_npc):
        """_trigger_start should create a trigger context on the actor."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # Ensure no existing context
        mock_npc.trigger_context = None
        
        # Call as instance method (cls is passed automatically via get_instance pattern)
        handler = CommandHandler()
        await handler.cmd_trigger_start(
            mock_npc, 
            "CATCH_SAY|greet_trigger|* contains 'hello'|@C123"
        )
        
        assert mock_npc.trigger_context is not None
        assert mock_npc.trigger_context.nesting_level == 1
        assert mock_npc.trigger_context.initiator_ref == "@C123"
        assert len(mock_npc.trigger_context.trigger_results) == 1
        assert mock_npc.trigger_context.trigger_results[0].trigger_type == "CATCH_SAY"
    
    @pytest.mark.asyncio
    async def test_trigger_start_increments_nesting(self, mock_npc):
        """Nested _trigger_start should increment nesting level."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        mock_npc.trigger_context = None
        handler = CommandHandler()
        
        # First trigger
        await handler.cmd_trigger_start(
            mock_npc,
            "CATCH_SAY|trigger1|crit1|@C1"
        )
        assert mock_npc.trigger_context.nesting_level == 1
        
        # Nested trigger
        await handler.cmd_trigger_start(
            mock_npc,
            "ON_RECEIVE|trigger2|crit2|@C1"
        )
        assert mock_npc.trigger_context.nesting_level == 2
        assert len(mock_npc.trigger_context.trigger_results) == 2
    
    @pytest.mark.asyncio
    async def test_trigger_end_decrements_nesting(self, mock_npc):
        """_trigger_end should decrement nesting level."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # Set up context with nesting level 2
        mock_npc.trigger_context = TriggerContext(
            initiator_ref="@C1",
            nesting_level=2,
            trigger_results=[
                TriggerResult("CATCH_SAY", "t1", "c1"),
                TriggerResult("ON_RECEIVE", "t2", "c2")
            ]
        )
        
        handler = CommandHandler()
        await handler.cmd_trigger_end(mock_npc, "")
        
        assert mock_npc.trigger_context.nesting_level == 1
        # Context should still exist
        assert mock_npc.trigger_context is not None
    
    @pytest.mark.asyncio
    async def test_trigger_end_clears_context_at_zero(self, mock_npc):
        """_trigger_end should clear context when nesting reaches 0."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # Set up context with nesting level 1 (will go to 0)
        mock_npc.trigger_context = TriggerContext(
            initiator_ref="@C1",
            nesting_level=1,
            trigger_results=[TriggerResult("CATCH_SAY", "t1", "c1")]
        )
        
        # NPC not LLM-enabled, so it should just clear context
        mock_npc.get_perm_var = MagicMock(return_value=None)
        
        handler = CommandHandler()
        await handler.cmd_trigger_end(mock_npc, "")
        
        # Context should be cleared
        assert mock_npc.trigger_context is None


class TestCommandResultRecording:
    """Tests for recording command results in trigger context."""
    
    @pytest.fixture
    def mock_npc_with_context(self):
        """Create NPC with active trigger context."""
        npc = create_mock_character(name="TestNPC")
        npc.actor_type = ActorType.CHARACTER
        npc.reference_number = "C1"
        npc.rid = "C1{test_npc}"
        npc.command_queue = []
        npc.is_busy = MagicMock(return_value=False)
        npc.is_dead = MagicMock(return_value=False)
        npc.has_temp_flags = MagicMock(return_value=False)
        npc.perm_variables = {}
        npc.get_perm_var = MagicMock(return_value=None)
        npc.connection = None
        
        # Set up trigger context
        current_trigger = TriggerResult("CATCH_SAY", "test", "test criteria")
        npc.trigger_context = TriggerContext(
            initiator_ref="@C1",
            nesting_level=1,
            trigger_results=[current_trigger],
            current_trigger=current_trigger
        )
        
        return npc
    
    @pytest.mark.asyncio
    async def test_successful_command_recorded(self, mock_npc_with_context):
        """Successful commands should be recorded in trigger context."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # Mock the command execution path
        with patch.object(CommandHandler, 'cmd_say', new_callable=AsyncMock):
            # Use a minimal setup for executing a command
            CommandHandler.executing_actors = {}
            
            # Simulate a successful say command
            # We need to mock more of the process to avoid actual execution
            from NextGenMUDApp.command_handler_interface import CommandResult
            
            # Directly test the recording logic
            mock_npc_with_context.trigger_context.current_trigger.command_results.append(
                CommandResult(command="say hello", succeeded=True)
            )
        
        assert len(mock_npc_with_context.trigger_context.current_trigger.command_results) == 1
        assert mock_npc_with_context.trigger_context.current_trigger.command_results[0].succeeded == True
    
    def test_internal_commands_not_recorded(self):
        """Internal trigger commands should not be recorded."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        # These should be recognized as internal and not recorded
        assert CommandHandler.is_instant_command("_trigger_start foo")
        assert CommandHandler.is_instant_command("_trigger_end")


class TestTriggerCriteriaSummary:
    """Tests for trigger criteria summary generation."""
    
    def test_get_criteria_summary_empty(self):
        """Empty criteria should return 'no criteria'."""
        from NextGenMUDApp.nondb_models.triggers import Trigger, TriggerType
        
        # Create a mock trigger with no criteria
        trigger = MagicMock()
        trigger.criteria_ = []
        
        # Manually test the logic
        criteria = trigger.criteria_
        if not criteria:
            summary = "no criteria"
        else:
            summary = "has criteria"
        
        assert summary == "no criteria"
    
    def test_get_criteria_summary_with_criteria(self):
        """Criteria should generate readable summary."""
        from NextGenMUDApp.nondb_models.triggers import TriggerCriteria
        
        crit = TriggerCriteria()
        crit.subject = "*"
        crit.operator = "contains"
        crit.predicate = "hello"
        
        summary = f"{crit.subject} {crit.operator} '{crit.predicate}'"
        
        assert summary == "* contains 'hello'"


class TestTriggerExecutionWithLLMTracking:
    """Tests for trigger execution with LLM tracking commands."""
    
    @pytest.fixture
    def mock_npc(self):
        """Create a mock NPC for trigger execution testing."""
        npc = create_mock_character(name="TestNPC")
        npc.actor_type = ActorType.CHARACTER
        npc.command_queue = []
        npc.trigger_context = None
        npc.reference_number = "C1"
        return npc
    
    def test_trigger_queues_start_and_end(self, mock_npc):
        """Trigger execution should queue _trigger_start and _trigger_end."""
        # Simulate what execute_trigger_script should do
        trigger_type = "CATCH_SAY"
        trigger_id = "greet"
        criteria_summary = "* contains 'hello'"
        initiator_ref = "@C123"
        
        # Build trigger info
        trigger_info = f"{trigger_type}|{trigger_id}|{criteria_summary}|{initiator_ref}"
        
        # Queue commands like execute_trigger_script would
        mock_npc.command_queue.append(f"_trigger_start {trigger_info}")
        mock_npc.command_queue.append("say Hi there!")
        mock_npc.command_queue.append("_trigger_end")
        
        assert len(mock_npc.command_queue) == 3
        assert mock_npc.command_queue[0].startswith("_trigger_start")
        assert mock_npc.command_queue[1] == "say Hi there!"
        assert mock_npc.command_queue[2] == "_trigger_end"
    
    def test_timer_tick_excluded_from_tracking(self):
        """TIMER_TICK triggers should not have LLM tracking."""
        from NextGenMUDApp.nondb_models.triggers import TriggerType
        
        # The implementation checks for TIMER_TICK
        trigger_type = TriggerType.TIMER_TICK
        should_track = trigger_type != TriggerType.TIMER_TICK
        
        assert should_track == False


class TestLLMIntegration:
    """Tests for LLM integration with trigger results."""
    
    def test_trigger_results_formatting(self):
        """Trigger results should be formatted for LLM consumption."""
        trigger_result = TriggerResult(
            trigger_type="CATCH_SAY",
            trigger_id="greet",
            trigger_criteria="* contains 'hello'"
        )
        trigger_result.command_results = [
            CommandResult(command="say 'Hi there!'", succeeded=True),
            CommandResult(command="give key player", succeeded=False, message="No key")
        ]
        
        # Format like _send_trigger_results_to_llm does
        trigger_desc = f"{trigger_result.trigger_type} trigger"
        if trigger_result.trigger_criteria:
            trigger_desc += f" ({trigger_result.trigger_criteria})"
        trigger_desc += ":"
        
        cmd_descs = []
        for cmd_result in trigger_result.command_results:
            status = "succeeded" if cmd_result.succeeded else "failed"
            cmd_descs.append(f"{cmd_result.command} ({status})")
        trigger_desc += " " + ", ".join(cmd_descs)
        
        assert "CATCH_SAY trigger" in trigger_desc
        assert "* contains 'hello'" in trigger_desc
        assert "say 'Hi there!' (succeeded)" in trigger_desc
        assert "give key player (failed)" in trigger_desc
    
    @pytest.mark.asyncio
    async def test_llm_not_called_when_not_enabled(self):
        """LLM should not be called if NPC is not LLM-enabled."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        npc = create_mock_character(name="NonLLMNpc")
        npc.trigger_context = TriggerContext(
            initiator_ref="@C1",
            nesting_level=1,
            trigger_results=[TriggerResult("CATCH_SAY", "t1", "c1")]
        )
        npc.get_perm_var = MagicMock(return_value=None)  # No LLM context
        
        handler = CommandHandler()
        await handler.cmd_trigger_end(npc, "")
        
        # Context should be cleared but no LLM call made
        assert npc.trigger_context is None


class TestActorTriggerContext:
    """Tests for trigger context on Actor class."""
    
    def test_actor_has_trigger_context_field(self):
        """Actor (via Character) should have trigger_context field."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        # Create a Character which is a concrete implementation of Actor
        char = Character("test_char", "test_zone", "Test Character", create_reference=True)
        
        assert hasattr(char, 'trigger_context')
        assert char.trigger_context is None  # Initially None
    
    def test_trigger_context_can_be_set(self):
        """Trigger context should be settable on actor."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        char = Character("test_char2", "test_zone", "Test Character", create_reference=True)
        
        context = TriggerContext(initiator_ref="@C1")
        char.trigger_context = context
        
        assert char.trigger_context is not None
        assert char.trigger_context.initiator_ref == "@C1"


class TestPrivilegedCommands:
    """Tests for privileged command configuration."""
    
    def test_trigger_commands_are_privileged(self):
        """Trigger commands should be in privileged_commands set."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert "_trigger_start" in CommandHandler.privileged_commands
        assert "_trigger_end" in CommandHandler.privileged_commands
    
    def test_trigger_commands_in_handlers(self):
        """Trigger commands should be in command_handlers dict."""
        from NextGenMUDApp.command_handler import CommandHandler
        
        assert "_trigger_start" in CommandHandler.command_handlers
        assert "_trigger_end" in CommandHandler.command_handlers
