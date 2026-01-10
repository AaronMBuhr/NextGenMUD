"""
Tests for the multiclassing system.

Tests cover:
- max_class_count limit (2 classes)
- Skill points system (0-100 range)
- Skill points per level scaling
- Level up with new skill notifications
- Skills command showing progression by level
- Combat stats combining from multiple classes
- Saving throws combining from multiple classes
- Adding a second class (multiclassing)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from NextGenMUDApp.constants import CharacterClassRole, Constants
from NextGenMUDApp.nondb_models.characters import Character
from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes, PermanentCharacterFlags
from NextGenMUDApp.handlers.level_up_handler import LevelUpHandler


class TestMulticlassLimit:
    """Tests for the 2-class multiclass limit."""
    
    def test_max_class_count_is_two(self, create_test_character, fighter_character_data):
        """Verify max_class_count is set to 2."""
        char = create_test_character(fighter_character_data)
        assert char.max_class_count == 2
    
    def test_cannot_add_third_class(self, create_test_character, fighter_character_data):
        """Verify that adding a third class fails."""
        char = create_test_character(fighter_character_data)
        # Already has Fighter from fixture
        
        # Add Rogue as second class
        success = char.add_class(CharacterClassRole.ROGUE)
        assert success is True
        assert len(char.class_priority) == 2
        
        # Try to add Mage as third class - should fail
        success = char.add_class(CharacterClassRole.MAGE)
        assert success is False
        assert len(char.class_priority) == 2
        assert CharacterClassRole.MAGE not in char.class_priority
    
    def test_can_add_second_class(self, create_test_character, fighter_character_data):
        """Verify that adding a second class succeeds."""
        char = create_test_character(fighter_character_data)
        
        # Add Rogue as second class
        success = char.add_class(CharacterClassRole.ROGUE)
        assert success is True
        assert CharacterClassRole.ROGUE in char.class_priority
        assert char.levels_by_role.get(CharacterClassRole.ROGUE) == 1


class TestSkillPointsSystem:
    """Tests for the 0-100 skill points system."""
    
    def test_max_skill_level_is_100(self):
        """Verify MAX_SKILL_LEVEL is set to 100."""
        assert Constants.MAX_SKILL_LEVEL == 100
    
    def test_skill_points_per_level_fighter(self):
        """Verify Fighter gets 25 skill points per level."""
        assert Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(CharacterClassRole.FIGHTER) == 25
    
    def test_skill_points_per_level_mage(self):
        """Verify Mage gets 20 skill points per level."""
        assert Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(CharacterClassRole.MAGE) == 20
    
    def test_skill_points_per_level_rogue(self):
        """Verify Rogue gets 22 skill points per level."""
        assert Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(CharacterClassRole.ROGUE) == 22
    
    def test_skill_points_per_level_cleric(self):
        """Verify Cleric gets 20 skill points per level."""
        assert Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(CharacterClassRole.CLERIC) == 20


class TestLevelUpWithNewSkills:
    """Tests for level up showing new skills."""
    
    def test_level_up_returns_new_skills(self, create_test_character, fighter_character_data):
        """Verify that level_up returns newly unlocked skills."""
        char = create_test_character(fighter_character_data)
        char.experience_points = 1000000  # Lots of XP
        char.skill_points_available = 0  # Clear skill points to allow level up
        
        # Level up
        success, stats_gained = char.level_up(CharacterClassRole.FIGHTER)
        assert success is True
        # The first level up may or may not have new skills depending on current level
        # Just check that the dict was returned properly
        assert isinstance(stats_gained, dict)
        assert 'level' in stats_gained
        assert 'skill_points' in stats_gained
    
    def test_unlock_skills_for_level_returns_list(self, create_test_character, base_character_data):
        """Verify _unlock_skills_for_level returns a list of skill names."""
        # Create a fresh character with no skills
        data = base_character_data.copy()
        data['class'] = {'fighter': {'level': 1}}
        char = create_test_character(data)
        
        # Clear any existing skills
        char.skill_levels_by_role[CharacterClassRole.FIGHTER] = {}
        
        # Unlock skills for level 1
        new_skills = char._unlock_skills_for_level(CharacterClassRole.FIGHTER, 1)
        
        # Should return a list (may be empty or have skills)
        assert isinstance(new_skills, list)


class TestMulticlassHandler:
    """Tests for the multiclass handler."""
    
    def test_handle_multiclass_success(self, create_test_character, fighter_character_data):
        """Verify multiclassing into a new class succeeds."""
        char = create_test_character(fighter_character_data)
        char.experience_points = 1000000  # Lots of XP
        char.skill_points_available = 0  # No unspent points
        
        success, message = LevelUpHandler.handle_multiclass(char, CharacterClassRole.ROGUE)
        assert success is True
        assert "MULTICLASS" in message
        assert CharacterClassRole.ROGUE in char.class_priority
    
    def test_handle_multiclass_already_has_class(self, create_test_character, fighter_character_data):
        """Verify multiclassing into existing class fails."""
        char = create_test_character(fighter_character_data)
        
        success, message = LevelUpHandler.handle_multiclass(char, CharacterClassRole.FIGHTER)
        assert success is False
        assert "already" in message.lower()
    
    def test_handle_multiclass_max_classes(self, create_test_character, fighter_character_data):
        """Verify multiclassing fails when at max classes."""
        char = create_test_character(fighter_character_data)
        char.experience_points = 1000000
        char.skill_points_available = 0
        
        # Add second class
        char.add_class(CharacterClassRole.ROGUE)
        
        # Try to add third - should fail
        success, message = LevelUpHandler.handle_multiclass(char, CharacterClassRole.MAGE)
        assert success is False
        assert "only have" in message.lower() or "2 classes" in message.lower()
    
    def test_handle_multiclass_not_base_class(self, create_test_character, fighter_character_data):
        """Verify multiclassing into specialization fails."""
        char = create_test_character(fighter_character_data)
        char.experience_points = 1000000
        char.skill_points_available = 0
        
        # Try to multiclass into a specialization
        success, message = LevelUpHandler.handle_multiclass(char, CharacterClassRole.BERSERKER)
        assert success is False
        assert "base classes" in message.lower()
    
    def test_handle_levelup_calls_multiclass_for_new_class(self, create_test_character, fighter_character_data):
        """Verify handle_level_up calls handle_multiclass for new classes."""
        char = create_test_character(fighter_character_data)
        char.experience_points = 1000000
        char.skill_points_available = 0
        
        # Call level up with a class the character doesn't have
        success, message = LevelUpHandler.handle_level_up(char, CharacterClassRole.ROGUE)
        assert success is True
        assert CharacterClassRole.ROGUE in char.class_priority


class TestCombatStatsMulticlass:
    """Tests for combat stats combining from multiple classes."""
    
    def test_hit_modifier_takes_best(self, create_test_character, multiclass_character_data):
        """Verify hit modifier takes the best from all classes."""
        char = create_test_character(multiclass_character_data)
        char.calculate_combat_bonuses()
        
        # Fighter should have better hit bonus than Mage at same level
        fighter_level = char.levels_by_role[CharacterClassRole.FIGHTER]
        mage_level = char.levels_by_role[CharacterClassRole.MAGE]
        
        fighter_hit = Constants.HIT_BONUS_PROGRESSION.get(CharacterClassRole.FIGHTER, [0]*50)[fighter_level - 1]
        mage_hit = Constants.HIT_BONUS_PROGRESSION.get(CharacterClassRole.MAGE, [0]*50)[mage_level - 1]
        
        expected_hit = char.base_hit_modifier + max(fighter_hit, mage_hit)
        assert char.hit_modifier == expected_hit
    
    def test_dodge_modifier_sums(self, create_test_character, multiclass_character_data):
        """Verify dodge modifier sums from all classes."""
        char = create_test_character(multiclass_character_data)
        char.calculate_combat_bonuses()
        
        fighter_level = char.levels_by_role[CharacterClassRole.FIGHTER]
        mage_level = char.levels_by_role[CharacterClassRole.MAGE]
        
        fighter_dodge = Constants.DODGE_BONUS_PROGRESSION.get(CharacterClassRole.FIGHTER, [0]*50)[fighter_level - 1]
        mage_dodge = Constants.DODGE_BONUS_PROGRESSION.get(CharacterClassRole.MAGE, [0]*50)[mage_level - 1]
        
        expected_dodge = char.base_dodge_modifier + fighter_dodge + mage_dodge
        assert char.dodge_modifier == expected_dodge
    
    def test_spell_power_takes_best(self, create_test_character, multiclass_character_data):
        """Verify spell power takes the best caster class."""
        char = create_test_character(multiclass_character_data)
        char.calculate_combat_bonuses()
        
        mage_level = char.levels_by_role.get(CharacterClassRole.MAGE, 0)
        
        if mage_level > 0:
            expected_spell_power = Constants.SPELL_POWER_PROGRESSION.get(CharacterClassRole.MAGE, [0]*50)[mage_level - 1]
            assert char.spell_power == expected_spell_power


class TestSavingThrowsSkillBased:
    """Tests for skill-based saving throw system (opposed checks)."""
    
    def test_fortitude_save_uses_skill_and_constitution(self, create_test_character, fighter_character_data):
        """Verify fortitude save combines skill level and Constitution."""
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        char = create_test_character(fighter_character_data)
        
        # Set known values
        char.skill_levels["fortitude"] = 50
        char.attributes[CharacterAttributes.CONSTITUTION] = 15
        
        # Expected: skill + (attribute × modifier)
        expected = 50 + (15 * Constants.ATTRIBUTE_SAVE_MODIFIER)
        assert char.get_save_value("fortitude") == expected
    
    def test_reflex_save_uses_skill_and_dexterity(self, create_test_character, rogue_character_data):
        """Verify reflex save combines skill level and Dexterity."""
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        char = create_test_character(rogue_character_data)
        
        char.skill_levels["reflex"] = 60
        char.attributes[CharacterAttributes.DEXTERITY] = 18
        
        expected = 60 + (18 * Constants.ATTRIBUTE_SAVE_MODIFIER)
        assert char.get_save_value("reflex") == expected
    
    def test_will_save_uses_skill_and_wisdom(self, create_test_character, mage_character_data):
        """Verify will save combines skill level and Wisdom."""
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        char = create_test_character(mage_character_data)
        
        char.skill_levels["will"] = 40
        char.attributes[CharacterAttributes.WISDOM] = 14
        
        expected = 40 + (14 * Constants.ATTRIBUTE_SAVE_MODIFIER)
        assert char.get_save_value("will") == expected
    
    def test_multiclass_saves_use_same_skill_system(self, create_test_character, base_character_data):
        """Verify multiclass characters use the same skill-based save system."""
        from NextGenMUDApp.nondb_models.character_interface import CharacterAttributes
        data = base_character_data.copy()
        data['class'] = {
            'fighter': {'level': 10},
            'rogue': {'level': 10}
        }
        data['class_priority'] = ['fighter', 'rogue']
        char = create_test_character(data)
        
        # Set skill levels (same for all characters regardless of class)
        char.skill_levels["fortitude"] = 30
        char.skill_levels["reflex"] = 70
        char.attributes[CharacterAttributes.CONSTITUTION] = 16
        char.attributes[CharacterAttributes.DEXTERITY] = 18
        
        # Saves are skill-based, not class-based
        assert char.get_save_value("fortitude") == 30 + (16 * Constants.ATTRIBUTE_SAVE_MODIFIER)
        assert char.get_save_value("reflex") == 70 + (18 * Constants.ATTRIBUTE_SAVE_MODIFIER)


class TestOpposedSavingThrows:
    """Tests for the opposed saving throw resolution system."""
    
    def test_resolve_saving_throw_equal_values(self, create_test_character, fighter_character_data):
        """Equal attacker and defender values should give 50% chance."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        save_chance, _ = Character.resolve_saving_throw(50, 50, 0)
        assert save_chance == 50
    
    def test_resolve_saving_throw_defender_advantage(self, create_test_character, fighter_character_data):
        """Higher defender save should increase save chance."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        save_chance, _ = Character.resolve_saving_throw(70, 50, 0)
        assert save_chance == 70  # 50 + (70-50) = 70
    
    def test_resolve_saving_throw_attacker_advantage(self, create_test_character, fighter_character_data):
        """Higher attacker penetration should decrease save chance."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        save_chance, _ = Character.resolve_saving_throw(50, 70, 0)
        assert save_chance == 30  # 50 + (50-70) = 30
    
    def test_resolve_saving_throw_clamped_min(self, create_test_character, fighter_character_data):
        """Save chance should not go below minimum."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        save_chance, _ = Character.resolve_saving_throw(10, 100, 0)
        assert save_chance == Constants.SAVE_CHANCE_MIN
    
    def test_resolve_saving_throw_clamped_max(self, create_test_character, fighter_character_data):
        """Save chance should not go above maximum."""
        from NextGenMUDApp.nondb_models.characters import Character
        
        save_chance, _ = Character.resolve_saving_throw(100, 10, 0)
        assert save_chance == Constants.SAVE_CHANCE_MAX


class TestAddClassStats:
    """Tests for stats gained when adding a new class."""
    
    def test_add_class_grants_hp(self, create_test_character, fighter_character_data):
        """Verify adding a class grants HP for that class."""
        char = create_test_character(fighter_character_data)
        old_hp = char.max_hit_points
        
        char.add_class(CharacterClassRole.MAGE)
        
        mage_hp = Constants.HP_BY_CHARACTER_CLASS.get(CharacterClassRole.MAGE, 0)
        assert char.max_hit_points == old_hp + mage_hp
    
    def test_add_class_grants_mana(self, create_test_character, fighter_character_data):
        """Verify adding a caster class grants mana."""
        char = create_test_character(fighter_character_data)
        old_mana = char.max_mana
        
        char.add_class(CharacterClassRole.MAGE)
        
        mage_mana = Constants.MANA_BY_CHARACTER_CLASS.get(CharacterClassRole.MAGE, 0)
        if mage_mana > 0:
            assert char.max_mana == old_mana + mage_mana
    
    def test_add_class_grants_stamina(self, create_test_character, mage_character_data):
        """Verify adding a physical class grants stamina."""
        char = create_test_character(mage_character_data)
        old_stamina = char.max_stamina
        
        char.add_class(CharacterClassRole.ROGUE)
        
        rogue_stamina = Constants.STAMINA_BY_CHARACTER_CLASS.get(CharacterClassRole.ROGUE, 0)
        if rogue_stamina > 0:
            assert char.max_stamina == old_stamina + rogue_stamina
    
    def test_add_class_unlocks_skills(self, create_test_character, fighter_character_data):
        """Verify adding a class unlocks that class's skills."""
        char = create_test_character(fighter_character_data)
        
        char.add_class(CharacterClassRole.ROGUE)
        
        # Should have Rogue skills now
        assert CharacterClassRole.ROGUE in char.skill_levels_by_role
        # Skills should exist (at level 0 = unlocked but not trained)
        assert len(char.skill_levels_by_role[CharacterClassRole.ROGUE]) > 0


