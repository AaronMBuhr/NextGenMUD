"""
Unit tests for the ON_ATTACKED trigger system.

Tests cover:
- TriggerOnAttacked class creation and configuration
- Trigger firing when attacks are attempted (before hit/miss)
- Variable availability (%S%, %a%, %A%, %attack_noun%, %attack_verb%)
- Trigger criteria evaluation
- Factory method registration
- Integration with do_single_attack
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from NextGenMUDApp.nondb_models.trigger_interface import TriggerType, TriggerFlags
from NextGenMUDApp.nondb_models.triggers import Trigger, TriggerOnAttacked
from NextGenMUDApp.nondb_models.actor_interface import ActorType
from NextGenMUDApp.nondb_models.attacks_and_damage import AttackData, DamageType

from tests.conftest import create_mock_character


class TestTriggerTypeEnum:
    """Tests for ON_ATTACKED in TriggerType enum."""
    
    def test_on_attacked_exists_in_enum(self):
        """ON_ATTACKED should be defined in TriggerType enum."""
        assert hasattr(TriggerType, 'ON_ATTACKED')
    
    def test_on_attacked_has_unique_value(self):
        """ON_ATTACKED should have a unique enum value."""
        assert TriggerType.ON_ATTACKED.value == 16
    
    def test_on_attacked_string_representation(self):
        """ON_ATTACKED should have proper string representation."""
        assert "ON_ATTACKED" in str(TriggerType.ON_ATTACKED)


class TestTriggerOnAttackedClass:
    """Tests for the TriggerOnAttacked class."""
    
    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor (NPC) that owns the trigger."""
        actor = create_mock_character(name="Guard")
        actor.actor_type = ActorType.CHARACTER
        actor.reference_number = "C1"
        actor.rid = "C1{guard}"
        actor.id = "guard"
        actor.command_queue = []
        actor.get_vars = MagicMock(return_value={'s_name': 'Guard'})
        return actor
    
    @pytest.fixture
    def mock_attacker(self):
        """Create a mock attacker character."""
        attacker = create_mock_character(name="Player", is_pc=True)
        attacker.actor_type = ActorType.CHARACTER
        attacker.reference_number = "C2"
        attacker.rid = "C2{player}"
        attacker.pronoun_subject = "they"
        attacker.pronoun_object = "them"
        attacker.pronoun_possessive = "their"
        attacker.get_vars = MagicMock(return_value={'a_name': 'Player'})
        return attacker
    
    def test_trigger_creation(self, mock_actor):
        """TriggerOnAttacked should be creatable with required arguments."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        
        assert trigger.id == "test_trigger"
        assert trigger.trigger_type_ == TriggerType.ON_ATTACKED
        assert trigger.actor_ == mock_actor
        assert trigger.disabled_ == False
    
    def test_trigger_starts_enabled(self, mock_actor):
        """Trigger with disabled=False should start enabled."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        
        assert trigger.disabled_ == False
    
    def test_trigger_starts_disabled(self, mock_actor):
        """Trigger with disabled=True should start disabled."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=True)
        
        assert trigger.disabled_ == True
    
    @pytest.mark.asyncio
    async def test_trigger_does_not_run_when_disabled(self, mock_actor, mock_attacker):
        """Disabled trigger should not execute."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=True)
        trigger.script_ = "say I'm being attacked!"
        
        mock_game_state = MagicMock()
        result = await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert result == False
    
    @pytest.mark.asyncio
    async def test_trigger_runs_when_enabled(self, mock_actor, mock_attacker):
        """Enabled trigger should execute."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.script_ = "say I'm being attacked!"
        trigger.criteria_ = []
        
        # Mock the execute_trigger_script method
        trigger.execute_trigger_script = AsyncMock()
        
        mock_game_state = MagicMock()
        result = await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert result == True
        trigger.execute_trigger_script.assert_called_once()


class TestTriggerOnAttackedVariables:
    """Tests for variable availability in ON_ATTACKED trigger."""
    
    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor that owns the trigger."""
        actor = create_mock_character(name="Guard")
        actor.actor_type = ActorType.CHARACTER
        actor.reference_number = "C1"
        actor.rid = "C1{guard}"
        actor.get_vars = MagicMock(return_value={'s_name': 'Guard', 's_hp': 100})
        return actor
    
    @pytest.fixture
    def mock_attacker(self):
        """Create a mock attacker."""
        attacker = create_mock_character(name="Player", is_pc=True)
        attacker.actor_type = ActorType.CHARACTER
        attacker.reference_number = "C2"
        attacker.pronoun_subject = "they"
        attacker.pronoun_object = "them"
        attacker.pronoun_possessive = "their"
        attacker.get_vars = MagicMock(return_value={'a_name': 'Player', 'a_hp': 50})
        return attacker
    
    @pytest.mark.asyncio
    async def test_attacker_variables_available(self, mock_actor, mock_attacker):
        """Attacker info should be available as %a% and %A%."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.criteria_ = []
        
        captured_vars = {}
        
        async def capture_vars(actor, vars, game_state):
            captured_vars.update(vars)
        
        trigger.execute_trigger_script = capture_vars
        
        mock_game_state = MagicMock()
        await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert 'a' in captured_vars  # Attacker name
        assert 'A' in captured_vars  # Attacker reference
        assert captured_vars['a'] == "Player"
    
    @pytest.mark.asyncio
    async def test_defender_variables_available(self, mock_actor, mock_attacker):
        """Defender (trigger owner) info should be available as %s% and %S%."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.criteria_ = []
        
        captured_vars = {}
        
        async def capture_vars(actor, vars, game_state):
            captured_vars.update(vars)
        
        trigger.execute_trigger_script = capture_vars
        
        mock_game_state = MagicMock()
        await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert 's' in captured_vars  # Defender name
        assert 'S' in captured_vars  # Defender reference
        assert captured_vars['s'] == "Guard"
    
    @pytest.mark.asyncio
    async def test_attack_info_passed_through(self, mock_actor, mock_attacker):
        """Attack info (noun, verb) should be passed through vars."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.criteria_ = []
        
        captured_vars = {}
        
        async def capture_vars(actor, vars, game_state):
            captured_vars.update(vars)
        
        trigger.execute_trigger_script = capture_vars
        
        mock_game_state = MagicMock()
        
        # Pass attack info in vars like core_actions.py does
        attack_vars = {
            'attack_noun': 'sword',
            'attack_verb': 'slashes'
        }
        
        await trigger.run(mock_attacker, "", attack_vars, mock_game_state)
        
        assert captured_vars.get('attack_noun') == 'sword'
        assert captured_vars.get('attack_verb') == 'slashes'


class TestTriggerFactoryMethod:
    """Tests for Trigger.new_trigger() factory method with ON_ATTACKED."""
    
    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor for trigger creation."""
        actor = create_mock_character(name="TestNPC")
        actor.rid = "C1{test}"
        return actor
    
    def test_factory_creates_on_attacked_from_string(self, mock_actor):
        """Factory should create TriggerOnAttacked from string type."""
        trigger = Trigger.new_trigger("on_attacked", mock_actor, disabled=False)
        
        assert isinstance(trigger, TriggerOnAttacked)
        assert trigger.trigger_type_ == TriggerType.ON_ATTACKED
    
    def test_factory_creates_on_attacked_from_enum(self, mock_actor):
        """Factory should create TriggerOnAttacked from enum type."""
        trigger = Trigger.new_trigger(TriggerType.ON_ATTACKED, mock_actor, disabled=False)
        
        assert isinstance(trigger, TriggerOnAttacked)
        assert trigger.trigger_type_ == TriggerType.ON_ATTACKED
    
    def test_factory_case_insensitive(self, mock_actor):
        """Factory should handle case-insensitive string input."""
        trigger1 = Trigger.new_trigger("ON_ATTACKED", mock_actor)
        trigger2 = Trigger.new_trigger("On_Attacked", mock_actor)
        trigger3 = Trigger.new_trigger("on_attacked", mock_actor)
        
        assert isinstance(trigger1, TriggerOnAttacked)
        assert isinstance(trigger2, TriggerOnAttacked)
        assert isinstance(trigger3, TriggerOnAttacked)


