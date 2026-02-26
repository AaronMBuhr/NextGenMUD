"""
Integration tests for quest-related commands (quests, setquestvar).

Verifies that player commands interact with the quest system correctly,
including empty state, active quest display, variable updates, and cross-zone scoping.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.comprehensive_game_state import ComprehensiveGameState
from NextGenMUDApp.config import default_app_config
from NextGenMUDApp.nondb_models.zone import Zone
from NextGenMUDApp.nondb_models.rooms import Room
from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.nondb_models.quests import (
    get_quest_var,
    set_quest_var,
    add_quest_llm_knowledge,
    add_zone_llm_knowledge,
    remove_quest_llm_knowledge,
    get_resolved_llm_knowledge,
)
from NextGenMUDApp.command_handler import CommandHandler


# ---------------------------------------------------------------------------
# Fixtures: Game state with one Zone and Murder Mystery quest
# ---------------------------------------------------------------------------

MURDER_MYSTERY_QUEST_DATA = {
    "murder_mystery": {
        "title": "The Gloomy Graveyard Murder",
        "variables": {
            "heard_about_murder": {
                "type": "boolean",
                "default": False,
                "description": "Heard rumors of the murder.",
            },
            "found_body": {
                "type": "boolean",
                "default": False,
                "description": "Discovered the victim's body.",
                "knowledge_updates": [
                    {
                        "condition": True,
                        "updates": {
                            "murder_case": "You found Lord Ashford's body among the graves.",
                        },
                    },
                ],
            },
        },
        "stages": [
            {
                "name": "Start",
                "sequence": 10,
                "description": "People are terrified—and they're blaming Old Tom. Start by talking to Maggie at the Weary Traveler.",
                "conditions": {"murder_mystery.heard_about_murder": True},
            },
        ],
    }
}


@pytest.fixture
def game_state():
    """A GameState containing one Zone (gloomy_graveyard) and one Quest (Murder Mystery)."""
    g = ComprehensiveGameState(default_app_config)
    g.zones = {}
    g.quest_index = {}

    zone = Zone("gloomy_graveyard")
    zone.name = "Gloomy Graveyard"
    zone.load_quests(MURDER_MYSTERY_QUEST_DATA)

    room = Room("start", zone, "Start Room")
    room.zone = zone
    zone.rooms["start"] = room

    g.zones["gloomy_graveyard"] = zone
    g.build_quest_index()

    return g


@pytest.fixture
def player(game_state):
    """A fully instantiated Player (Character) with an active session in the quest zone."""
    zone = game_state.zones["gloomy_graveyard"]
    room = zone.rooms["start"]

    char = Character("testplayer", "gloomy_graveyard", "TestPlayer")
    char.perm_variables = {}
    char.send_text = AsyncMock()
    room.add_character(char)

    return char


# ---------------------------------------------------------------------------
# Test: cmd_quests — empty
# ---------------------------------------------------------------------------


class TestCmdQuestsEmpty:
    """When player has no variables, cmd_quests shows no active quests."""

    @pytest.mark.asyncio
    async def test_cmd_quests_empty(self, game_state, player):
        player.perm_variables = {}

        with patch.object(CommandHandler, "_game_state", game_state):
            await CommandHandler.cmd_quests(CommandHandler, player, "")

        player.send_text.assert_called()
        call_args = player.send_text.call_args[0]
        assert "You have no active quests" in call_args[1]


# ---------------------------------------------------------------------------
# Test: cmd_quests — active quest and stage description
# ---------------------------------------------------------------------------


class TestCmdQuestsActive:
    """When player has the right variable, cmd_quests shows quest title and stage description."""

    @pytest.mark.asyncio
    async def test_cmd_quests_active(self, game_state, player):
        player.perm_variables["gloomy_graveyard.murder_mystery.heard_about_murder"] = True

        with patch.object(CommandHandler, "_game_state", game_state):
            await CommandHandler.cmd_quests(CommandHandler, player, "")

        player.send_text.assert_called()
        call_args = player.send_text.call_args[0]
        output = call_args[1]
        assert "The Gloomy Graveyard Murder" in output
        assert "People are terrified" in output or "Maggie" in output or "Weary Traveler" in output


# ---------------------------------------------------------------------------
# Test: setquestvar updates state (and optionally knowledge)
# ---------------------------------------------------------------------------


class TestSetquestvarUpdatesState:
    """setquestvar updates perm_variables and can trigger knowledge_updates."""

    @pytest.mark.asyncio
    async def test_setquestvar_updates_state(self, game_state, player):
        with patch.object(CommandHandler, "_game_state", game_state):
            await CommandHandler.cmd_setquestvar(
                CommandHandler, player, "me murder_mystery.found_body true"
            )

        assert get_quest_var(player, "murder_mystery.found_body") is True

    @pytest.mark.asyncio
    async def test_setquestvar_appends_quest_llm_knowledge_ids(self, game_state, player):
        with patch.object(CommandHandler, "_game_state", game_state):
            set_quest_var(player, "murder_mystery.found_body", True, auto_update_knowledge=True)

        key = "gloomy_graveyard.murder_mystery.llm_knowledge"
        assert key in player.perm_variables
        assert player.perm_variables[key] == ["murder_case"]


# ---------------------------------------------------------------------------
# Test: Cross-zone scoping (short syntax resolves to player's zone)
# ---------------------------------------------------------------------------


class TestCrossZoneScoping:
    """When player is in Zone A and quest is in Zone B, short syntax resolves to player's zone."""

    @pytest.fixture
    def two_zone_game_state(self):
        """GameState with Zone A (player's zone) and Zone B (quest zone)."""
        g = ComprehensiveGameState(default_app_config)
        g.zones = {}
        g.quest_index = {}

        # Zone A: player's zone, no quest
        zone_a = Zone("zone_a")
        zone_a.name = "Zone A"
        room_a = Room("start", zone_a, "Start A")
        room_a.zone = zone_a
        zone_a.rooms["start"] = room_a
        g.zones["zone_a"] = zone_a

        # Zone B: has Murder Mystery quest
        zone_b = Zone("zone_b")
        zone_b.name = "Zone B"
        zone_b.load_quests(MURDER_MYSTERY_QUEST_DATA)
        room_b = Room("start", zone_b, "Start B")
        room_b.zone = zone_b
        zone_b.rooms["start"] = room_b
        g.zones["zone_b"] = zone_b

        g.build_quest_index()
        return g

    @pytest.fixture
    def player_in_zone_a(self, two_zone_game_state):
        """Player in Zone A (quest is in Zone B)."""
        zone_a = two_zone_game_state.zones["zone_a"]
        room_a = zone_a.rooms["start"]
        char = Character("testplayer", "zone_a", "TestPlayer")
        char.perm_variables = {}
        char.send_text = AsyncMock()
        room_a.add_character(char)
        return char

    @pytest.mark.asyncio
    async def test_cross_zone_scoping_short_syntax_resolves_to_player_zone(
        self, two_zone_game_state, player_in_zone_a
    ):
        with patch.object(CommandHandler, "_game_state", two_zone_game_state):
            await CommandHandler.cmd_setquestvar(
                CommandHandler, player_in_zone_a, "me murder_mystery.found_body true"
            )

        # Short syntax resolves using player's current zone (Zone A)
        assert get_quest_var(player_in_zone_a, "murder_mystery.found_body") is True
        # Variable is stored under Zone A namespace
        full_key = "zone_a.murder_mystery.found_body"
        assert full_key in player_in_zone_a.perm_variables
        assert player_in_zone_a.perm_variables[full_key] is True


