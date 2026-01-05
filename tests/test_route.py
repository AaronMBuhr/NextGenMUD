"""
Unit tests for route and walkto commands.

Tests cover:
- Pathfinding algorithm (find_path)
- Direction abbreviation conversion (get_route_string)
- Route command output
- Walkto command queue behavior
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from NextGenMUDApp.nondb_models.actor_interface import ActorType
from NextGenMUDApp.nondb_models.room_interface import Exit
from NextGenMUDApp.command_handler import CommandHandler

from tests.conftest import create_mock_character


# Get the command handler instance for testing
def get_handler():
    """Get a CommandHandler instance for testing."""
    return CommandHandler()


def create_mock_room(room_id: str, zone_id: str = "test_zone", name: str = None):
    """Create a mock room with proper structure for pathfinding tests."""
    room = MagicMock()
    room.id = room_id
    room.rid = f"{zone_id}.{room_id}"
    room.name = name or f"Room {room_id}"
    room.exits = {}
    room.characters = []
    room.contents = []
    room.echo = AsyncMock()
    
    # Create a mock zone
    zone = MagicMock()
    zone.id = zone_id
    zone.rooms = {}
    room.zone = zone
    
    # For location_room property
    room.location_room = room
    room.art_name = f"the {room.name.lower()}"
    room.art_name_cap = f"The {room.name}"
    
    return room


def create_mock_exit(destination: str):
    """Create a mock exit object."""
    exit_obj = MagicMock(spec=Exit)
    exit_obj.destination = destination
    exit_obj.has_door = False
    exit_obj.is_closed = False
    exit_obj.is_locked = False
    return exit_obj


def create_mock_game_state_with_zones(zones_dict):
    """Create a mock game state with the given zones structure.
    
    zones_dict format: {zone_id: {room_id: room_mock, ...}, ...}
    """
    game_state = MagicMock()
    game_state.zones = {}
    
    for zone_id, rooms in zones_dict.items():
        zone = MagicMock()
        zone.id = zone_id
        zone.rooms = rooms
        game_state.zones[zone_id] = zone
        
        # Update each room's zone reference
        for room_id, room in rooms.items():
            room.zone = zone
            zone.rooms[room_id] = room
    
    def get_zone_by_id(zone_id):
        return game_state.zones.get(zone_id)
    
    game_state.get_zone_by_id = get_zone_by_id
    
    return game_state


class TestDirectionAbbreviations:
    """Tests for direction abbreviation mapping."""
    
    def test_full_direction_names(self):
        """Full direction names should convert to abbreviations."""
        # Test the class attribute directly
        assert CommandHandler.DIRECTION_ABBREV['north'] == 'N'
        assert CommandHandler.DIRECTION_ABBREV['south'] == 'S'
        assert CommandHandler.DIRECTION_ABBREV['east'] == 'E'
        assert CommandHandler.DIRECTION_ABBREV['west'] == 'W'
        assert CommandHandler.DIRECTION_ABBREV['up'] == 'U'
        assert CommandHandler.DIRECTION_ABBREV['down'] == 'D'
    
    def test_short_direction_names(self):
        """Short direction names should also map correctly."""
        assert CommandHandler.DIRECTION_ABBREV['n'] == 'N'
        assert CommandHandler.DIRECTION_ABBREV['s'] == 'S'
        assert CommandHandler.DIRECTION_ABBREV['e'] == 'E'
        assert CommandHandler.DIRECTION_ABBREV['w'] == 'W'
        assert CommandHandler.DIRECTION_ABBREV['u'] == 'U'
        assert CommandHandler.DIRECTION_ABBREV['d'] == 'D'
    
    def test_special_directions(self):
        """Special directions like in/out should map correctly."""
        assert CommandHandler.DIRECTION_ABBREV['in'] == 'IN'
        assert CommandHandler.DIRECTION_ABBREV['out'] == 'OUT'


class TestGetRouteString:
    """Tests for get_route_string function."""
    
    def test_empty_path(self):
        """Empty path should return empty string."""
        handler = get_handler()
        result = handler.get_route_string([])
        assert result == ""
    
    def test_single_direction(self):
        """Single direction path should return single abbreviation."""
        handler = get_handler()
        result = handler.get_route_string(['north'])
        assert result == "N"
    
    def test_multiple_directions(self):
        """Multiple directions should be space-separated."""
        handler = get_handler()
        result = handler.get_route_string(['east', 'east', 'south', 'down'])
        assert result == "E E S D"
    
    def test_mixed_case_input(self):
        """Should handle mixed case input."""
        handler = get_handler()
        result = handler.get_route_string(['NORTH', 'South', 'EAST'])
        assert result == "N S E"
    
    def test_unknown_direction_uppercased(self):
        """Unknown directions should be uppercased."""
        handler = get_handler()
        result = handler.get_route_string(['northeast', 'portal'])
        assert result == "NORTHEAST PORTAL"
    
    def test_complex_route(self):
        """Test a complex route like user example."""
        handler = get_handler()
        result = handler.get_route_string(['east', 'east', 'south', 'down', 'east', 'north', 'up'])
        assert result == "E E S D E N U"


class TestFindPath:
    """Tests for the find_path BFS algorithm."""
    
    def test_same_room_returns_empty_path(self):
        """When start and target are the same room, return empty list."""
        handler = get_handler()
        room = create_mock_room("room1")
        
        result = handler.find_path(room, room)
        assert result == []
    
    def test_direct_connection(self):
        """Should find path between directly connected rooms."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        
        # room1 -> east -> room2
        room1.exits['east'] = create_mock_exit('room2')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2}}
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room2)
        
        assert result == ['east']
    
    def test_two_hop_path(self):
        """Should find path through intermediate room."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        room3 = create_mock_room("room3")
        
        # room1 -> north -> room2 -> east -> room3
        room1.exits['north'] = create_mock_exit('room2')
        room2.exits['east'] = create_mock_exit('room3')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2, 'room3': room3}}
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room3)
        
        assert result == ['north', 'east']
    
    def test_no_path_returns_none(self):
        """Should return None when no path exists."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        
        # No exits from room1
        
        zones = {'test_zone': {'room1': room1, 'room2': room2}}
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room2)
        
        assert result is None
    
    def test_finds_shortest_path(self):
        """Should find shortest path when multiple routes exist."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        room3 = create_mock_room("room3")
        room4 = create_mock_room("room4")
        
        # Short path: room1 -> east -> room4
        # Long path: room1 -> north -> room2 -> east -> room3 -> south -> room4
        room1.exits['east'] = create_mock_exit('room4')
        room1.exits['north'] = create_mock_exit('room2')
        room2.exits['east'] = create_mock_exit('room3')
        room3.exits['south'] = create_mock_exit('room4')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2, 'room3': room3, 'room4': room4}}
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room4)
        
        # Should find the direct east path
        assert result == ['east']
    
    def test_cross_zone_path(self):
        """Should find path across zones."""
        handler = get_handler()
        
        room1 = create_mock_room("room1", "zone1")
        room2 = create_mock_room("room2", "zone2")
        
        # room1 -> south -> zone2.room2
        room1.exits['south'] = create_mock_exit('zone2.room2')
        
        zones = {
            'zone1': {'room1': room1},
            'zone2': {'room2': room2}
        }
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room2)
        
        assert result == ['south']
    
    def test_handles_invalid_destination(self):
        """Should skip exits with invalid destinations."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        
        # One valid exit, one invalid
        room1.exits['north'] = create_mock_exit('nonexistent_room')
        room1.exits['east'] = create_mock_exit('room2')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2}}
        game_state = create_mock_game_state_with_zones(zones)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            result = handler.find_path(room1, room2)
        
        # Should find the valid path
        assert result == ['east']