class TestTriggerCriteria:
    """Tests for ON_ATTACKED trigger criteria evaluation."""
    
    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor that owns the trigger."""
        actor = create_mock_character(name="Guard")
        actor.actor_type = ActorType.CHARACTER
        actor.reference_number = "C1"
        actor.get_vars = MagicMock(return_value={})
        return actor
    
    @pytest.fixture
    def mock_attacker(self):
        """Create a mock attacker."""
        attacker = create_mock_character(name="Player", is_pc=True)
        attacker.actor_type = ActorType.CHARACTER
        attacker.reference_number = "C2"
        attacker.pronoun_subject = "they"
        attacker.pronoun_object = "them"
        attacker.pronoun_possessive = "their"
        attacker.get_vars = MagicMock(return_value={})
        return attacker
    
    @pytest.mark.asyncio
    async def test_criteria_blocks_execution(self, mock_actor, mock_attacker):
        """Trigger should not execute when criteria not met."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.script_ = "say Attacked!"
        
        # Add a criteria that always fails
        mock_criteria = MagicMock()
        mock_criteria.evaluate = MagicMock(return_value=False)
        trigger.criteria_ = [mock_criteria]
        
        trigger.execute_trigger_script = AsyncMock()
        
        mock_game_state = MagicMock()
        result = await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert result == False
        trigger.execute_trigger_script.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_criteria_allows_execution(self, mock_actor, mock_attacker):
        """Trigger should execute when all criteria met."""
        trigger = TriggerOnAttacked("test_trigger", mock_actor, disabled=False)
        trigger.script_ = "say Attacked!"
        
        # Add criteria that always passes
        mock_criteria = MagicMock()
        mock_criteria.evaluate = MagicMock(return_value=True)
        trigger.criteria_ = [mock_criteria]
        
        trigger.execute_trigger_script = AsyncMock()
        
        mock_game_state = MagicMock()
        result = await trigger.run(mock_attacker, "", {}, mock_game_state)
        
        assert result == True
        trigger.execute_trigger_script.assert_called_once()


