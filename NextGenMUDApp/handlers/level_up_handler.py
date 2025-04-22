from ..constants import Constants, CharacterClassRole
from ..nondb_models.characters import Character

class LevelUpHandler:
    """Handler for level up and specialization selection"""
    
    @classmethod
    def handle_level_up(cls, character: Character, role: CharacterClassRole):
        """
        Handle leveling up a character in a specific class role.
        Returns a tuple: (success, message)
        """
        # Check if the character can level up
        if not character.can_level():
            return False, "You don't have enough experience to level up."
            
        # Check if the character has the class
        if role not in character.class_priority:
            return False, f"You are not a {CharacterClassRole.field_name(role)}."
            
        # Level up the character
        character.level_up(role)
        class_name = character.get_display_class_name(role)
        return True, f"You have advanced to level {character.levels_by_role[role]} {class_name}!"
    
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