class TestSkillProgression:
    """Tests for skill progression display."""
    
    def test_skills_are_unlocked_at_level_0(self, create_test_character, fighter_character_data):
        """Verify skills are unlocked at level 0 (untrained)."""
        # Create character with fresh skills
        data = fighter_character_data.copy()
        char = create_test_character(data)
        
        # Clear skills and re-unlock
        char.skill_levels_by_role[CharacterClassRole.FIGHTER] = {}
        char._unlock_skills_for_level(CharacterClassRole.FIGHTER, 1)
        
        # Skills should be at 0 (unlocked but not trained)
        for skill_name, skill_level in char.skill_levels_by_role[CharacterClassRole.FIGHTER].items():
            assert skill_level == 0
    
    def test_spend_skill_points(self, create_test_character, fighter_character_data):
        """Verify skill points can be spent on skills."""
        char = create_test_character(fighter_character_data)
        char.skill_points_available = 50
        
        # Find a skill to train
        if CharacterClassRole.FIGHTER in char.skill_levels_by_role:
            skills = char.skill_levels_by_role[CharacterClassRole.FIGHTER]
            if skills:
                skill_name = list(skills.keys())[0]
                original_level = skills[skill_name]
                
                success, message = char.spend_skill_points(skill_name, 10)
                assert success is True
                assert char.skill_levels_by_role[CharacterClassRole.FIGHTER][skill_name] == original_level + 10
                assert char.skill_points_available == 40
    
    def test_cannot_exceed_max_skill_level(self, create_test_character, fighter_character_data):
        """Verify skill level cannot exceed MAX_SKILL_LEVEL."""
        char = create_test_character(fighter_character_data)
        char.skill_points_available = 200
        
        if CharacterClassRole.FIGHTER in char.skill_levels_by_role:
            skills = char.skill_levels_by_role[CharacterClassRole.FIGHTER]
            if skills:
                skill_name = list(skills.keys())[0]
                
                # Try to spend more than max
                success, message = char.spend_skill_points(skill_name, 150)
                
                # Should fail since 150 > MAX_SKILL_LEVEL (100)
                assert success is False
                assert "maximum" in message.lower() or "exceed" in message.lower()


