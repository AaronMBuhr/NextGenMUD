from ..constants import Constants, CharacterClassRole
from ..nondb_models.characters import Character

class LevelUpHandler:
    """Handler for level up and specialization selection"""
    
    @classmethod
    def handle_multiclass(cls, character: Character, role: CharacterClassRole) -> tuple[bool, str]:
        """
        Handle adding a new class to a character (multiclassing).
        Returns a tuple: (success, message)
        """
        # Check if character can multiclass
        if role in character.class_priority:
            return False, f"You are already a {CharacterClassRole.field_name(role).title()}."
        
        if len(character.class_priority) >= character.max_class_count:
            current_classes = [CharacterClassRole.field_name(r).title() for r in character.class_priority]
            return False, f"You can only have {character.max_class_count} classes. Your classes: {', '.join(current_classes)}"
        
        # Check if this is a base class (can't multiclass into specializations)
        if not CharacterClassRole.is_base_class(role):
            return False, "You can only multiclass into base classes (Fighter, Rogue, Mage, Cleric)."
        
        # Check XP requirement for multiclassing
        if not character.can_level():
            next_xp = Constants.XP_PROGRESSION[character.total_levels()]
            return False, f"You need {next_xp:,} XP to multiclass. You have {character.experience_points:,} XP."
        
        # Check for unspent skill points
        if character.has_unspent_skill_points():
            return False, f"You must spend your {character.skill_points_available} skill points before multiclassing. Use 'skillup <skill> <points>'."
        
        # Add the new class
        success = character.add_class(role)
        if not success:
            return False, "Failed to add new class."
        
        # Update class features for the new multiclass combination
        character._update_class_features()
        
        class_name = CharacterClassRole.field_name(role).title()
        messages = [
            f"*** MULTICLASS! ***",
            f"You have become a level 1 {class_name}!",
            ""
        ]
        
        # Show stats gained from the new class
        hp_gain = Constants.HP_BY_CHARACTER_CLASS.get(role, 0)
        if hp_gain > 0:
            messages.append(f"  +{hp_gain} HP (now {character.current_hit_points}/{character.max_hit_points})")
        
        mana_gain = Constants.MANA_BY_CHARACTER_CLASS.get(role, 0)
        if mana_gain > 0:
            messages.append(f"  +{mana_gain} Mana (now {int(character.current_mana)}/{character.max_mana})")
        
        stamina_gain = Constants.STAMINA_BY_CHARACTER_CLASS.get(role, 0)
        if stamina_gain > 0:
            messages.append(f"  +{stamina_gain} Stamina (now {int(character.current_stamina)}/{character.max_stamina})")
        
        skill_points_gain = Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(role, 0)
        if skill_points_gain > 0:
            character.skill_points_available += skill_points_gain
            messages.append(f"  +{skill_points_gain} Skill Points (now {character.skill_points_available} available)")
        
        # Show new class skills
        if role in character.skill_levels_by_role and character.skill_levels_by_role[role]:
            messages.append("")
            messages.append("These skills are now available to you:")
            for skill_name in character.skill_levels_by_role[role].keys():
                display_name = skill_name.replace('_', ' ').title()
                messages.append(f"  - {display_name}")
        
        messages.append("")
        messages.append(f"Use 'skills' to see your available skills.")
        messages.append(f"Use 'skillup <skill> <points>' to improve your skills.")
        
        return True, "\n".join(messages)
    
    @classmethod
    def handle_level_up(cls, character: Character, role: CharacterClassRole) -> tuple[bool, str]:
        """
        Handle leveling up a character in a specific class role.
        If the character doesn't have the class yet, handles multiclassing.
        Returns a tuple: (success, message)
        """
        # If character doesn't have this class, try to multiclass
        if role not in character.class_priority:
            return cls.handle_multiclass(character, role)
        
        # Use the character's comprehensive check
        can_level, reason = character.can_perform_levelup(role)
        if not can_level:
            return False, reason
            
        # Level up the character
        success, stats_gained = character.level_up(role)
        
        if not success:
            return False, "Failed to level up."
        
        # Build detailed level up message
        class_name = character.get_display_class_name(role)
        new_level = stats_gained.get('level', character.levels_by_role[role])
        
        messages = [
            f"*** LEVEL UP! ***",
            f"You have advanced to level {new_level} {class_name.title()}!",
            "",
            "Stats gained:"
        ]
        
        hp = stats_gained.get('hp', 0)
        if hp > 0:
            messages.append(f"  +{hp} HP (now {character.current_hit_points}/{character.max_hit_points})")
        
        mana = stats_gained.get('mana', 0)
        if mana > 0:
            messages.append(f"  +{mana} Mana (now {int(character.current_mana)}/{character.max_mana})")
        
        stamina = stats_gained.get('stamina', 0)
        if stamina > 0:
            messages.append(f"  +{stamina} Stamina (now {int(character.current_stamina)}/{character.max_stamina})")
        
        skill_points = stats_gained.get('skill_points', 0)
        if skill_points > 0:
            messages.append(f"  +{skill_points} Skill Points (now {character.skill_points_available} available)")
        
        # Show newly unlocked skills
        new_skills = stats_gained.get('new_skills', [])
        if new_skills:
            messages.append("")
            messages.append("These skills are now available to you:")
            for skill_name in new_skills:
                messages.append(f"  - {skill_name}")
        
        messages.append("")
        messages.append(f"Use 'skills' to see your available skills.")
        messages.append(f"Use 'skillup <skill> <points>' to improve your skills.")
        
        return True, "\n".join(messages)
    
    @classmethod
    def handle_skill_up(cls, character: Character, skill_name: str, points: int) -> tuple[bool, str]:
        """
        Handle spending skill points on a skill.
        Returns a tuple: (success, message)
        """
        return character.spend_skill_points(skill_name, points)
    
    @classmethod
    def get_available_specializations(cls, character: Character):
        """Get the available specializations for a character"""
        available = {}
        
        for role in character.class_priority:
            if character.can_specialize(role):
                available[role] = CharacterClassRole.get_specializations(role)
                
        return available
    
    @classmethod
    def handle_specialization_selection(cls, character: Character, base_class: CharacterClassRole, specialization: CharacterClassRole):
        """
        Handle selecting a specialization for a base class.
        Returns a tuple: (success, message)
        """
        # Check if the character can specialize in this class
        if not character.can_specialize(base_class):
            # Check if already specialized
            if base_class in character.specializations:
                return False, f"You are already specialized as a {CharacterClassRole.field_name(character.specializations[base_class])}."
            
            # Check level requirement
            if base_class in character.levels_by_role and character.levels_by_role[base_class] < Constants.SPECIALIZATION_LEVEL:
                return False, f"You need to be level {Constants.SPECIALIZATION_LEVEL} to specialize."
                
            return False, "You cannot specialize in that class."
            
        # Check if the specialization is valid for this base class
        if specialization not in CharacterClassRole.get_specializations(base_class):
            return False, f"That is not a valid specialization for a {CharacterClassRole.field_name(base_class)}."
            
        # Apply the specialization
        success = character.choose_specialization(base_class, specialization)
        
        if success:
            spec_name = CharacterClassRole.field_name(specialization)
            base_name = CharacterClassRole.field_name(base_class)
            return True, f"You have specialized as a {spec_name}! Your journey as a {base_name} takes a new path."
        else:
            return False, "Failed to choose specialization." 