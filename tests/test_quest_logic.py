"""
Unit tests for Quest logic and parsing.

Verifies that Quest objects parse correctly and evaluate player state
accurately without running the full game engine.
"""

import pytest
from unittest.mock import MagicMock

from NextGenMUDApp.nondb_models.quests import Quest, QuestStage, QuestCondition
from NextGenMUDApp.nondb_models.zone import Zone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_actor():
    """A simple mock acting as a player with perm_variables."""
    actor = MagicMock()
    actor.perm_variables = {}
    actor.location_room = None
    actor.definition_zone_id = None
    return actor


@pytest.fixture
def sample_quest_data():
    """Dictionary representing a standard quest: Title, Description, 3 stages."""
    return {
        "test_quest": {
            "title": "The Test Quest",
            "stages": [
                {
                    "name": "start",
                    "sequence": 10,
                    "description": "You have begun the quest.",
                    "conditions": {"test_quest.started": True},
                },
                {
                    "name": "progress",
                    "sequence": 20,
                    "description": "You are making progress.",
                    "conditions": {"test_quest.started": True, "test_quest.progress": True},
                },
                {
                    "name": "complete",
                    "sequence": 30,
                    "description": "You have completed the quest.",
                    "conditions": {"test_quest.completed": True},
                },
            ],
        }
    }


# ---------------------------------------------------------------------------
# Test: Quest initialization (YAML → Python mapping)
# ---------------------------------------------------------------------------


class TestQuestInitialization:
    """Ensure YAML data is correctly mapped to Python objects."""

    def test_quest_initialization(self, sample_quest_data, mock_actor):
        """Create a Quest via Zone parsing; check title, id, and stage count."""
        zone = Zone("test_zone")
        zone.load_quests(sample_quest_data)

        quest = zone.quests["test_quest"]
        assert quest is not None
        assert quest.title == "The Test Quest"
        assert quest.id == "test_zone.test_quest"
        assert len(quest.stages) == 3


# ---------------------------------------------------------------------------
# Test: Stage sequence priority (descending order)
# ---------------------------------------------------------------------------


class TestStageSequencePriority:
    """Verify the Descending Sequence Order rule (highest ID wins)."""

    def test_stage_sequence_priority(self, mock_actor):
        """When both Stage 10 and Stage 100 conditions are met, Stage 100 must win."""
        zone = Zone("priority_zone")
        zone.load_quests({
            "priority_quest": {
                "title": "Priority Quest",
                "stages": [
                    {
                        "name": "start",
                        "sequence": 10,
                        "description": "Start stage.",
                        "conditions": {"priority_quest.flag": "x"},
                    },
                    {
                        "name": "complete",
                        "sequence": 100,
                        "description": "Complete stage.",
                        "conditions": {"priority_quest.flag": "x"},
                    },
                ],
            }
        })

        quest = zone.quests["priority_quest"]
        mock_actor.definition_zone_id = "priority_zone"
        mock_actor.perm_variables["priority_zone.priority_quest.flag"] = "x"

        active = quest.get_active_stage(mock_actor)
        assert active is not None
        assert active.sequence == 100
        assert active.name == "complete"


# ---------------------------------------------------------------------------
# Test: Condition operators (math/logic engine)
# ---------------------------------------------------------------------------


