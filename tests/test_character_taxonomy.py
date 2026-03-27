import pytest

from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.player_save_manager import PlayerSaveManager


def test_character_from_yaml_loads_type_and_race():
    char = Character("taxonomy_test", "test_zone", create_reference=False)
    char.from_yaml(
        {
            "id": "taxonomy_test",
            "name": "Taxonomy Test",
            "type": "Humanoid",
            "race": "Elf",
        },
        "test_zone",
    )

    assert char.character_type == "humanoid"
    assert char.race == "elf"


@pytest.mark.asyncio
async def test_character_type_and_race_persist_through_save_load(tmp_path):
    save_mgr = PlayerSaveManager(saves_dir=str(tmp_path))

    source = Character("save_taxonomy_test", "test_zone", name="Saver", create_reference=False)
    source.character_type = "undead"
    source.race = "vampire"

    assert save_mgr.save_character(source)

    target = Character("save_taxonomy_test", "test_zone", name="Saver", create_reference=False)
    loaded = await save_mgr.load_character("Saver", target_character=target)

    assert loaded is not None
    assert target.character_type == "undead"
    assert target.race == "vampire"
