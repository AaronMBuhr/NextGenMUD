from ..constants import CharacterClassRole
from .level_up_handler import LevelUpHandler

def handle_level_command(char, args, game_state):
    """Handle the 'level' command for checking XP and leveling status"""
    
    # Show current level and XP
    total_level = char.total_levels()
    next_level_xp = game_state.constants.XP_PROGRESSION[total_level]
    
    response = [
        f"You are level {total_level} with {char.experience_points} experience points.",
        f"You need {next_level_xp} experience points for your next level."
    ]
    
    # Add class breakdown
    response.append("Class levels:")
    for role in char.class_priority:
        class_name = char.get_display_class_name(role)
        level = char.levels_by_role[role]
        response.append(f"  {class_name}: Level {level}")
    
    # Check for available level-ups
    if char.can_level():
        response.append("You have enough experience to advance a level! Use 'levelup <class>' to level up.")
    
    # Check for available specializations
    available_specs = LevelUpHandler.get_available_specializations(char)
    if available_specs:
        response.append("You can choose a specialization for the following classes:")
        for base_class, specializations in available_specs.items():
            base_name = CharacterClassRole.field_name(base_class)
            spec_names = [CharacterClassRole.field_name(spec) for spec in specializations]
            response.append(f"  {base_name}: {', '.join(spec_names)}")
        response.append("Use 'specialize <class> <specialization>' to choose a specialization.")
    
    char.send_output("\n".join(response))
    return True

def handle_levelup_command(char, args, game_state):
    """Handle the 'levelup' command for advancing a level"""
    if not args:
        char.send_output("Usage: levelup <class>")
        return True
    
    class_name = args[0].upper()
    try:
        role = CharacterClassRole[class_name]
    except KeyError:
        char.send_output(f"Unknown class: {args[0]}")
        return True
    
    success, message = LevelUpHandler.handle_level_up(char, role)
    char.send_output(message)
    return True

def handle_specialize_command(char, args, game_state):
    """Handle the 'specialize' command for choosing a specialization"""
    if len(args) < 2:
        char.send_output("Usage: specialize <class> <specialization>")
        return True
    
    try:
        base_class_name = args[0].upper()
        spec_name = args[1].upper()
        
        base_class = CharacterClassRole[base_class_name]
        specialization = CharacterClassRole[spec_name]
    except KeyError:
        char.send_output(f"Unknown class or specialization: {' '.join(args)}")
        return True
    
    success, message = LevelUpHandler.handle_specialization_selection(char, base_class, specialization)
    char.send_output(message)
    return True

command_handlers = {
    # ... existing commands ...
    "level": handle_level_command,
    "levelup": handle_levelup_command,
    "specialize": handle_specialize_command,
} 