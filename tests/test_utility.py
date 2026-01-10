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
    set_vars, firstcap, article_plus_name, matches_text_pattern,
    parse_text_pattern_tokens, evaluate_if_condition
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


class TestTextPatternMatching:
    """Tests for the text pattern matching grammar with () grouping and | alternation."""
    
    # Basic backward compatibility tests
    def test_simple_substring_match(self):
        """Simple patterns without grammar should work like before."""
        assert matches_text_pattern("hello world", "hello") is True
        assert matches_text_pattern("hello world", "world") is True
        assert matches_text_pattern("hello world", "goodbye") is False
    
    def test_simple_case_insensitive(self):
        """Matching should be case-insensitive."""
        assert matches_text_pattern("Hello World", "hello") is True
        assert matches_text_pattern("hello world", "HELLO") is True
        assert matches_text_pattern("HELLO WORLD", "world") is True
    
    def test_empty_pattern_returns_false(self):
        """Empty pattern should return False."""
        assert matches_text_pattern("hello world", "") is False
        assert matches_text_pattern("hello world", "   ") is False
    
    # Single group with alternatives tests
    def test_single_group_matches_first_alternative(self):
        """Single group should match if first alternative is found."""
        assert matches_text_pattern("I want to travel to the oasis", "(travel|guide)") is True
    
    def test_single_group_matches_second_alternative(self):
        """Single group should match if second alternative is found."""
        assert matches_text_pattern("can you guide me to water", "(travel|guide)") is True
    
    def test_single_group_no_match(self):
        """Single group should not match if no alternatives found."""
        assert matches_text_pattern("I want to walk to the oasis", "(travel|guide)") is False
    
    def test_single_group_multiple_alternatives(self):
        """Single group with multiple alternatives."""
        assert matches_text_pattern("where is the oasis", "(travel|guide|oasis|water)") is True
        assert matches_text_pattern("I need fresh water", "(travel|guide|oasis|water)") is True
        assert matches_text_pattern("hello there", "(travel|guide|oasis|water)") is False
    
    # Pipe without parentheses tests
    def test_pipe_without_parens(self):
        """Pipe without parentheses should still work as alternatives."""
        assert matches_text_pattern("I want to travel", "travel|guide") is True
        assert matches_text_pattern("can you guide me", "travel|guide") is True
        assert matches_text_pattern("I want to walk", "travel|guide") is False
    
    # Multiple groups (AND logic) tests
    def test_multiple_groups_both_match(self):
        """Multiple groups should require all to match (AND)."""
        pattern = "(travel|guide) (oasis|fresh water)"
        assert matches_text_pattern("can you guide me to the oasis", pattern) is True
        assert matches_text_pattern("I want to travel to find fresh water", pattern) is True
    
    def test_multiple_groups_first_only_matches(self):
        """Should fail if only first group matches."""
        pattern = "(travel|guide) (oasis|fresh water)"
        assert matches_text_pattern("I want to travel to the city", pattern) is False
    
    def test_multiple_groups_second_only_matches(self):
        """Should fail if only second group matches."""
        pattern = "(travel|guide) (oasis|fresh water)"
        assert matches_text_pattern("where is the oasis", pattern) is False
    
    def test_multiple_groups_neither_matches(self):
        """Should fail if neither group matches."""
        pattern = "(travel|guide) (oasis|fresh water)"
        assert matches_text_pattern("hello world", pattern) is False
    
    # Mixed word and group tests
    def test_word_and_group(self):
        """Mix of plain word and group should work."""
        pattern = "cave (dark|dim)"
        assert matches_text_pattern("the cave is dark", pattern) is True
        assert matches_text_pattern("a dim cave ahead", pattern) is True
        assert matches_text_pattern("the cave is bright", pattern) is False
        assert matches_text_pattern("it is dark outside", pattern) is False
    
    def test_group_and_word(self):
        """Group followed by plain word should work."""
        pattern = "(ancient|old) temple"
        assert matches_text_pattern("the ancient temple stands tall", pattern) is True
        assert matches_text_pattern("an old temple in ruins", pattern) is True
        assert matches_text_pattern("a new temple was built", pattern) is False
    
    # Multi-word alternatives tests
    def test_multi_word_alternatives(self):
        """Alternatives can contain multiple words."""
        pattern = "(fresh water|clean water|drinking water)"
        assert matches_text_pattern("I need fresh water", pattern) is True
        assert matches_text_pattern("is there clean water here", pattern) is True
        assert matches_text_pattern("looking for drinking water", pattern) is True
        assert matches_text_pattern("I need water", pattern) is False
    
    # Complex patterns tests
    def test_complex_pattern(self):
        """Complex pattern with multiple groups and words."""
        pattern = "(tell|show|guide) (way|path|route) (village|town|city)"
        assert matches_text_pattern("can you tell me the way to the village", pattern) is True
        assert matches_text_pattern("show me the path to town", pattern) is True
        assert matches_text_pattern("guide me on the route to the city", pattern) is True
        assert matches_text_pattern("tell me about the village", pattern) is False  # missing way/path/route
    
    # Edge cases
    def test_whitespace_in_pattern(self):
        """Extra whitespace in pattern should be handled."""
        pattern = "(travel|guide)   (oasis|water)"
        assert matches_text_pattern("travel to the oasis", pattern) is True
    
    def test_whitespace_in_alternatives(self):
        """Whitespace around alternatives should be trimmed."""
        pattern = "( travel | guide )"
        assert matches_text_pattern("I want to travel", pattern) is True
    
    def test_nested_parens_not_supported(self):
        """Nested parentheses - outer group should be parsed."""
        # This tests current behavior - nested parens aren't specially handled
        pattern = "((a|b)|c)"
        # The inner content is "(a|b)|c" which splits to ["(a", "b)", "c"]
        # This is an edge case - users should avoid nested parens
        # Just verify it doesn't crash
        result = matches_text_pattern("test a here", pattern)
        assert isinstance(result, bool)
    
    # Integration with evaluate_if_condition tests
    def test_contains_operator_simple(self):
        """contains operator should work with simple patterns."""
        assert evaluate_if_condition("hello world", "contains", "hello") is True
        assert evaluate_if_condition("hello world", "contains", "goodbye") is False
    
    def test_contains_operator_with_groups(self):
        """contains operator should work with group patterns."""
        assert evaluate_if_condition("I want to travel", "contains", "(travel|guide)") is True
        assert evaluate_if_condition("can you guide me", "contains", "(travel|guide)") is True
        assert evaluate_if_condition("I want to walk", "contains", "(travel|guide)") is False
    
    def test_contains_operator_multiple_groups(self):
        """contains operator should work with multiple groups."""
        pattern = "(travel|guide) (oasis|water)"
        assert evaluate_if_condition("guide me to the oasis", "contains", pattern) is True
        assert evaluate_if_condition("travel to find water", "contains", pattern) is True
        assert evaluate_if_condition("travel to the city", "contains", pattern) is False


