"""
Optimization tests for the quest index (build_quest_index and optimized cmd_quests lookup).

Verifies that the hash index correctly maps variables to quests and that
cmd_quests only evaluates quests that reference variables the player has.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.comprehensive_game_state import ComprehensiveGameState
from NextGenMUDApp.config import default_app_config
from NextGenMUDApp.nondb_models.zone import Zone
from NextGenMUDApp.nondb_models.rooms import Room
from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.command_handler import CommandHandler


def _make_quest_data(quest_id: str, title: str, condition_vars: list) -> dict:
    """Build quest dict with one stage that has conditions on the given variable names."""
    conditions = {}
    for var in condition_vars:
        conditions[var] = True
    return {
        "title": title,
        "stages": [
            {
                "name": "stage1",
                "sequence": 10,
                "description": f"Stage for {quest_id}.",
                "conditions": conditions,
            }
        ],
    }


def _make_complex_game_state_with_100_quests():
    """Build a GameState with one zone and 100 quests: A (var_a), B (var_b), C (var_a, var_b), D (secret_door_found neq), and 96 dummies."""
    g = ComprehensiveGameState(default_app_config)
    g.zones = {}
    g.quest_index = {}

    zone = Zone("opt_zone")
    zone.name = "Optimization Test Zone"
    zone.rooms = {}
    # One room so we can put a player in the zone if needed
    room = Room("start", zone, "Start")
    room.zone = zone
    zone.rooms["start"] = room

    quests_data = {}

    # Quest A: uses var_a only
    quests_data["quest_a"] = _make_quest_data("quest_a", "Quest A", ["var_a"])

    # Quest B: uses var_b only
    quests_data["quest_b"] = _make_quest_data("quest_b", "Quest B", ["var_b"])

    # Quest C: uses var_a AND var_b
    quests_data["quest_c"] = _make_quest_data("quest_c", "Quest C", ["var_a", "var_b"])

    # Quest D: secret_door_found != true (edge case: no variable "anchor" when player has no vars)
    quests_data["quest_d"] = {
        "title": "Quest D",
        "stages": [
            {
                "name": "stage1",
                "sequence": 10,
                "description": "You found the secret door.",
                "conditions": {
                    "secret_door_found": {"op": "neq", "val": "true"},
                },
            }
        ],
    }

    # 96 dummy quests to reach 100 total
    for i in range(96):
        qid = f"quest_dummy_{i}"
        quests_data[qid] = _make_quest_data(qid, f"Dummy Quest {i}", [f"dummy_var_{i}"])

    zone.load_quests(quests_data)
    g.zones["opt_zone"] = zone
    g.build_quest_index()

    return g


@pytest.fixture
def complex_game_state():
    """A GameState populated with 100 dummy quests. Quest A uses var_a, B uses var_b, C uses var_a and var_b, D uses secret_door_found."""
    return _make_complex_game_state_with_100_quests()


# ---------------------------------------------------------------------------
# Test: Index build integrity
# ---------------------------------------------------------------------------


class TestIndexBuildIntegrity:
    """Ensure the mapper associates variables with every quest that uses them."""

    def test_index_build_integrity(self, complex_game_state):
        complex_game_state.build_quest_index()

        zone = complex_game_state.zones["opt_zone"]
        quest_a = zone.quests["quest_a"]
        quest_b = zone.quests["quest_b"]
        quest_c = zone.quests["quest_c"]

        # Index uses both short and qualified names; we use short in conditions so var_a/var_b are keys
        assert "var_a" in complex_game_state.quest_index
        assert "var_b" in complex_game_state.quest_index

        list_a = complex_game_state.quest_index["var_a"]
        list_b = complex_game_state.quest_index["var_b"]

        assert quest_a in list_a
        assert quest_c in list_a
        assert len(list_a) == 2

        assert quest_b in list_b
        assert quest_c in list_b
        assert len(list_b) == 2


# ---------------------------------------------------------------------------
# Test: Optimized lookup performance (only relevant quests evaluated)
# ---------------------------------------------------------------------------


class TestOptimizedLookupPerformance:
    """With var_a set, only Quest A and Quest C should be checked; Quest B must not be evaluated."""

    @pytest.mark.asyncio
    async def test_optimized_lookup_performance(self, complex_game_state):
        zone = complex_game_state.zones["opt_zone"]
        room = zone.rooms["start"]
        quest_a = zone.quests["quest_a"]
        quest_b = zone.quests["quest_b"]
        quest_c = zone.quests["quest_c"]

        player = Character("testplayer", "opt_zone", "TestPlayer")
        player.perm_variables = {"var_a": True}
        player.send_text = AsyncMock()
        room.add_character(player)

        # Patch each quest's get_active_stage to count calls (only A and C should be evaluated)
        with patch.object(quest_a, "get_active_stage", wraps=quest_a.get_active_stage) as mock_a:
            with patch.object(quest_b, "get_active_stage", wraps=quest_b.get_active_stage) as mock_b:
                with patch.object(quest_c, "get_active_stage", wraps=quest_c.get_active_stage) as mock_c:
                    with patch.object(CommandHandler, "_game_state", complex_game_state):
                        await CommandHandler.cmd_quests(CommandHandler, player, "")

        # Only Quest A and Quest C should have get_active_stage called (they're in candidate_quests via var_a)
        assert mock_a.call_count == 1
        assert mock_c.call_count == 1
        assert mock_b.call_count == 0


# ---------------------------------------------------------------------------
# Test: Edge case — missing vars (Quest D not in output when player has no vars)
# ---------------------------------------------------------------------------


class TestEdgeCaseMissingVars:
    """Quest D uses secret_door_found; with empty variables the index won't find it, so it must not appear."""

    @pytest.mark.asyncio
    async def test_edge_case_missing_vars(self, complex_game_state):
        zone = complex_game_state.zones["opt_zone"]
        room = zone.rooms["start"]

        player = Character("testplayer", "opt_zone", "TestPlayer")
        player.perm_variables = {}
        player.send_text = AsyncMock()
        room.add_character(player)

        with patch.object(CommandHandler, "_game_state", complex_game_state):
            await CommandHandler.cmd_quests(CommandHandler, player, "")

        # With no variables, cmd_quests sends "You have no active quests" and never evaluates any quest.
        # Quest D (secret_door_found) is not in the candidate list because the player has no variables,
        # so the index lookup returns nothing for every key in perm_variables (there are none).
        player.send_text.assert_called_once()
        call_args = player.send_text.call_args[0]
        output = call_args[1]
        assert "You have no active quests" in output
        assert "Quest D" not in output