class TestCmdRoute:
    """Tests for the route command."""
    
    @pytest.fixture
    def setup_route_test(self):
        """Set up rooms and game state for route testing."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        room3 = create_mock_room("room3")
        
        room1.exits['east'] = create_mock_exit('room2')
        room2.exits['south'] = create_mock_exit('room3')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2, 'room3': room3}}
        game_state = create_mock_game_state_with_zones(zones)
        game_state.find_target_character = MagicMock(return_value=None)
        game_state.find_target_object = MagicMock(return_value=None)
        game_state.find_target_room = MagicMock(return_value=room3)
        
        actor = create_mock_character()
        actor.location_room = room1
        
        return handler, game_state, actor, room1, room2, room3
    
    @pytest.mark.asyncio
    async def test_route_no_input(self, setup_route_test):
        """Route with no input should prompt for target."""
        handler, game_state, actor, room1, room2, room3 = setup_route_test
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_route(actor, "")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "Route to what?" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_route_already_there(self, setup_route_test):
        """Route should say 'already there' if at target location."""
        handler, game_state, actor, room1, room2, room3 = setup_route_test
        
        game_state.find_target_room = MagicMock(return_value=room1)  # Same as actor's room
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_route(actor, "room1")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "already there" in call_args[1].lower()
    
    @pytest.mark.asyncio
    async def test_route_outputs_directions(self, setup_route_test):
        """Route should output abbreviated directions."""
        handler, game_state, actor, room1, room2, room3 = setup_route_test
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_route(actor, "room3")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert call_args[1] == "E S"
    
    @pytest.mark.asyncio
    async def test_route_no_path_found(self):
        """Route should say 'No route exists.' when target exists but unreachable."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")  # Disconnected
        
        zones = {'test_zone': {'room1': room1, 'room2': room2}}
        game_state = create_mock_game_state_with_zones(zones)
        game_state.find_target_character = MagicMock(return_value=None)
        game_state.find_target_object = MagicMock(return_value=None)
        game_state.find_target_room = MagicMock(return_value=room2)
        
        actor = create_mock_character()
        actor.location_room = room1
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_route(actor, "room2")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "No route exists." in call_args[1]
    
    @pytest.mark.asyncio
    async def test_route_target_not_found(self):
        """Route should say 'Target can't be found.' when target doesn't exist."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        
        zones = {'test_zone': {'room1': room1}}
        game_state = create_mock_game_state_with_zones(zones)
        game_state.find_target_character = MagicMock(return_value=None)
        game_state.find_target_object = MagicMock(return_value=None)
        game_state.find_target_room = MagicMock(return_value=None)
        
        actor = create_mock_character()
        actor.location_room = room1
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_route(actor, "nonexistent")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "Target can't be found." in call_args[1]


class TestCmdWalkto:
    """Tests for the walkto command."""
    
    @pytest.fixture
    def setup_walkto_test(self):
        """Set up rooms and game state for walkto testing."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        room3 = create_mock_room("room3")
        
        room1.exits['north'] = create_mock_exit('room2')
        room2.exits['west'] = create_mock_exit('room3')
        
        zones = {'test_zone': {'room1': room1, 'room2': room2, 'room3': room3}}
        game_state = create_mock_game_state_with_zones(zones)
        game_state.find_target_character = MagicMock(return_value=None)
        game_state.find_target_object = MagicMock(return_value=None)
        game_state.find_target_room = MagicMock(return_value=room3)
        
        actor = create_mock_character()
        actor.location_room = room1
        actor.command_queue = []
        
        return handler, game_state, actor, room1, room2, room3
    
    @pytest.mark.asyncio
    async def test_walkto_queues_commands(self, setup_walkto_test):
        """Walkto should add movement commands to command queue."""
        handler, game_state, actor, room1, room2, room3 = setup_walkto_test
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_walkto(actor, "room3")
        
        assert actor.command_queue == ['north', 'west']
    
    @pytest.mark.asyncio
    async def test_walkto_outputs_route(self, setup_walkto_test):
        """Walkto should output the walking route."""
        handler, game_state, actor, room1, room2, room3 = setup_walkto_test
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_walkto(actor, "room3")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "Walking:" in call_args[1]
        assert "N W" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_walkto_no_input(self, setup_walkto_test):
        """Walkto with no input should prompt for target."""
        handler, game_state, actor, room1, room2, room3 = setup_walkto_test
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_walkto(actor, "")
        
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "Walk to what?" in call_args[1]
        assert actor.command_queue == []
    
    @pytest.mark.asyncio
    async def test_walkto_already_there(self, setup_walkto_test):
        """Walkto should not queue commands if already at target."""
        handler, game_state, actor, room1, room2, room3 = setup_walkto_test
        
        game_state.find_target_room = MagicMock(return_value=room1)
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_walkto(actor, "room1")
        
        assert actor.command_queue == []
        actor.send_text.assert_called()
        call_args = actor.send_text.call_args[0]
        assert "already there" in call_args[1].lower()
    
    @pytest.mark.asyncio
    async def test_walkto_to_character(self):
        """Walkto should work with character targets."""
        handler = get_handler()
        
        room1 = create_mock_room("room1")
        room2 = create_mock_room("room2")
        
        room1.exits['south'] = create_mock_exit('room2')
        
        target_npc = create_mock_character(name="Guard")
        target_npc.location_room = room2
        
        zones = {'test_zone': {'room1': room1, 'room2': room2}}
        game_state = create_mock_game_state_with_zones(zones)
        game_state.find_target_character = MagicMock(return_value=target_npc)
        game_state.find_target_object = MagicMock(return_value=None)
        game_state.find_target_room = MagicMock(return_value=None)
        
        actor = create_mock_character()
        actor.location_room = room1
        actor.command_queue = []
        
        with patch.object(CommandHandler, '_game_state', game_state):
            await handler.cmd_walkto(actor, "guard")
        
        assert actor.command_queue == ['south']