class TestParseTextPatternTokens:
    """Tests for the token parsing function."""
    
    def test_parse_simple_word(self):
        """Should parse a simple word."""
        tokens = parse_text_pattern_tokens("hello")
        assert tokens == [('word', 'hello')]
    
    def test_parse_multiple_words(self):
        """Should parse multiple words."""
        tokens = parse_text_pattern_tokens("hello world")
        assert tokens == [('word', 'hello'), ('word', 'world')]
    
    def test_parse_single_group(self):
        """Should parse a single group."""
        tokens = parse_text_pattern_tokens("(a|b|c)")
        assert tokens == [('group', ['a', 'b', 'c'])]
    
    def test_parse_group_with_spaces(self):
        """Should parse a group with spaces in alternatives."""
        tokens = parse_text_pattern_tokens("(fresh water|clean water)")
        assert tokens == [('group', ['fresh water', 'clean water'])]
    
    def test_parse_mixed(self):
        """Should parse mixed words and groups."""
        tokens = parse_text_pattern_tokens("find (oasis|water)")
        assert tokens == [('word', 'find'), ('group', ['oasis', 'water'])]
    
    def test_parse_pipe_without_parens(self):
        """Should parse pipe without parentheses as a group."""
        tokens = parse_text_pattern_tokens("a|b|c")
        assert tokens == [('group', ['a', 'b', 'c'])]