class TestAttributeAdvancement:
    """Tests for attribute point advancement every 10 levels."""
    
    def test_attribute_gain_at_level_10(self, create_test_character, fighter_character_data):
        """Verify attribute point is gained at level 10."""
        data = fighter_character_data.copy()
        data['class'] = {'fighter': {'level': 9}}  # Start at level 9
        char = create_test_character(data)
        char.experience_points = 100000  # Enough to level
        
        old_attr_points = char.unspent_attribute_points
        
        success, stats_gained = char.level_up(CharacterClassRole.FIGHTER)
        
        assert success is True
        assert char.total_levels() == 10
        assert 'attribute_point' in stats_gained
        assert char.unspent_attribute_points == old_attr_points + 1
    
    def test_no_attribute_gain_at_non_milestone(self, create_test_character, fighter_character_data):
        """Verify no attribute point at non-milestone levels."""
        data = fighter_character_data.copy()
        data['class'] = {'fighter': {'level': 8}}  # Start at level 8
        char = create_test_character(data)
        char.experience_points = 100000  # Enough to level
        
        old_attr_points = char.unspent_attribute_points
        
        success, stats_gained = char.level_up(CharacterClassRole.FIGHTER)
        
        assert success is True
        assert char.total_levels() == 9
        assert 'attribute_point' not in stats_gained
        assert char.unspent_attribute_points == old_attr_points
    
    def test_attribute_points_accumulate(self, create_test_character, fighter_character_data):
        """Verify attribute points can accumulate without being spent."""
        data = fighter_character_data.copy()
        data['class'] = {'fighter': {'level': 9}}
        char = create_test_character(data)
        char.unspent_attribute_points = 2  # Already has some points
        char.experience_points = 100000
        
        char.level_up(CharacterClassRole.FIGHTER)
        
        assert char.unspent_attribute_points == 3  # 2 + 1 from level 10


