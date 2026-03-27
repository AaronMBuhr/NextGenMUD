from unittest.mock import MagicMock

from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.nondb_models.objects import Object
from NextGenMUDApp.nondb_models.rooms import Room


def test_character_definition_perm_variables_applied_on_instance():
    char_def = Character("test_char", "test_zone", "Template Character", create_reference=False)
    char_def.from_yaml(
        {
            "name": "Template Character",
            "description": "Template",
            "class": {"fighter": {"level": 1}},
            "perm_variables": {
                "quest_stage": 2,
                "flags": ["met_guard", "opened_gate"],
            },
        },
        "test_zone",
    )

    instance = Character.create_from_definition(char_def, game_state=MagicMock(), include_items=False)

    assert instance.perm_variables["quest_stage"] == 2
    assert instance.perm_variables["flags"] == ["met_guard", "opened_gate"]

    # Verify instance vars are a separate copy from definition vars.
    instance.perm_variables["flags"].append("changed_on_instance")
    assert char_def.perm_variables["flags"] == ["met_guard", "opened_gate"]


def test_object_definition_perm_variables_applied_on_instance():
    obj_def = Object("template_obj", "test_zone", "Template Object", create_reference=False)
    obj_def.from_yaml(
        {
            "id": "template_obj",
            "name": "Template Object",
            "description": "Template object",
            "perm_variables": {
                "owner": "guild",
                "charges_used": 0,
            },
        },
        "test_zone",
        game_state=MagicMock(),
    )

    instance = Object.create_from_definition(obj_def)

    assert instance.perm_variables["owner"] == "guild"
    assert instance.perm_variables["charges_used"] == 0


def test_room_perm_variables_loaded_from_yaml():
    zone = MagicMock()
    zone.id = "test_zone"

    room = Room("room_1", zone, create_reference=False)
    room.from_yaml(
        zone,
        {
            "name": "Test Room",
            "description": "A test room.",
            "exits": {},
            "perm_variables": {
                "weather": "rainy",
                "lights_on": True,
            },
        },
    )

    assert room.perm_variables["weather"] == "rainy"
    assert room.perm_variables["lights_on"] is True
