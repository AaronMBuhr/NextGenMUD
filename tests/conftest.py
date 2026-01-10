"""
Shared pytest fixtures for NextGenMUD tests.

This module provides common test fixtures used across multiple test files,
including mock characters, game state, and other test utilities.
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings before importing Django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NextGenMUD.settings')

import django
django.setup()


# Store exit status for later use
_pytest_exit_status = 0

def pytest_sessionfinish(session, exitstatus):
    global _pytest_exit_status
    _pytest_exit_status = exitstatus

# Hard-exit after pytest is fully done (including summary) to avoid hang on Windows
def pytest_unconfigure(config):
    import sys
    import os
    # Flush output buffers before hard exit so file redirects capture everything
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_pytest_exit_status)

from NextGenMUDApp.constants import CharacterClassRole, Constants
from NextGenMUDApp.nondb_models.character_interface import (
    CharacterAttributes, EquipLocation, PermanentCharacterFlags, 
    TemporaryCharacterFlags, GamePermissionFlags
)
from NextGenMUDApp.nondb_models.attacks_and_damage import DamageType, DamageMultipliers


@pytest.fixture
def mock_game_state():
    """Create a mock game state for testing."""
    game_state = MagicMock()
    game_state.world_clock_tick = 100
    game_state.current_tick = 100
    game_state.find_target_character = MagicMock(return_value=None)
    game_state.find_target_object = MagicMock(return_value=None)
    game_state.add_scheduled_event = MagicMock()
    return game_state


@pytest.fixture
def base_character_data() -> Dict[str, Any]:
    """Base YAML-like data for creating a test character."""
    return {
        'name': 'Test Character',
        'article': 'a',
        'description': 'A test character for unit testing.',
        'pronoun_subject': 'they',
        'pronoun_object': 'them',
        'pronoun_possessive': 'their',
        'attributes': {
            'strength': 14,
            'dexterity': 12,
            'constitution': 13,
            'intelligence': 10,
            'wisdom': 11,
            'charisma': 10
        },
        'hit_dice': '3d10+9',
        'natural_attacks': [
            {
                'attack_noun': 'fist',
                'attack_verb': 'punches',
                'potential_damage': [
                    {'damage_type': 'bludgeoning', 'damage_dice': '1d4+2'}
                ]
            }
        ]
    }


@pytest.fixture
def fighter_character_data(base_character_data) -> Dict[str, Any]:
    """Character data for a fighter."""
    data = base_character_data.copy()
    data['name'] = 'Test Fighter'
    data['class'] = {
        'fighter': {
            'level': 5
        }
    }
    data['attributes']['strength'] = 16
    data['attributes']['constitution'] = 15
    return data


@pytest.fixture  
def mage_character_data(base_character_data) -> Dict[str, Any]:
    """Character data for a mage."""
    data = base_character_data.copy()
    data['name'] = 'Test Mage'
    data['class'] = {
        'mage': {
            'level': 5
        }
    }
    data['attributes']['intelligence'] = 16
    data['attributes']['wisdom'] = 14
    return data


@pytest.fixture
def rogue_character_data(base_character_data) -> Dict[str, Any]:
    """Character data for a rogue."""
    data = base_character_data.copy()
    data['name'] = 'Test Rogue'
    data['class'] = {
        'rogue': {
            'level': 5
        }
    }
    data['attributes']['dexterity'] = 16
    return data


@pytest.fixture
def multiclass_character_data(base_character_data) -> Dict[str, Any]:
    """Character data for a multiclass fighter/mage."""
    data = base_character_data.copy()
    data['name'] = 'Test Multiclass'
    data['class'] = {
        'fighter': {'level': 3},
        'mage': {'level': 2}
    }
    data['class_priority'] = ['fighter', 'mage']
    data['attributes']['strength'] = 14
    data['attributes']['intelligence'] = 14
    return data


@pytest.fixture
def create_test_character(mock_game_state):
    """Factory fixture to create test characters from YAML data."""
    from NextGenMUDApp.nondb_models.characters import Character
    from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
    from NextGenMUDApp.skills_core import SkillsRegistry
    
    # Set up the game state interface
    GameStateInterface.set_instance(mock_game_state)
    
    # Ensure skills are registered for auto-population to work
    SkillsRegistry.register_skill_classes()
    
    def _create(yaml_data: Dict[str, Any], zone_id: str = "test_zone") -> 'Character':
        char = Character(yaml_data.get('id', 'test_char'), zone_id, yaml_data.get('name', 'Test'))
        char.from_yaml(yaml_data, zone_id)
        return char
    
    return _create


@pytest.fixture
def test_fighter(create_test_character, fighter_character_data):
    """Create a test fighter character."""
    return create_test_character(fighter_character_data)


@pytest.fixture
def test_mage(create_test_character, mage_character_data):
    """Create a test mage character."""
    return create_test_character(mage_character_data)


@pytest.fixture
def test_rogue(create_test_character, rogue_character_data):
    """Create a test rogue character."""
    return create_test_character(rogue_character_data)


@pytest.fixture
def mock_room():
    """Create a mock room for testing."""
    room = MagicMock()
    room.characters = []
    room.objects = []
    room.rid = "test_zone.test_room"
    room.name = "Test Room"
    room.echo = AsyncMock()
    room.get_nearby_enemies = MagicMock(return_value=[])
    room.get_nearby_allies = MagicMock(return_value=[])
    return room


@pytest.fixture
def mock_connection():
    """Create a mock connection for testing."""
    conn = MagicMock()
    conn.send = AsyncMock()  # Main send method used by send_status_update
    conn.send_text = AsyncMock()
    conn.send_json = AsyncMock()
    return conn


# Utility functions for tests
def create_mock_character(
    name: str = "Mock Character",
    hp: int = 100,
    max_hp: int = 100,
    mana: int = 50,
    max_mana: int = 50,
    stamina: int = 50,
    max_stamina: int = 50,
    is_pc: bool = False
) -> MagicMock:
    """
    Create a fully mocked character for tests that don't need full Character objects.
    """
    char = MagicMock()
    char.name = name
    char.art_name = f"the {name.lower()}"
    char.art_name_cap = f"The {name}"
    char.rid = f"mock.{name.lower().replace(' ', '_')}"
    
    char.current_hit_points = hp
    char.max_hit_points = max_hp
    char.current_mana = mana
    char.max_mana = max_mana
    char.current_stamina = stamina
    char.max_stamina = max_stamina
    
    char.levels_by_role = {}
    char.skill_levels_by_role = {}
    char.class_priority = []
    char.attributes = {attr: 10 for attr in CharacterAttributes}
    
    char.permanent_character_flags = PermanentCharacterFlags(0)
    char.temporary_character_flags = TemporaryCharacterFlags(0)
    
    if is_pc:
        char.permanent_character_flags = char.permanent_character_flags.add_flags(
            PermanentCharacterFlags.IS_PC
        )
    
    char.has_perm_flags = MagicMock(side_effect=lambda f: char.permanent_character_flags.are_flags_set(f))
    char.has_temp_flags = MagicMock(side_effect=lambda f: char.temporary_character_flags.are_flags_set(f))
    
    char.fighting_whom = None
    char.cooldowns = []
    char.has_cooldown = MagicMock(return_value=False)
    char.command_queue = []
    char.current_states = []
    
    char.echo = AsyncMock()
    char.send_text = AsyncMock()
    
    return char
