import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import create_mock_character


def make_command_actor(is_pc=True):
    from NextGenMUDApp.nondb_models.actor_interface import ActorType

    actor = create_mock_character(is_pc=is_pc)
    actor.reference_number = "C1"
    actor.id = "test_actor"
    actor.actor_type = ActorType.CHARACTER
    actor.connection = MagicMock()
    actor.trigger_context = None
    actor.is_dead = MagicMock(return_value=False)
    actor.is_busy = MagicMock(return_value=False)
    actor.states = []
    actor.charmed_by = None
    actor.location_room = MagicMock()
    actor.location_room.echo = AsyncMock()
    actor.add_temp_flags = MagicMock(side_effect=lambda flags: setattr(
        actor, "temporary_character_flags", actor.temporary_character_flags.add_flags(flags)
    ) or True)
    actor.remove_temp_flags = MagicMock(side_effect=lambda flags: setattr(
        actor, "temporary_character_flags", actor.temporary_character_flags.remove_flags(flags)
    ) or True)
    return actor


class TestCommandImpairment:
    @pytest.mark.asyncio
    async def test_charmed_blocks_non_whitelisted_command(self, mock_game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        actor = make_command_actor()
        actor.charmed_by = object()
        mock_game_state.is_debug_enabled = MagicMock(return_value=False)
        mock_game_state.get_current_tick = MagicMock(return_value=100)
        CommandHandler._game_state = mock_game_state

        await CommandHandler.process_command(actor, "north")

        messages = [call.args[1] for call in actor.send_text.await_args_list]
        assert any("You are under another's control." in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_charmed_allows_whitelisted_status(self, mock_game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        actor = make_command_actor()
        actor.charmed_by = object()
        mock_game_state.is_debug_enabled = MagicMock(return_value=False)
        mock_game_state.get_current_tick = MagicMock(return_value=100)
        CommandHandler._game_state = mock_game_state

        assert CommandHandler.get_command_impairment_message(actor, "status") is None

    @pytest.mark.asyncio
    async def test_confused_blocks_non_whitelisted_command(self, mock_game_state):
        from NextGenMUDApp.command_handler import CommandHandler
        from NextGenMUDApp.nondb_models.character_interface import TemporaryCharacterFlags

        actor = make_command_actor()
        actor.temporary_character_flags = actor.temporary_character_flags.add_flags(TemporaryCharacterFlags.IS_CONFUSED)
        mock_game_state.is_debug_enabled = MagicMock(return_value=False)
        mock_game_state.get_current_tick = MagicMock(return_value=100)
        CommandHandler._game_state = mock_game_state

        await CommandHandler.process_command(actor, "north")

        messages = [call.args[1] for call in actor.send_text.await_args_list]
        assert any("You're too confused to do that." in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_command_bypasses_impairment_for_controlled_target(self, mock_game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        actor = make_command_actor()
        target = make_command_actor(is_pc=False)
        target.name = "zombie"
        target.art_name = "the zombie"
        target.art_name_cap = "The zombie"
        target.charmed_by = actor
        actor.location_room = MagicMock()
        actor.location_room.echo = AsyncMock()
        actor.has_game_flags = MagicMock(return_value=False)
        mock_game_state.find_target_character = MagicMock(return_value=target)
        mock_game_state.is_debug_enabled = MagicMock(return_value=False)
        mock_game_state.get_current_tick = MagicMock(return_value=100)
        CommandHandler._game_state = mock_game_state

        with patch.object(CommandHandler, "process_command", new=AsyncMock()) as process_command_mock:
            await CommandHandler.cmd_command(CommandHandler, actor, "zombie north")

        process_command_mock.assert_awaited_once_with(target, "north", {}, bypass_impairment=True)
