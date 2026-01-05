"""
Quest Variable Schema System

Defines quest variables with automatic world knowledge updates.
When a quest variable is set, associated common knowledge is automatically
updated for the player, so NPCs react appropriately.

YAML Schema Format (in zone files or separate quest_schema.yaml):

    quest_variables:
      murder_mystery:                    # Quest/category name
        found_body:                      # Variable name
          description: "Player discovered the mayor's body"
          type: boolean                  # boolean, string, integer
          default: false
          knowledge_updates:             # When value changes, update world knowledge
            - condition: true            # When variable equals this value
              updates:
                murder_case: "The mayor's body was discovered in the old mill"
                village_mood: "The village is in shock after the grim discovery"
                
        identified_killer:
          description: "Player identified the killer"
          type: string                   # Can be "unknown", "blacksmith", "innkeeper"
          default: "unknown"
          knowledge_updates:
            - condition: "blacksmith"
              updates:
                murder_case: "The blacksmith has been identified as the killer"
            - condition: "innkeeper"  
              updates:
                murder_case: "The innkeeper was behind the murder all along"
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING
from enum import Enum

from .structured_logger import StructuredLogger

if TYPE_CHECKING:
    from .nondb_models.characters import Character
    from .comprehensive_game_state_interface import GameStateInterface


class QuestVarType(Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"


@dataclass
class KnowledgeUpdate:
    """A knowledge update triggered by a variable value."""
    condition: Any  # The value that triggers this update
    updates: Dict[str, str] = field(default_factory=dict)  # knowledge_id -> content


@dataclass
class QuestVariable:
    """Definition of a quest variable."""
    id: str  # Full ID like "murder_mystery.found_body"
    name: str  # Short name like "found_body"
    category: str  # Category like "murder_mystery"
    description: str = ""
    var_type: QuestVarType = QuestVarType.BOOLEAN
    default: Any = None
    knowledge_updates: List[KnowledgeUpdate] = field(default_factory=list)
    
    def get_default(self) -> Any:
        """Get the default value based on type."""
        if self.default is not None:
            return self.default
        if self.var_type == QuestVarType.BOOLEAN:
            return False
        if self.var_type == QuestVarType.STRING:
            return ""
        if self.var_type == QuestVarType.INTEGER:
            return 0
        return None
    
    def validate_value(self, value: Any) -> bool:
        """Check if a value is valid for this variable type."""
        if self.var_type == QuestVarType.BOOLEAN:
            return isinstance(value, bool)
        if self.var_type == QuestVarType.STRING:
            return isinstance(value, str)
        if self.var_type == QuestVarType.INTEGER:
            return isinstance(value, int)
        return True


class QuestSchemaRegistry:
    """
    Registry of quest variable definitions.
    
    Loads schema from YAML and provides methods to set variables
    with automatic knowledge updates.
    """
    
    # Singleton instance
    _instance: Optional['QuestSchemaRegistry'] = None
    
    def __init__(self):
        self._variables: Dict[str, QuestVariable] = {}
        self._logger = StructuredLogger(__name__, prefix="QuestSchemaRegistry> ")
    
    @classmethod
    def get_instance(cls) -> 'QuestSchemaRegistry':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = QuestSchemaRegistry()
        return cls._instance
    
    def register_variable(self, variable: QuestVariable) -> None:
        """Register a quest variable definition."""
        self._variables[variable.id] = variable
        self._logger.debug(f"Registered quest variable: {variable.id}")
    
    def get_variable(self, var_id: str) -> Optional[QuestVariable]:
        """Get a variable definition by ID."""
        return self._variables.get(var_id)
    
    def get_all_variables(self) -> Dict[str, QuestVariable]:
        """Get all registered variables."""
        return self._variables.copy()
    
    def get_variables_by_category(self, category: str) -> List[QuestVariable]:
        """
        Get all variables in a category.
        
        Category format is "zone_id.category_name" as stored in variable definitions.
        """
        # Category in the variable is stored as just the category part,
        # but the full ID is zone.category.name
        # So we need to match variables where id starts with "category."
        # or where the full path matches
        
        matching = []
        for v in self._variables.values():
            # Check if the variable ID starts with the category prefix
            # e.g., category="gloomy_graveyard.murder_mystery" 
            # matches id="gloomy_graveyard.murder_mystery.found_body"
            if v.id.startswith(f"{category}."):
                matching.append(v)
        
        return matching
    
    def load_from_dict(self, data: dict, zone_id: Optional[str] = None) -> int:
        """
        Load quest variables from a dictionary (parsed from YAML).
        
        Args:
            data: The quest_variables section from YAML
            zone_id: Optional zone ID to prefix variable IDs
            
        Returns:
            Number of variables loaded
        """
        count = 0
        
        for category, variables in data.items():
            if not isinstance(variables, dict):
                self._logger.warning(f"Quest category '{category}' is not a dictionary, skipping")
                continue
            
            for var_name, var_def in variables.items():
                if not isinstance(var_def, dict):
                    self._logger.warning(f"Quest variable '{var_name}' is not a dictionary, skipping")
                    continue
                
                # Build full ID and full category path
                if zone_id:
                    full_id = f"{zone_id}.{category}.{var_name}"
                    full_category = f"{zone_id}.{category}"
                else:
                    full_id = f"{category}.{var_name}"
                    full_category = category
                
                # Parse type
                type_str = var_def.get("type", "boolean").lower()
                try:
                    var_type = QuestVarType(type_str)
                except ValueError:
                    self._logger.warning(f"Unknown type '{type_str}' for {full_id}, defaulting to boolean")
                    var_type = QuestVarType.BOOLEAN
                
                # Parse knowledge updates
                knowledge_updates = []
                for ku in var_def.get("knowledge_updates", []):
                    if isinstance(ku, dict) and "condition" in ku and "updates" in ku:
                        knowledge_updates.append(KnowledgeUpdate(
                            condition=ku["condition"],
                            updates=ku.get("updates", {})
                        ))
                
                # Create and register
                variable = QuestVariable(
                    id=full_id,
                    name=var_name,
                    category=full_category,
                    description=var_def.get("description", ""),
                    var_type=var_type,
                    default=var_def.get("default"),
                    knowledge_updates=knowledge_updates,
                )
                
                self.register_variable(variable)
                count += 1
        
        return count
    
    def clear(self) -> None:
        """Clear all registered variables."""
        self._variables.clear()


def _resolve_var_id(player: 'Character', var_id: str) -> str:
    """
    Resolve a variable ID, adding zone prefix if needed.
    
    - 3+ parts (zone.category.var): Already fully qualified, use as-is
    - 2 parts (category.var): Prefix with player's current zone
    
    Args:
        player: The player character (for zone context)
        var_id: The variable ID
        
    Returns:
        Fully qualified variable ID
    """
    parts = var_id.split('.')
    
    if len(parts) >= 3:
        # Already fully qualified: gloomy_graveyard.murder_mystery.found_body
        return var_id
    
    if len(parts) == 2:
        # Need to add zone prefix: murder_mystery.found_body -> zone.murder_mystery.found_body
        zone_id = None
        if player.location_room and hasattr(player.location_room, 'zone') and player.location_room.zone:
            zone_id = player.location_room.zone.id
        elif hasattr(player, 'definition_zone_id') and player.definition_zone_id:
            zone_id = player.definition_zone_id
        
        if zone_id:
            return f"{zone_id}.{var_id}"
    
    # Single part or couldn't resolve zone - return as-is
    return var_id


def set_quest_var(
    player: 'Character',
    var_id: str,
    value: Any,
    auto_update_knowledge: bool = True
) -> bool:
    """
    Set a quest variable for a player with automatic knowledge updates.
    
    If the variable is defined in the schema and has knowledge_updates,
    the appropriate world knowledge will be set automatically.
    
    Variable ID formats:
    - Full: "gloomy_graveyard.murder_mystery.found_body"
    - Local: "murder_mystery.found_body" (uses player's current zone)
    
    Args:
        player: The player character
        var_id: The variable ID
        value: The value to set
        auto_update_knowledge: Whether to auto-update world knowledge
        
    Returns:
        True if the variable was set successfully
        
    Example:
        # Full path
        set_quest_var(player, "gloomy_graveyard.murder_mystery.found_body", True)
        
        # Or local (if player is in gloomy_graveyard)
        set_quest_var(player, "murder_mystery.found_body", True)
    """
    logger = StructuredLogger(__name__, prefix="set_quest_var> ")
    
    # Resolve to full ID if needed
    full_var_id = _resolve_var_id(player, var_id)
    
    # Set the variable on the player
    player.perm_variables[full_var_id] = value
    logger.debug(f"Set {full_var_id} = {value} for player {player.name}")
    
    if not auto_update_knowledge:
        return True
    
    # Check if this variable is in the schema
    registry = QuestSchemaRegistry.get_instance()
    var_def = registry.get_variable(full_var_id)
    
    if var_def is None:
        # Not in schema, just set the variable without knowledge updates
        logger.debug(f"Variable {full_var_id} not in schema, no knowledge updates")
        return True
    
    # Check for knowledge updates that match this value
    from .llm_npc_conversation import NPCConversationHandler
    
    for ku in var_def.knowledge_updates:
        if ku.condition == value:
            # Apply all knowledge updates
            for knowledge_id, content in ku.updates.items():
                NPCConversationHandler.set_world_knowledge(player, knowledge_id, content)
                logger.debug(f"Auto-updated knowledge '{knowledge_id}' for player {player.name}")
    
    return True


def get_quest_var(
    player: 'Character',
    var_id: str,
    default: Any = None
) -> Any:
    """
    Get a quest variable for a player.
    
    If the variable is in the schema and no value is set, returns the schema default.
    
    Variable ID formats:
    - Full: "gloomy_graveyard.murder_mystery.found_body"
    - Local: "murder_mystery.found_body" (uses player's current zone)
    
    Args:
        player: The player character
        var_id: The variable ID
        default: Default value if not set and not in schema
        
    Returns:
        The variable value
    """
    # Resolve to full ID if needed
    full_var_id = _resolve_var_id(player, var_id)
    
    # Check if set on player
    if full_var_id in player.perm_variables:
        return player.perm_variables[full_var_id]
    
    # Check schema for default
    registry = QuestSchemaRegistry.get_instance()
    var_def = registry.get_variable(full_var_id)
    
    if var_def is not None:
        return var_def.get_default()
    
    return default


def get_quest_progress(player: 'Character', category: str) -> Dict[str, Any]:
    """
    Get all quest variable values for a category.
    
    Category can be:
    - Full: "gloomy_graveyard.murder_mystery"
    - Local: "murder_mystery" (uses player's current zone)
    
    Args:
        player: The player character
        category: The quest category
        
    Returns:
        Dictionary of variable_name -> value
    """
    registry = QuestSchemaRegistry.get_instance()
    
    # If category doesn't have a zone prefix, add one from player's location
    if '.' not in category:
        zone_id = None
        if player.location_room and hasattr(player.location_room, 'zone') and player.location_room.zone:
            zone_id = player.location_room.zone.id
        elif hasattr(player, 'definition_zone_id') and player.definition_zone_id:
            zone_id = player.definition_zone_id
        
        if zone_id:
            category = f"{zone_id}.{category}"
    
    variables = registry.get_variables_by_category(category)
    
    progress = {}
    for var in variables:
        progress[var.name] = get_quest_var(player, var.id)
    
    return progress


def describe_quest_state(player: 'Character', category: str) -> str:
    """
    Get a human-readable description of quest progress.
    Useful for debugging or showing to LLM for context.
    
    Category can be:
    - Full: "gloomy_graveyard.murder_mystery"
    - Local: "murder_mystery" (uses player's current zone)
    
    Args:
        player: The player character
        category: The quest category
        
    Returns:
        Description string
    """
    registry = QuestSchemaRegistry.get_instance()
    
    # If category doesn't have a zone prefix, add one from player's location
    original_category = category
    if '.' not in category:
        zone_id = None
        if player.location_room and hasattr(player.location_room, 'zone') and player.location_room.zone:
            zone_id = player.location_room.zone.id
        elif hasattr(player, 'definition_zone_id') and player.definition_zone_id:
            zone_id = player.definition_zone_id
        
        if zone_id:
            category = f"{zone_id}.{category}"
    
    variables = registry.get_variables_by_category(category)
    
    if not variables:
        return f"No quest variables defined for category '{original_category}'"
    
    lines = [f"Quest progress for '{original_category}':"]
    for var in variables:
        value = get_quest_var(player, var.id)
        desc = var.description or var.name
        lines.append(f"  - {desc}: {value}")
    
    return "\n".join(lines)
