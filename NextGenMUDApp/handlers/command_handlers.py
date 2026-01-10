from ..constants import CharacterClassRole, Constants
from .level_up_handler import LevelUpHandler

def handle_level_command(char, args, game_state):
    """Handle the 'level' command for checking XP and leveling status"""
    
    # Show current level and XP
    total_level = char.total_levels()
    
    response = [
        f"=== Character Level Status ===",
        f"Total Level: {total_level} / {Constants.MAX_LEVEL}",
        f"Experience: {char.experience_points:,} XP"
    ]
    
    # Show XP needed for next level
    if total_level < Constants.MAX_LEVEL:
        next_level_xp = Constants.XP_PROGRESSION[total_level]
        xp_needed = next_level_xp - char.experience_points
        if xp_needed > 0:
            response.append(f"XP to next level: {xp_needed:,}")
        else:
            response.append("Ready to level up!")
    else:
        response.append("Maximum level reached!")
    
    response.append("")
    
    # Add class breakdown
    response.append("Class Levels:")
    for role in char.class_priority:
        class_name = char.get_display_class_name(role)
        level = char.levels_by_role[role]
        response.append(f"  {class_name.title()}: Level {level}")
    
    response.append("")
    
    # Show skill points
    response.append(f"Skill Points Available: {char.skill_points_available}")
    
    # Check for available level-ups
    if char.can_level():
        if char.has_unspent_skill_points():
            response.append("")
            response.append(f"You have {char.skill_points_available} unspent skill points!")
            response.append("Use 'skillup <skill> <points>' to spend them before leveling up.")
        else:
            response.append("")
            response.append("You have enough experience to advance a level!")
            response.append("Use 'levelup <class>' to level up.")
    
    # Check for available specializations
    available_specs = LevelUpHandler.get_available_specializations(char)
    if available_specs:
        response.append("")
        response.append("Specialization available for:")
        for base_class, specializations in available_specs.items():
            base_name = CharacterClassRole.field_name(base_class)
            spec_names = [CharacterClassRole.field_name(spec).title() for spec in specializations]
            response.append(f"  {base_name.title()}: {', '.join(spec_names)}")
        response.append("Use 'specialize <class> <specialization>' to choose.")
    
    char.send_output("\n".join(response))
    return True

def handle_levelup_command(char, args, game_state):
    """Handle the 'levelup' command for advancing a level"""
    if not args:
        # If only one class, level that one automatically
        if len(char.class_priority) == 1:
            role = char.class_priority[0]
        else:
            class_names = [CharacterClassRole.field_name(r).title() for r in char.class_priority]
            char.send_output(f"Usage: levelup <class>")
            char.send_output(f"Your classes: {', '.join(class_names)}")
            return True
    else:
        class_name = args[0].upper()
        try:
            role = CharacterClassRole[class_name]
        except KeyError:
            char.send_output(f"Unknown class: {args[0]}")
            return True
    
    success, message = LevelUpHandler.handle_level_up(char, role)
    char.send_output(message)
    return True

def handle_skillup_command(char, args, game_state):
    """Handle the 'skillup' command for spending skill points on skills"""
    if len(args) < 1:
        char.send_output("Usage: skillup <skill> [points]")
        char.send_output(f"You have {char.skill_points_available} skill points available.")
        char.send_output("Use 'skills' to see your available skills.")
        return True
    
    # Parse skill name and points
    # Last argument might be a number (points to spend)
    points = 1  # Default to 1 point
    skill_parts = args[:]
    
    if len(args) >= 2 and args[-1].isdigit():
        points = int(args[-1])
        skill_parts = args[:-1]
    
    skill_name = ' '.join(skill_parts)
    
    success, message = LevelUpHandler.handle_skill_up(char, skill_name, points)
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
    "skillup": handle_skillup_command,
    "specialize": handle_specialize_command,
} 