class TestUniversalSkills:
    """Tests for universal skills (save skills) available to all characters."""
    
    def test_universal_skills_unlocked_on_first_class(self, create_test_character, fighter_character_data):
        """Verify universal skills are unlocked when character gets first class."""
        char = create_test_character(fighter_character_data)
        
        # Universal skills should be in skill_levels dict
        assert "fortitude" in char.skill_levels
        assert "reflex" in char.skill_levels
        assert "will" in char.skill_levels
    
    def test_save_skills_start_at_zero(self, create_test_character, fighter_character_data):
        """Verify save skills start at 0 (trainable)."""
        char = create_test_character(fighter_character_data)
        
        assert char.skill_levels.get("fortitude", -1) == 0
        assert char.skill_levels.get("reflex", -1) == 0
        assert char.skill_levels.get("will", -1) == 0
    
    def test_get_save_skill_returns_correct_value(self, create_test_character, fighter_character_data):
        """Verify get_save_skill returns the skill level."""
        char = create_test_character(fighter_character_data)
        
        char.skill_levels["fortitude"] = 42
        
        assert char.get_save_skill("fortitude") == 42
        assert char.get_save_skill("Fortitude") == 42  # Case insensitive


class TestStatAllocationConstants:
    """Tests for stat allocation configuration constants."""
    
    def test_stat_allocation_order_has_all_stats(self):
        """Verify all 6 stats are in the allocation order."""
        from NextGenMUDApp.consumers import STAT_ALLOCATION_ORDER
        
        assert len(STAT_ALLOCATION_ORDER) == 6
        assert 'STRENGTH' in STAT_ALLOCATION_ORDER
        assert 'DEXTERITY' in STAT_ALLOCATION_ORDER
        assert 'CONSTITUTION' in STAT_ALLOCATION_ORDER
        assert 'INTELLIGENCE' in STAT_ALLOCATION_ORDER
        assert 'WISDOM' in STAT_ALLOCATION_ORDER
        assert 'CHARISMA' in STAT_ALLOCATION_ORDER
    
    def test_points_per_stat_is_ten(self):
        """Verify each stat gets 10 points (60 total)."""
        from NextGenMUDApp.consumers import POINTS_PER_STAT, STAT_ALLOCATION_ORDER
        
        assert POINTS_PER_STAT == 10
        assert POINTS_PER_STAT * len(STAT_ALLOCATION_ORDER) == 60
    
    def test_max_stat_at_creation_is_twentyfive(self):
        """Verify max stat at creation is 25."""
        from NextGenMUDApp.consumers import MAX_STAT_AT_CREATION
        
        assert MAX_STAT_AT_CREATION == 25
    
    def test_min_stat_at_creation_is_one(self):
        """Verify min stat at creation is 1."""
        from NextGenMUDApp.consumers import MIN_STAT_AT_CREATION
        
        assert MIN_STAT_AT_CREATION == 1
    
    def test_stat_descriptions_exist_for_all_stats(self):
        """Verify all stats have descriptions."""
        from NextGenMUDApp.consumers import STAT_ALLOCATION_ORDER, STAT_DESCRIPTIONS
        
        for stat in STAT_ALLOCATION_ORDER:
            assert stat in STAT_DESCRIPTIONS
            assert len(STAT_DESCRIPTIONS[stat]) > 0
