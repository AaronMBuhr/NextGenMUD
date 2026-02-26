"""
Tests for setstat command (admin-only, in-room only, instant).

Covers: permission check, target resolution (in-room only), stat names,
dice and constant amount, attribute recalc, and status update for PCs.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes, PermanentCharacterFlags, GamePermissionFlags
from NextGenMUDApp.command_handler import CommandHandler
from NextGenMUDApp.nondb_models.characters import Character


def _make_target_character():
    """Minimal Character instance for setstat tests (passes isinstance check)."""
    c = Character("setstat-test-id", "debug_zone", "Target", create_reference=False)
    c.max_hit_points = 100
    c.current_hit_points = 100
    c.max_mana = 50
    c.current_mana = 50
    c.max_stamina = 50
    c.current_stamina = 50
    c.experience_points = 0
    c.attributes = {attr: 10 for attr in CharacterAttributes}
    c.unspent_attribute_points = 0
    c.levels_by_role = {}
    c.has_perm_flags = MagicMock(return_value=False)
    c.send_status_update = AsyncMock()
    return c


@pytest.fixture
def admin_actor():
    actor = MagicMock()
    actor.has_game_flags = MagicMock(side_effect=lambda f: f == GamePermissionFlags.IS_ADMIN)
    actor.send_text = AsyncMock()
    return actor


@pytest.fixture
def non_admin_actor():
    actor = MagicMock()
    actor.has_game_flags = MagicMock(return_value=False)
    actor.send_text = AsyncMock()
    return actor


@pytest.fixture
def mock_game_state():
    gs = MagicMock()
    gs.find_target_character = MagicMock(return_value=None)
    return gs


@pytest.mark.asyncio
async def test_setstat_non_admin_rejected(non_admin_actor, mock_game_state):
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, non_admin_actor, "me hp 50")
    non_admin_actor.send_text.assert_called_once()
    call_args = non_admin_actor.send_text.call_args[0]
    assert "permission" in call_args[1].lower()
    mock_game_state.find_target_character.assert_not_called()


@pytest.mark.asyncio
async def test_setstat_usage_too_few_args(admin_actor, mock_game_state):
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me hp")
    admin_actor.send_text.assert_called_once()
    assert "usage" in admin_actor.send_text.call_args[0][1].lower() or "setstat" in admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_setstat_target_not_found(admin_actor, mock_game_state):
    mock_game_state.find_target_character.return_value = None
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "nobody hp 50")
    admin_actor.send_text.assert_called_once()
    assert "cannot find target" in admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_setstat_hp_constant(admin_actor, mock_game_state):
    target = _make_target_character()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me hp 50")
    assert target.current_hit_points == 50
    admin_actor.send_text.assert_called()
    msg = admin_actor.send_text.call_args[0][1]
    assert "hp set to 50" in msg and target.id in msg


@pytest.mark.asyncio
async def test_setstat_strength_triggers_recalc(admin_actor, mock_game_state):
    target = _make_target_character()
    target.calculate_combat_bonuses = MagicMock()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me strength 18")
    assert target.attributes[CharacterAttributes.STRENGTH] == 18
    target.calculate_combat_bonuses.assert_called_once()
    admin_actor.send_text.assert_called()
    assert "18" in admin_actor.send_text.call_args[0][1]


@pytest.mark.asyncio
async def test_setstat_dice_amount_parsed(admin_actor, mock_game_state):
    target = _make_target_character()
    target.max_hit_points = 200
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me hp 2d6+10")
    # 2d6+10 yields 12–22; we only check it was applied (value in range)
    assert 12 <= target.current_hit_points <= 22
    admin_actor.send_text.assert_called()
    mock_game_state.find_target_character.assert_called_once_with(admin_actor, "me", search_world=False)


@pytest.mark.asyncio
async def test_setstat_in_room_only_search_world_false(admin_actor, mock_game_state):
    target = _make_target_character()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me hp 1")
    mock_game_state.find_target_character.assert_called_once()
    kwargs = mock_game_state.find_target_character.call_args[1]
    assert kwargs.get("search_world") is False


@pytest.mark.asyncio
async def test_setstat_unknown_stat_rejected(admin_actor, mock_game_state):
    target = _make_target_character()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me bogus 99")
    admin_actor.send_text.assert_called_once()
    assert "unknown stat" in admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_setstat_invalid_amount_rejected(admin_actor, mock_game_state):
    target = _make_target_character()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_setstat(CommandHandler, admin_actor, "me hp notanumber")
    admin_actor.send_text.assert_called_once()
    assert "number" in admin_actor.send_text.call_args[0][1].lower() or "dice" in admin_actor.send_text.call_args[0][1].lower()


# --- getstat command tests ---


@pytest.mark.asyncio
async def test_getstat_non_admin_rejected(non_admin_actor, mock_game_state):
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_getstat(CommandHandler, non_admin_actor, "me hp")
    non_admin_actor.send_text.assert_called_once()
    assert "permission" in non_admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_getstat_usage_too_few_args(admin_actor, mock_game_state):
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_getstat(CommandHandler, admin_actor, "me")
    admin_actor.send_text.assert_called_once()
    assert "usage" in admin_actor.send_text.call_args[0][1].lower() or "getstat" in admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_getstat_target_not_found(admin_actor, mock_game_state):
    mock_game_state.find_target_character.return_value = None
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_getstat(CommandHandler, admin_actor, "nobody max_hp")
    admin_actor.send_text.assert_called_once()
    assert "cannot find target" in admin_actor.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_getstat_shows_value(admin_actor, mock_game_state):
    target = _make_target_character()
    target.max_hit_points = 20
    target.current_hit_points = 15
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_getstat(CommandHandler, admin_actor, "me max_hp")
    admin_actor.send_text.assert_called_once()
    msg = admin_actor.send_text.call_args[0][1]
    assert "max_hp = 20" in msg
    assert target.id in msg


@pytest.mark.asyncio
async def test_getstat_unknown_stat_rejected(admin_actor, mock_game_state):
    target = _make_target_character()
    mock_game_state.find_target_character.return_value = target
    with patch.object(CommandHandler, "_game_state", mock_game_state):
        await CommandHandler.cmd_getstat(CommandHandler, admin_actor, "me bogus")
    admin_actor.send_text.assert_called_once()
    assert "unknown stat" in admin_actor.send_text.call_args[0][1].lower()
