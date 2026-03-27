"""
Tests for the loot table system.

Covers:
- LOOT_TABLES YAML parsing into WorldDefinition
- Character loot field parsing (single dict and list formats)
- Loot generation logic: chance rolls, quantity selection, item creation
- Integration with spawn methods (create_from_definition, spawn_character)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from typing import Dict, Any

from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.nondb_models.objects import Object
from NextGenMUDApp.nondb_models.world import WorldDefinition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world_definition():
    wd = WorldDefinition()
    wd.loot_tables = {
        "test_zone.minor_loot": ["test_zone.healing_potion", "test_zone.mana_potion"],
        "test_zone.rare_loot": ["test_zone.magic_sword"],
    }
    return wd


@pytest.fixture
def mock_obj_def():
    """A minimal mock Object used as an object definition template."""
    obj = MagicMock(spec=Object)
    obj.name = "healing potion"
    obj.id = "healing_potion"
    obj.reference_number = 1
    obj.weight = 1
    obj.triggers_by_type = {}
    return obj


@pytest.fixture
def loot_game_state(world_definition, mock_obj_def):
    """Game state wired up so find_object_definition always returns mock_obj_def."""
    gs = MagicMock()
    gs.world_definition = world_definition
    world_definition.find_object_definition = MagicMock(return_value=mock_obj_def)
    return gs


@pytest.fixture
def base_loot_char_data() -> Dict[str, Any]:
    """Minimal character YAML data with a loot entry."""
    return {
        "id": "loot_mob",
        "name": "Loot Mob",
        "article": "a",
        "description": "A mob with loot.",
        "attributes": {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10,
        },
        "hit_dice": "1d8",
    }


# ---------------------------------------------------------------------------
# WorldDefinition.loot_tables
# ---------------------------------------------------------------------------

class TestWorldDefinitionLootTables:

    def test_loot_tables_initialised_empty(self):
        wd = WorldDefinition()
        assert wd.loot_tables == {}

    def test_loot_tables_stores_items(self, world_definition):
        assert "test_zone.minor_loot" in world_definition.loot_tables
        assert len(world_definition.loot_tables["test_zone.minor_loot"]) == 2


# ---------------------------------------------------------------------------
# Character.from_yaml loot parsing
# ---------------------------------------------------------------------------

class TestCharacterLootParsing:

    def test_loot_defaults_to_empty(self, create_test_character, base_loot_char_data):
        char = create_test_character(base_loot_char_data, zone_id="test_zone")
        assert char.loot == []

    def test_loot_list_format(self, create_test_character, base_loot_char_data):
        data = base_loot_char_data.copy()
        data["loot"] = [
            {"table": "minor_loot", "chance_percent": 10, "quantity_percent_chances": {1: 80, 2: 20}},
            {"table": "rare_loot", "chance_percent": 2, "quantity_percent_chances": {1: 100}},
        ]
        char = create_test_character(data, zone_id="test_zone")
        assert len(char.loot) == 2
        assert char.loot[0]["table"] == "minor_loot"
        assert char.loot[1]["chance_percent"] == 2

    def test_loot_single_dict_format(self, create_test_character, base_loot_char_data):
        data = base_loot_char_data.copy()
        data["loot"] = {"table": "minor_loot", "chance_percent": 5, "quantity_percent_chances": {1: 100}}
        char = create_test_character(data, zone_id="test_zone")
        assert len(char.loot) == 1
        assert char.loot[0]["table"] == "minor_loot"

    def test_loot_defaults_chance_and_quantity(self, create_test_character, base_loot_char_data):
        data = base_loot_char_data.copy()
        data["loot"] = [{"table": "minor_loot"}]
        char = create_test_character(data, zone_id="test_zone")
        assert char.loot[0]["chance_percent"] == 100
        assert char.loot[0]["quantity_percent_chances"] == {1: 100}


# ---------------------------------------------------------------------------
# _generate_loot logic
# ---------------------------------------------------------------------------

class TestGenerateLoot:

    def test_chance_roll_miss_produces_no_items(self, loot_game_state):
        char = Character("mob1", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "minor_loot", "chance_percent": 50, "quantity_percent_chances": {1: 100}}]

        # Roll 51 > 50 → miss
        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            mock_random.randint.return_value = 51
            from NextGenMUDApp.structured_logger import StructuredLogger
            logger = StructuredLogger(__name__)
            char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 0

    def test_chance_roll_hit_adds_item(self, loot_game_state, mock_obj_def):
        char = Character("mob2", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "minor_loot", "chance_percent": 50, "quantity_percent_chances": {1: 100}}]

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            mock_random.randint.return_value = 50  # 50 <= 50 → hit
            mock_random.choice.return_value = "test_zone.healing_potion"
            with patch.object(Object, "create_from_definition", return_value=MagicMock(weight=0)) as mock_create:
                mock_create.return_value.name = "healing potion"
                from NextGenMUDApp.structured_logger import StructuredLogger
                logger = StructuredLogger(__name__)
                char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 1

    def test_quantity_two_adds_two_items(self, loot_game_state, mock_obj_def):
        char = Character("mob3", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {2: 100}}]

        call_count = 0
        def make_obj(*a, **kw):
            nonlocal call_count
            call_count += 1
            m = MagicMock(weight=0)
            m.name = f"item_{call_count}"
            return m

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            # First call: chance check (1 <= 100), second call: quantity roll (1 <= 100 → qty 2)
            mock_random.randint.side_effect = [1, 1]
            mock_random.choice.return_value = "test_zone.healing_potion"
            with patch.object(Object, "create_from_definition", side_effect=make_obj):
                from NextGenMUDApp.structured_logger import StructuredLogger
                logger = StructuredLogger(__name__)
                char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 2

    def test_quantity_selection_weighted(self, loot_game_state):
        """With qty chances {1: 80, 2: 20}, a roll of 81 should pick qty 2."""
        char = Character("mob4", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 80, 2: 20}}]

        created = []
        def make_obj(*a, **kw):
            m = MagicMock(weight=0)
            m.name = f"item_{len(created)}"
            created.append(m)
            return m

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            # chance roll = 1 (hit), quantity roll = 81 (> 80, so qty 2)
            mock_random.randint.side_effect = [1, 81]
            mock_random.choice.return_value = "test_zone.healing_potion"
            with patch.object(Object, "create_from_definition", side_effect=make_obj):
                from NextGenMUDApp.structured_logger import StructuredLogger
                logger = StructuredLogger(__name__)
                char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 2

    def test_missing_loot_table_logs_warning(self, loot_game_state):
        char = Character("mob5", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "nonexistent_table", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            mock_random.randint.return_value = 1
            from NextGenMUDApp.structured_logger import StructuredLogger
            logger = StructuredLogger(__name__)
            char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 0

    def test_missing_item_def_logs_warning(self, loot_game_state):
        loot_game_state.world_definition.find_object_definition = MagicMock(return_value=None)
        char = Character("mob6", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            mock_random.randint.return_value = 1
            mock_random.choice.return_value = "test_zone.healing_potion"
            from NextGenMUDApp.structured_logger import StructuredLogger
            logger = StructuredLogger(__name__)
            char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 0

    def test_cross_zone_table_reference(self):
        """Table name like 'other_zone.rare_loot' should be resolved as-is."""
        wd = WorldDefinition()
        wd.loot_tables = {"other_zone.rare_loot": ["other_zone.magic_ring"]}
        mock_obj = MagicMock(weight=0)
        mock_obj.name = "magic ring"
        wd.find_object_definition = MagicMock(return_value=mock_obj)

        gs = MagicMock()
        gs.world_definition = wd

        char = Character("mob7", "test_zone", "Mob", create_reference=False)
        char.loot = [{"table": "other_zone.rare_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            mock_random.randint.return_value = 1
            mock_random.choice.return_value = "other_zone.magic_ring"
            with patch.object(Object, "create_from_definition", return_value=mock_obj):
                from NextGenMUDApp.structured_logger import StructuredLogger
                logger = StructuredLogger(__name__)
                char._generate_loot(gs, logger)

        assert len(char.contents) == 1

    def test_multiple_loot_entries_processed(self, loot_game_state):
        """Each loot entry should be rolled independently."""
        char = Character("mob8", "test_zone", "Mob", create_reference=False)
        char.loot = [
            {"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}},
            {"table": "rare_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}},
        ]

        created = []
        def make_obj(*a, **kw):
            m = MagicMock(weight=0)
            m.name = f"item_{len(created)}"
            created.append(m)
            return m

        with patch("NextGenMUDApp.nondb_models.characters.random") as mock_random:
            # Two entries: each needs chance roll (1) + quantity roll (1)
            mock_random.randint.side_effect = [1, 1, 1, 1]
            mock_random.choice.side_effect = ["test_zone.healing_potion", "test_zone.magic_sword"]
            with patch.object(Object, "create_from_definition", side_effect=make_obj):
                from NextGenMUDApp.structured_logger import StructuredLogger
                logger = StructuredLogger(__name__)
                char._generate_loot(loot_game_state, logger)

        assert len(char.contents) == 2


# ---------------------------------------------------------------------------
# create_from_definition integration
# ---------------------------------------------------------------------------

class TestCreateFromDefinitionLoot:

    def test_loot_cleared_after_spawn(self, create_test_character, base_loot_char_data, loot_game_state):
        """After create_from_definition, the spawned instance's loot list should be empty."""
        data = base_loot_char_data.copy()
        data["loot"] = [{"table": "minor_loot", "chance_percent": 0, "quantity_percent_chances": {1: 100}}]
        char_def = create_test_character(data, zone_id="test_zone")

        new_char = Character.create_from_definition(char_def, loot_game_state)
        assert new_char.loot == []

    def test_loot_generated_on_spawn(self, create_test_character, base_loot_char_data, loot_game_state):
        """create_from_definition should call _generate_loot when loot entries exist."""
        data = base_loot_char_data.copy()
        data["loot"] = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]
        char_def = create_test_character(data, zone_id="test_zone")

        with patch.object(Character, "_generate_loot") as mock_gen:
            new_char = Character.create_from_definition(char_def, loot_game_state)
            mock_gen.assert_called_once()

    def test_no_loot_without_game_state(self, create_test_character, base_loot_char_data):
        """Without game_state, _generate_loot should not be called."""
        data = base_loot_char_data.copy()
        data["loot"] = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]
        char_def = create_test_character(data, zone_id="test_zone")

        with patch.object(Character, "_generate_loot") as mock_gen:
            new_char = Character.create_from_definition(char_def, game_state=None)
            mock_gen.assert_not_called()

    def test_no_loot_when_include_items_false(self, create_test_character, base_loot_char_data, loot_game_state):
        """When include_items=False, _generate_loot should not be called."""
        data = base_loot_char_data.copy()
        data["loot"] = [{"table": "minor_loot", "chance_percent": 100, "quantity_percent_chances": {1: 100}}]
        char_def = create_test_character(data, zone_id="test_zone")

        with patch.object(Character, "_generate_loot") as mock_gen:
            new_char = Character.create_from_definition(char_def, loot_game_state, include_items=False)
            mock_gen.assert_not_called()
