"""
Unit tests for utility functions.

Tests cover:
- Dice rolling
- Variable substitution
- Text formatting
- Time conversions
"""

import pytest
from unittest.mock import patch
import random

from NextGenMUDApp.utility import (
    roll_dice, get_dice_parts, ticks_from_seconds, seconds_from_ticks,
    set_vars, firstcap, article_plus_name
)


class TestDiceRolling:
    """Tests for dice rolling functions."""
    
    def test_roll_dice_returns_int(self):
        """roll_dice should return an integer."""
        result = roll_dice(1, 6, 0)
        assert isinstance(result, int)
    
    def test_roll_dice_within_range(self):
        """roll_dice should return values within expected range."""
        # 1d6+0 should be 1-6
        for _ in range(100):
            result = roll_dice(1, 6, 0)
            assert 1 <= result <= 6
    
    def test_roll_dice_with_modifier(self):
        """roll_dice should add modifier correctly."""
        # 1d6+5 should be 6-11
        for _ in range(100):
            result = roll_dice(1, 6, 5)
            assert 6 <= result <= 11
    
    def test_roll_dice_multiple_dice(self):
        """roll_dice should handle multiple dice."""
        # 3d6+0 should be 3-18
        for _ in range(100):
            result = roll_dice(3, 6, 0)
            assert 3 <= result <= 18
    
    def test_roll_dice_zero_dice(self):
        """roll_dice with 0 dice should return modifier only."""
        result = roll_dice(0, 6, 10)
        assert result == 10
    
    @patch('random.randint')
    def test_roll_dice_uses_randint(self, mock_randint):
        """roll_dice should use random.randint for each die."""
        mock_randint.return_value = 4
        
        result = roll_dice(2, 6, 0)
        
        assert result == 8  # 4 + 4
        assert mock_randint.call_count == 2


class TestDiceParsing:
    """Tests for dice string parsing."""
    
    def test_parse_simple_dice(self):
        """Should parse simple dice notation."""
        num, size, mod = get_dice_parts("1d6")
        assert num == 1
        assert size == 6
        assert mod == 0
    
    def test_parse_dice_with_positive_modifier(self):
        """Should parse dice with positive modifier."""
        num, size, mod = get_dice_parts("2d8+5")
        assert num == 2
        assert size == 8
        assert mod == 5
    
    def test_parse_dice_with_negative_modifier(self):
        """Should parse dice with negative modifier."""
        num, size, mod = get_dice_parts("1d10-2")
        assert num == 1
        assert size == 10
        assert mod == -2
    
    def test_parse_multiple_dice(self):
        """Should parse multiple dice correctly."""
        num, size, mod = get_dice_parts("3d6+10")
        assert num == 3
        assert size == 6
        assert mod == 10


class TestTimeConversions:
    """Tests for tick/second conversion functions."""
    
    def test_ticks_from_seconds_basic(self):
        """Should convert seconds to ticks."""
        # Assuming 2 ticks per second (0.5s per tick)
        ticks = ticks_from_seconds(1)
        assert ticks == 2
    
    def test_ticks_from_seconds_multiple(self):
        """Should handle multiple seconds."""
        ticks = ticks_from_seconds(5)
        assert ticks == 10
    
    def test_ticks_from_seconds_fractional(self):
        """Should handle fractional seconds."""
        ticks = ticks_from_seconds(0.5)
        assert ticks == 1
    
    def test_seconds_from_ticks_basic(self):
        """Should convert ticks to seconds."""
        seconds = seconds_from_ticks(2)
        assert seconds == 1.0
    
    def test_seconds_from_ticks_multiple(self):
        """Should handle multiple ticks."""
        seconds = seconds_from_ticks(10)
        assert seconds == 5.0


class TestTextFormatting:
    """Tests for text formatting functions."""
    
    def test_firstcap_capitalizes_first_letter(self):
        """firstcap should capitalize the first letter."""
        result = firstcap("hello world")
        assert result == "Hello world"
    
    def test_firstcap_preserves_rest(self):
        """firstcap should preserve the rest of the string."""
        result = firstcap("hELLO WORLD")
        assert result == "HELLO WORLD"
    
    def test_firstcap_empty_string(self):
        """firstcap should handle empty string."""
        result = firstcap("")
        assert result == ""
    
    def test_article_plus_name_with_article(self):
        """article_plus_name should combine article and name."""
        result = article_plus_name("a", "sword")
        assert result == "a sword"
    
    def test_article_plus_name_without_article(self):
        """article_plus_name should work with empty article."""
        result = article_plus_name("", "Gandalf")
        assert result == "Gandalf"


class TestVariableSubstitution:
    """Tests for the set_vars function."""
    
    def test_set_vars_returns_dict(self):
        """set_vars should return a dictionary."""
        from tests.conftest import create_mock_character
        
        actor = create_mock_character(name="Actor")
        subject = create_mock_character(name="Subject")
        target = create_mock_character(name="Target")
        
        result = set_vars(actor, subject, target, "test message")
        
        assert isinstance(result, dict)
    
    def test_set_vars_contains_actor_info(self):
        """set_vars should include actor information."""
        from tests.conftest import create_mock_character
        
        actor = create_mock_character(name="TestActor")
        subject = create_mock_character(name="Subject")
        target = create_mock_character(name="Target")
        
        result = set_vars(actor, subject, target, "test message")
        
        # Check that actor-related vars exist
        assert 'a' in result or 'actor' in result or 'A' in result
