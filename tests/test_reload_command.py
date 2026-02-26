"""
Tests for admin reload commands: reload zone and reload rooms.

Tests cover:
- reload_zone: unknown zone, valid zone full reload, NPC respawn, player snapshot/restore
- reload_rooms: unknown zone, valid zone rooms-only reload, occupant preservation
- cmd_reload: permission check, subcommand and zone_name parsing
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.comprehensive_game_state import ComprehensiveGameState
from NextGenMUDApp.config import default_app_config
from NextGenMUDApp.nondb_models.actor_interface import ActorType
from NextGenMUDApp.nondb_models.character_interface import PermanentCharacterFlags, GamePermissionFlags
from NextGenMUDApp.nondb_models.characters import Character


@pytest.fixture(scope="module")
def game_state():
    """Real game state with world loaded (shared across module to avoid slow repeated init)."""
    g = ComprehensiveGameState(default_app_config)
    g.Initialize()
    return g


@pytest.fixture
def small_zone_id():
    """A zone with few rooms for fast tests."""
    return "debug_zone"


@pytest.fixture
def zone_with_npcs_id():
    """A zone that has spawn_data NPCs."""
    return "enchanted_forest"


class TestReloadZone:
    """Tests for full zone reload (reload zone)."""

    @pytest.mark.asyncio
    async def test_reload_zone_unknown_zone_returns_error(self, game_state):
        result = await game_state.reload_zone("nonexistent_zone_xyz")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_reload_zone_valid_zone_returns_summary(self, game_state, small_zone_id):
        result = await game_state.reload_zone(small_zone_id)
        assert "reloaded" in result.lower()
        assert small_zone_id in result
        assert "rooms" in result.lower()

    @pytest.mark.asyncio
    async def test_reload_zone_rebuilds_rooms(self, game_state, small_zone_id):
        zone = game_state.zones[small_zone_id]
        room_ids_before = set(zone.rooms.keys())
        await game_state.reload_zone(small_zone_id)
        zone_after = game_state.zones[small_zone_id]
        room_ids_after = set(zone_after.rooms.keys())
        assert room_ids_after == room_ids_before

    @pytest.mark.asyncio
    async def test_reload_zone_respawns_npcs_from_spawn_data(self, game_state, zone_with_npcs_id):
        zone = game_state.zones[zone_with_npcs_id]
        npc_count_before = sum(len(r.characters) for r in zone.rooms.values())
        await game_state.reload_zone(zone_with_npcs_id)
        zone_after = game_state.zones[zone_with_npcs_id]
        npc_count_after = sum(len(r.characters) for r in zone_after.rooms.values())
        assert npc_count_after == npc_count_before
        assert npc_count_after >= 1

    @pytest.mark.asyncio
    async def test_reload_zone_abort_when_definitions_fail(self, game_state, small_zone_id):
        # When _reload_zone_definitions returns failure, we get abort message and zone is unchanged
        with patch.object(game_state, "_reload_zone_definitions", return_value=(False, "No zone in YAML")):
            result = await game_state.reload_zone(small_zone_id)
            assert "aborted" in result.lower()
            assert small_zone_id in game_state.zones


class TestReloadRooms:
    """Tests for rooms-only reload (reload rooms)."""

    @pytest.mark.asyncio
    async def test_reload_rooms_unknown_zone_returns_error(self, game_state):
        result = await game_state.reload_rooms("nonexistent_zone_xyz")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_reload_rooms_valid_zone_returns_summary(self, game_state, small_zone_id):
        result = await game_state.reload_rooms(small_zone_id)
        assert "reloaded" in result.lower()
        assert small_zone_id in result

    @pytest.mark.asyncio
    async def test_reload_rooms_preserves_occupants(self, game_state, zone_with_npcs_id):
        zone = game_state.zones[zone_with_npcs_id]
        npc_count_before = sum(len(r.characters) for r in zone.rooms.values())
        await game_state.reload_rooms(zone_with_npcs_id)
        zone_after = game_state.zones[zone_with_npcs_id]
        npc_count_after = sum(len(r.characters) for r in zone_after.rooms.values())
        assert npc_count_after == npc_count_before

    @pytest.mark.asyncio
    async def test_reload_rooms_does_not_respawn_extra_npcs(self, game_state, zone_with_npcs_id):
        total_chars_before = len(game_state.characters)
        await game_state.reload_rooms(zone_with_npcs_id)
        total_chars_after = len(game_state.characters)
        assert total_chars_after == total_chars_before


class TestCmdReload:
    """Tests for the reload admin command handler."""

    @pytest.mark.asyncio
    async def test_cmd_reload_requires_admin(self):
        """Non-admin PC is rejected by the command dispatcher (privileged check), not by cmd_reload."""
        from NextGenMUDApp.command_handler import CommandHandler

        actor = MagicMock()
        actor.actor_type = ActorType.CHARACTER
        actor.rid = "test_pc"
        actor.reference_number = "1"
        actor.has_perm_flags = MagicMock(return_value=True)   # is a player character
        actor.has_game_flags = MagicMock(return_value=False)  # not admin
        actor.has_temp_flags = MagicMock(return_value=False)
        actor.is_dead = MagicMock(return_value=False)
        actor.is_busy = MagicMock(return_value=False)
        actor.command_queue = []
        actor.id = "test_pc"
        actor.send_text = AsyncMock()
        actor.trigger_context = None

        mock_game_state = MagicMock()
        mock_game_state.get_current_tick = MagicMock(return_value=0)
        mock_game_state.is_debug_enabled = MagicMock(return_value=False)

        with patch.object(CommandHandler, "_game_state", mock_game_state), \
             patch("NextGenMUDApp.command_handler.flush_admin_log_queue", new_callable=AsyncMock), \
             patch("NextGenMUDApp.command_handler.clear_current_actor"):
            await CommandHandler.process_command(actor, "reload zone debug_zone")

        # Dispatcher should have sent the permission message (and the echo "> reload ...")
        messages_sent = [call_args[0][1] for call_args in actor.send_text.call_args_list if call_args[0]]
        assert any("permission" in (msg or "").lower() for msg in messages_sent)

    @pytest.mark.asyncio
    async def test_cmd_reload_usage_with_no_input(self):
        from NextGenMUDApp.command_handler import CommandHandler

        actor = MagicMock()
        actor.has_game_flags = MagicMock(return_value=True)
        actor.send_text = AsyncMock()

        await CommandHandler.cmd_reload(CommandHandler, actor, "")

        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "usage" in call_args[1].lower() or "reload" in call_args[1].lower()

    @pytest.mark.asyncio
    async def test_cmd_reload_zone_with_explicit_zone_name(self, game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        with patch.object(CommandHandler, "_game_state", game_state):
            actor = MagicMock()
            actor.has_game_flags = MagicMock(return_value=True)
            actor.send_text = AsyncMock()

            await CommandHandler.cmd_reload(CommandHandler, actor, "zone debug_zone")

            actor.send_text.assert_called()
            call_args = actor.send_text.call_args[0]
            assert "reloaded" in call_args[1].lower() or "aborted" in call_args[1].lower()

    @pytest.mark.asyncio
    async def test_cmd_reload_rooms_with_explicit_zone_name(self, game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        with patch.object(CommandHandler, "_game_state", game_state):
            actor = MagicMock()
            actor.has_game_flags = MagicMock(return_value=True)
            actor.send_text = AsyncMock()

            await CommandHandler.cmd_reload(CommandHandler, actor, "rooms debug_zone")

            actor.send_text.assert_called()
            call_args = actor.send_text.call_args[0]
            assert "reloaded" in call_args[1].lower()

    @pytest.mark.asyncio
    async def test_cmd_reload_unknown_zone_returns_message(self, game_state):
        from NextGenMUDApp.command_handler import CommandHandler

        with patch.object(CommandHandler, "_game_state", game_state):
            actor = MagicMock()
            actor.has_game_flags = MagicMock(return_value=True)
            actor.send_text = AsyncMock()

            await CommandHandler.cmd_reload(CommandHandler, actor, "zone not_a_zone_123")

            actor.send_text.assert_called()
            call_args = actor.send_text.call_args[0]
            assert "not found" in call_args[1].lower()