# ---------------------------------------------------------------------------
# Test: LLM knowledge lists (append-only, additive)
# ---------------------------------------------------------------------------


class TestQuestLlmKnowledge:
    """add_quest_llm_knowledge and add_zone_llm_knowledge are append-only and additive."""

    def test_add_quest_llm_knowledge_appends_ids(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case"])
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case"
        ]

    def test_add_quest_llm_knowledge_append_only_no_duplicate(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case"])
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case"])
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case"
        ]

    def test_add_quest_llm_knowledge_adds_multiple(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_quest_llm_knowledge(
            player, "gloomy_graveyard", "murder_mystery", ["murder_case", "knows_about_tom"]
        )
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case",
            "knows_about_tom",
        ]
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["found_body"])
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case",
            "knows_about_tom",
            "found_body",
        ]


class TestZoneLlmKnowledge:
    """add_zone_llm_knowledge is append-only and additive."""

    def test_add_zone_llm_knowledge_appends_ids(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_zone_llm_knowledge(player, "gloomy_graveyard", ["knows_about_ghost"])
        assert player.perm_variables["gloomy_graveyard.llm_knowledge"] == ["knows_about_ghost"]

    def test_add_zone_llm_knowledge_append_only_no_duplicate(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_zone_llm_knowledge(player, "gloomy_graveyard", ["found_body"])
        add_zone_llm_knowledge(player, "gloomy_graveyard", ["found_body"])
        assert player.perm_variables["gloomy_graveyard.llm_knowledge"] == ["found_body"]


class TestRemoveQuestLlmKnowledge:
    """remove_quest_llm_knowledge removes given ids from the list (replacement/supersede)."""

    def test_remove_quest_llm_knowledge_removes_ids(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_quest_llm_knowledge(
            player, "gloomy_graveyard", "murder_mystery", ["murder_case_heard", "murder_case_found_body"]
        )
        remove_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case_heard"])
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case_found_body"
        ]

    def test_remove_quest_llm_knowledge_no_op_for_missing_id(self):
        player = Character("p", "gloomy_graveyard", "P")
        player.perm_variables = {}
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case_heard"])
        remove_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["nonexistent"])
        assert player.perm_variables["gloomy_graveyard.murder_mystery.llm_knowledge"] == [
            "murder_case_heard"
        ]


class TestSetquestvarReplaces:
    """set_quest_var applies 'replaces' from knowledge_updates to remove superseded ids."""

    @pytest.fixture
    def game_state_with_replaces(self):
        """GameState with one zone and a quest var that has updates + replaces."""
        g = ComprehensiveGameState(default_app_config)
        g.zones = {}
        g.quest_index = {}
        zone = Zone("gloomy_graveyard")
        zone.name = "Gloomy Graveyard"
        quest_data = {
            "murder_mystery": {
                "title": "Murder",
                "variables": {
                    "found_body": {
                        "type": "boolean",
                        "default": False,
                        "knowledge_updates": [
                            {"condition": True, "updates": {"murder_case_found_body": True}},
                        ],
                    },
                    "quest_complete": {
                        "type": "boolean",
                        "default": False,
                        "knowledge_updates": [
                            {
                                "condition": True,
                                "updates": {"murder_case_solved": True},
                                "replaces": ["murder_case_found_body"],
                            },
                        ],
                    },
                },
                "stages": [],
            }
        }
        zone.load_quests(quest_data)
        room = Room("start", zone, "Start")
        room.zone = zone
        zone.rooms["start"] = room
        g.zones["gloomy_graveyard"] = zone
        g.build_quest_index()
        return g

    @pytest.fixture
    def player_in_replaces_state(self, game_state_with_replaces):
        zone = game_state_with_replaces.zones["gloomy_graveyard"]
        room = zone.rooms["start"]
        char = Character("testplayer", "gloomy_graveyard", "TestPlayer")
        char.perm_variables = {}
        char.send_text = AsyncMock()
        room.add_character(char)
        return char

    @pytest.mark.asyncio
    async def test_setquestvar_replaces_removes_superseded_ids(
        self, game_state_with_replaces, player_in_replaces_state
    ):
        player = player_in_replaces_state
        g = game_state_with_replaces
        # First add intermediate knowledge
        set_quest_var(player, "murder_mystery.found_body", True, auto_update_knowledge=True)
        key = "gloomy_graveyard.murder_mystery.llm_knowledge"
        assert player.perm_variables[key] == ["murder_case_found_body"]
        # Then complete quest: add murder_case_solved and replace murder_case_found_body
        set_quest_var(player, "murder_mystery.quest_complete", True, auto_update_knowledge=True)
        assert player.perm_variables[key] == ["murder_case_solved"]


class TestResolvedLlmKnowledge:
    """get_resolved_llm_knowledge resolves ids to content from zone.common_knowledge."""

    def test_resolved_returns_content_from_zone(self, game_state, player):
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["murder_case"])
        zone = game_state.zones["gloomy_graveyard"]
        zone.common_knowledge["murder_case"] = "Lord Ashford was found dead."
        resolved = get_resolved_llm_knowledge(game_state, player)
        assert resolved.get("murder_case") == "Lord Ashford was found dead."

    def test_resolved_ignores_unknown_id(self, game_state, player):
        add_quest_llm_knowledge(player, "gloomy_graveyard", "murder_mystery", ["unknown_id"])
        resolved = get_resolved_llm_knowledge(game_state, player)
        assert "unknown_id" not in resolved