class TestDoSingleAttackIntegration:
    """Tests for ON_ATTACKED trigger integration with do_single_attack."""
    
    @pytest.fixture
    def mock_game_state(self):
        """Create a mock game state."""
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        
        game_state = MagicMock()
        game_state.world_clock_tick = 100
        return game_state
    
    @pytest.fixture
    def attacker(self, mock_game_state):
        """Create an attacker character."""
        attacker = create_mock_character(name="Player", is_pc=True)
        attacker.actor_type = ActorType.CHARACTER
        attacker.hit_modifier = 50
        attacker.critical_chance = 0  # No crits for predictable tests
        attacker.critical_damage_bonus = 0
        
        # Set up room
        room = MagicMock()
        room.echo = AsyncMock()
        attacker.location_room = room
        attacker._location_room = room
        
        return attacker
    
    @pytest.fixture
    def defender(self, mock_game_state):
        """Create a defender with ON_ATTACKED trigger."""
        defender = create_mock_character(name="Guard")
        defender.actor_type = ActorType.CHARACTER
        defender.dodge_dice_number = 1
        defender.dodge_dice_size = 20
        defender.dodge_modifier = 0
        defender.current_hit_points = 100
        defender.max_hit_points = 100
        defender.is_unkillable = False
        defender.is_dead = MagicMock(return_value=False)
        defender.reference_number = "C1"
        defender.pronoun_subject = "he"
        defender.pronoun_object = "him"
        defender.pronoun_possessive = "his"
        defender.get_vars = MagicMock(return_value={})
        
        # Set up room
        room = MagicMock()
        room.echo = AsyncMock()
        defender.location_room = room
        defender._location_room = room
        
        # Set up damage multipliers
        defender.damage_multipliers = MagicMock()
        defender.damage_multipliers.get = MagicMock(return_value=0)
        defender.damage_reduction = MagicMock()
        defender.damage_reduction.get = MagicMock(return_value=0)
        
        # No triggers initially
        defender.triggers_by_type = {}
        
        return defender
    
    @pytest.fixture
    def attack_data(self):
        """Create attack data for testing."""
        return AttackData(
            damage_type=DamageType.SLASHING,
            damage_amount="1d8+2",
            attack_noun="sword",
            attack_verb="slashes"
        )
    
    @pytest.mark.asyncio
    async def test_on_attacked_fires_on_attack_attempt(self, attacker, defender, attack_data, mock_game_state):
        """ON_ATTACKED trigger should fire when attack is attempted."""
        from NextGenMUDApp.core_actions import CoreActions
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        
        # Set up game state
        GameStateInterface.set_instance(mock_game_state)
        
        # Create and register a trigger
        trigger = TriggerOnAttacked("guard_response", defender, disabled=False)
        trigger.script_ = "say You dare attack me?!"
        trigger.criteria_ = []
        trigger.execute_trigger_script = AsyncMock()
        
        defender.triggers_by_type = {
            TriggerType.ON_ATTACKED: [trigger]
        }
        
        core_actions = CoreActions()
        core_actions.game_state = mock_game_state
        
        # Perform attack
        await core_actions.do_single_attack(attacker, defender, attack_data)
        
        # Trigger should have fired
        trigger.execute_trigger_script.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_attacked_fires_even_on_miss(self, attacker, defender, attack_data, mock_game_state):
        """ON_ATTACKED should fire even when attack misses."""
        from NextGenMUDApp.core_actions import CoreActions
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        
        GameStateInterface.set_instance(mock_game_state)
        
        # Set up defender to always dodge (extremely high dodge)
        defender.dodge_dice_number = 100
        defender.dodge_dice_size = 100
        defender.dodge_modifier = 1000
        
        # Set up attacker to always miss
        attacker.hit_modifier = -1000
        
        trigger = TriggerOnAttacked("guard_response", defender, disabled=False)
        trigger.script_ = "say Nice try!"
        trigger.criteria_ = []
        trigger.execute_trigger_script = AsyncMock()
        
        defender.triggers_by_type = {
            TriggerType.ON_ATTACKED: [trigger]
        }
        
        core_actions = CoreActions()
        core_actions.game_state = mock_game_state
        
        # Perform attack (will miss due to high dodge)
        result = await core_actions.do_single_attack(attacker, defender, attack_data)
        
        # Attack missed
        assert result == -1
        
        # But trigger still fired!
        trigger.execute_trigger_script.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_attack_vars_passed_to_trigger(self, attacker, defender, attack_data, mock_game_state):
        """Attack noun and verb should be passed to the trigger."""
        from NextGenMUDApp.core_actions import CoreActions
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        
        GameStateInterface.set_instance(mock_game_state)
        
        captured_vars = {}
        
        async def capture_vars(actor, vars, game_state):
            captured_vars.update(vars)
        
        trigger = TriggerOnAttacked("guard_response", defender, disabled=False)
        trigger.criteria_ = []
        trigger.execute_trigger_script = capture_vars
        
        defender.triggers_by_type = {
            TriggerType.ON_ATTACKED: [trigger]
        }
        
        core_actions = CoreActions()
        core_actions.game_state = mock_game_state
        
        await core_actions.do_single_attack(attacker, defender, attack_data)
        
        # Check that attack info was passed
        assert captured_vars.get('attack_noun') == 'sword'
        assert captured_vars.get('attack_verb') == 'slashes'
    
    @pytest.mark.asyncio
    async def test_multiple_triggers_all_fire(self, attacker, defender, attack_data, mock_game_state):
        """All ON_ATTACKED triggers on defender should fire."""
        from NextGenMUDApp.core_actions import CoreActions
        from NextGenMUDApp.comprehensive_game_state_interface import GameStateInterface
        
        GameStateInterface.set_instance(mock_game_state)
        
        trigger1 = TriggerOnAttacked("response1", defender, disabled=False)
        trigger1.criteria_ = []
        trigger1.execute_trigger_script = AsyncMock()
        
        trigger2 = TriggerOnAttacked("response2", defender, disabled=False)
        trigger2.criteria_ = []
        trigger2.execute_trigger_script = AsyncMock()
        
        defender.triggers_by_type = {
            TriggerType.ON_ATTACKED: [trigger1, trigger2]
        }
        
        core_actions = CoreActions()
        core_actions.game_state = mock_game_state
        
        await core_actions.do_single_attack(attacker, defender, attack_data)
        
        # Both triggers should have fired
        trigger1.execute_trigger_script.assert_called_once()
        trigger2.execute_trigger_script.assert_called_once()