class TestConditionOperators:
    """Validate condition operators: eq, neq, numgt, numlt, numgte, contains."""

    def test_condition_operators_eq_neq(self, mock_actor):
        """eq and neq operators."""
        zone = Zone("op_zone")
        zone.load_quests({
            "op_quest": {
                "title": "Operator Quest",
                "stages": [
                    {
                        "name": "eq_stage",
                        "sequence": 10,
                        "description": "Match eq.",
                        "conditions": {"op_quest.status": {"op": "eq", "val": "active"}},
                    },
                    {
                        "name": "neq_stage",
                        "sequence": 20,
                        "description": "Match neq.",
                        "conditions": {"op_quest.status": {"op": "neq", "val": "inactive"}},
                    },
                ],
            }
        })
        quest = zone.quests["op_quest"]
        mock_actor.definition_zone_id = "op_zone"
        mock_actor.perm_variables["op_zone.op_quest.status"] = "active"

        active = quest.get_active_stage(mock_actor)
        assert active is not None
        assert active.name == "neq_stage"  # higher sequence, both match

    def test_condition_operators_numgte_edge_cases(self, mock_actor):
        """numgte: kills 9 vs 10 — only 10 should satisfy kills >= 10."""
        zone = Zone("kills_zone")
        zone.load_quests({
            "kills_quest": {
                "title": "Kills Quest",
                "stages": [
                    {
                        "name": "in_progress",
                        "sequence": 10,
                        "description": "Not enough kills.",
                        "conditions": {"kills_quest.kills": {"op": "numlt", "val": 10}},
                    },
                    {
                        "name": "complete",
                        "sequence": 20,
                        "description": "Enough kills.",
                        "conditions": {"kills_quest.kills": {"op": "numgte", "val": 10}},
                    },
                ],
            }
        })
        quest = zone.quests["kills_quest"]
        mock_actor.definition_zone_id = "kills_zone"

        mock_actor.perm_variables["kills_zone.kills_quest.kills"] = 9
        active_9 = quest.get_active_stage(mock_actor)
        assert active_9 is not None
        assert active_9.name == "in_progress"

        mock_actor.perm_variables["kills_zone.kills_quest.kills"] = 10
        active_10 = quest.get_active_stage(mock_actor)
        assert active_10 is not None
        assert active_10.name == "complete"

    def test_condition_operators_numgt_numlt(self, mock_actor):
        """numgt and numlt."""
        zone = Zone("cmp_zone")
        zone.load_quests({
            "cmp_quest": {
                "title": "Compare Quest",
                "stages": [
                    {
                        "name": "low",
                        "sequence": 10,
                        "description": "Value is low.",
                        "conditions": {"cmp_quest.x": {"op": "numlt", "val": 5}},
                    },
                    {
                        "name": "high",
                        "sequence": 20,
                        "description": "Value is high.",
                        "conditions": {"cmp_quest.x": {"op": "numgt", "val": 5}},
                    },
                ],
            }
        })
        quest = zone.quests["cmp_quest"]
        mock_actor.definition_zone_id = "cmp_zone"

        mock_actor.perm_variables["cmp_zone.cmp_quest.x"] = 3
        active_low = quest.get_active_stage(mock_actor)
        assert active_low is not None
        assert active_low.name == "low"

        mock_actor.perm_variables["cmp_zone.cmp_quest.x"] = 7
        active_high = quest.get_active_stage(mock_actor)
        assert active_high is not None
        assert active_high.name == "high"

    def test_condition_operators_contains(self, mock_actor):
        """contains operator for string substring."""
        zone = Zone("str_zone")
        zone.load_quests({
            "str_quest": {
                "title": "String Quest",
                "stages": [
                    {
                        "name": "found",
                        "sequence": 10,
                        "description": "Found the word.",
                        "conditions": {"str_quest.phrase": {"op": "contains", "val": "secret"}},
                    },
                ],
            }
        })
        quest = zone.quests["str_quest"]
        mock_actor.definition_zone_id = "str_zone"
        mock_actor.perm_variables["str_zone.str_quest.phrase"] = "the secret door"

        active = quest.get_active_stage(mock_actor)
        assert active is not None
        assert active.name == "found"


# ---------------------------------------------------------------------------
# Test: Missing variable handling (no crash)
# ---------------------------------------------------------------------------


class TestMissingVariableHandling:
    """When a stage requires a variable that is not set, must not crash."""

    def test_missing_variable_handling(self, mock_actor):
        """Stage requires found_key: true; perm_variables is empty; get_active_stage returns None."""
        zone = Zone("missing_zone")
        zone.load_quests({
            "missing_quest": {
                "title": "Missing Var Quest",
                "stages": [
                    {
                        "name": "needs_key",
                        "sequence": 10,
                        "description": "You need the key.",
                        "conditions": {"missing_quest.found_key": True},
                    },
                ],
            }
        })
        quest = zone.quests["missing_quest"]
        mock_actor.perm_variables = {}

        active = quest.get_active_stage(mock_actor)
        assert active is None