class TestTriggerFromYAML:
    """Tests for loading ON_ATTACKED triggers from YAML data."""
    
    @pytest.fixture
    def mock_actor(self):
        """Create a mock actor for trigger loading."""
        actor = create_mock_character(name="TestNPC")
        actor.rid = "C1{test}"
        return actor
    
    def test_from_dict_loads_on_attacked(self, mock_actor):
        """Trigger should load from YAML-like dict data."""
        yaml_data = {
            'id': 'guard_reaction',
            'type': 'on_attacked',
            'script': 'say You will pay for that!'
        }
        
        trigger = Trigger.new_trigger(yaml_data['type'], mock_actor, disabled=False)
        trigger = trigger.from_dict(yaml_data)
        
        assert trigger.id == 'guard_reaction'
        assert trigger.trigger_type_ == TriggerType.ON_ATTACKED
        assert 'pay for that' in trigger.script_
    
    def test_from_dict_with_criteria(self, mock_actor):
        """Trigger should load criteria from YAML-like dict data."""
        yaml_data = {
            'id': 'guard_reaction',
            'type': 'on_attacked',
            'criteria': [
                {
                    'subject': '$random(1,100)',
                    'operator': 'numlte',
                    'predicate': '50'
                }
            ],
            'script': 'say Ouch!'
        }
        
        trigger = Trigger.new_trigger(yaml_data['type'], mock_actor, disabled=False)
        trigger = trigger.from_dict(yaml_data)
        
        assert len(trigger.criteria_) == 1
        assert trigger.criteria_[0].operator == 'numlte'
