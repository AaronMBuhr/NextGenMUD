from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum

from ..structured_logger import StructuredLogger
from ..utility import evaluate_if_condition

if TYPE_CHECKING:
    from .characters import Character

# ==========================================
# PART 1: QUEST SCHEMA & REGISTRY
# (Logic imported from quest_schema.py)
# ==========================================

class QuestVarType(Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"

@dataclass
class KnowledgeUpdate:
    """A knowledge update triggered by a variable value."""
    condition: Any  # The value that triggers this update
    updates: Dict[str, str] = field(default_factory=dict)  # knowledge_id -> content (keys are ids to add)
    replaces: List[str] = field(default_factory=list)  # knowledge ids to remove from the list when this update runs

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
        if self.default is not None:
            return self.default
        if self.var_type == QuestVarType.BOOLEAN:
            return False
        if self.var_type == QuestVarType.STRING:
            return ""
        if self.var_type == QuestVarType.INTEGER:
            return 0
        return None

class QuestSchemaRegistry:
    """Registry of quest variable definitions."""
    _instance: Optional['QuestSchemaRegistry'] = None
    
    def __init__(self):
        self._variables: Dict[str, QuestVariable] = {}
        self._logger = StructuredLogger(__name__, prefix="QuestSchemaRegistry> ")
    
    @classmethod
    def get_instance(cls) -> 'QuestSchemaRegistry':
        if cls._instance is None:
            cls._instance = QuestSchemaRegistry()
        return cls._instance
    
    def register_variable(self, variable: QuestVariable) -> None:
        self._variables[variable.id] = variable
        self._logger.debug(f"Registered quest variable: {variable.id}")
    
    def get_variable(self, var_id: str) -> Optional[QuestVariable]:
        return self._variables.get(var_id)
    
    def get_variables_by_category(self, category: str) -> List[QuestVariable]:
        matching = []
        for v in self._variables.values():
            if v.id.startswith(f"{category}."):
                matching.append(v)
        return matching
    
    def load_from_dict(self, data: dict, zone_id: Optional[str] = None) -> int:
        count = 0
        for category, variables in data.items():
            if not isinstance(variables, dict): continue
            
            for var_name, var_def in variables.items():
                if not isinstance(var_def, dict): continue
                
                if zone_id:
                    full_id = f"{zone_id}.{category}.{var_name}"
                    full_category = f"{zone_id}.{category}"
                else:
                    full_id = f"{category}.{var_name}"
                    full_category = category
                
                type_str = var_def.get("type", "boolean").lower()
                try:
                    var_type = QuestVarType(type_str)
                except ValueError:
                    var_type = QuestVarType.BOOLEAN
                
                knowledge_updates = []
                for ku in var_def.get("knowledge_updates", []):
                    if isinstance(ku, dict) and "condition" in ku and "updates" in ku:
                        repl = ku.get("replaces", [])
                        if not isinstance(repl, list):
                            repl = [repl] if repl else []
                        knowledge_updates.append(KnowledgeUpdate(
                            condition=ku["condition"],
                            updates=ku.get("updates", {}),
                            replaces=repl,
                        ))
                
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
        self._variables.clear()

# ==========================================
# PART 2: HELPER FUNCTIONS
# ==========================================

def _defining_zone_id(actor: Any) -> Optional[str]:
    """Return the zone id of the zone that defines this actor (where it was spawned/defined)."""
    if actor is None:
        return None
    if hasattr(actor, 'definition_zone_id') and getattr(actor, 'definition_zone_id', None):
        return actor.definition_zone_id
    zone = getattr(actor, 'zone', None)
    if zone is not None and hasattr(zone, 'id'):
        return zone.id
    loc = getattr(actor, 'location_room', None)
    if loc and getattr(loc, 'zone', None) and getattr(loc.zone, 'id', None):
        return loc.zone.id
    return None


def _resolve_var_id(player, var_id: str, invoking_actor: Any = None) -> str:
    """
    Resolve a possibly short var_id (e.g. murder_mystery.found_note) to a full zone-prefixed key.
    When var_id has no zone prefix (2 parts), the prefix is taken from the actor running the script
    (invoking_actor) if provided, so that quest vars are scoped to the defining zone of the script,
    not the target's current location.
    """
    parts = var_id.split('.')
    if len(parts) >= 3:
        return var_id
    if len(parts) == 2:
        zone_id = None
        if invoking_actor is not None:
            zone_id = _defining_zone_id(invoking_actor)
        if zone_id is None and player.location_room and hasattr(player.location_room, 'zone') and player.location_room.zone:
            zone_id = player.location_room.zone.id
        if zone_id is None and hasattr(player, 'definition_zone_id') and player.definition_zone_id:
            zone_id = player.definition_zone_id
        if zone_id:
            return f"{zone_id}.{var_id}"
    return var_id


def _zone_and_quest_from_var_id(full_var_id: str, player: Any, invoking_actor: Any = None) -> tuple:
    """
    Derive (zone_id, quest_id) from a full quest variable id.
    full_var_id is like 'gloomy_graveyard.murder_mystery.heard_about_murder' or 'murder_mystery.found_body'.
    Returns (zone_id, quest_id) or (None, None) if not enough parts.
    When full_var_id has only 2 parts, uses invoking_actor's defining zone if provided.
    """
    parts = full_var_id.split(".")
    if len(parts) >= 3:
        return parts[0], parts[1]
    if len(parts) == 2:
        zone_id = None
        if invoking_actor is not None:
            zone_id = _defining_zone_id(invoking_actor)
        if zone_id is None and player.location_room and hasattr(player.location_room, "zone") and player.location_room.zone:
            zone_id = player.location_room.zone.id
        if zone_id is None and hasattr(player, "definition_zone_id") and player.definition_zone_id:
            zone_id = player.definition_zone_id
        if zone_id:
            return zone_id, parts[0]
    return None, None


def add_quest_llm_knowledge(player: Any, zone_id: str, quest_id: str, knowledge_ids: List[str]) -> None:
    """
    Append knowledge ids to the quest's llm_knowledge list (append-only, no duplicates).
    Key: {zone_id}.{quest_id}.llm_knowledge = list of ids.
    """
    if player.perm_variables is None:
        player.perm_variables = {}
    key = f"{zone_id}.{quest_id}.llm_knowledge"
    current = player.perm_variables.get(key, [])
    if not isinstance(current, list):
        current = []
    for kid in knowledge_ids:
        if kid not in current:
            current.append(kid)
    player.perm_variables[key] = current


def add_zone_llm_knowledge(player: Any, zone_id: str, knowledge_ids: List[str]) -> None:
    """
    Append knowledge ids to the zone's llm_knowledge list (append-only, no duplicates).
    Key: {zone_id}.llm_knowledge = list of ids.
    """
    if player.perm_variables is None:
        player.perm_variables = {}
    key = f"{zone_id}.llm_knowledge"
    current = player.perm_variables.get(key, [])
    if not isinstance(current, list):
        current = []
    for kid in knowledge_ids:
        if kid not in current:
            current.append(kid)
    player.perm_variables[key] = current


def remove_quest_llm_knowledge(player: Any, zone_id: str, quest_id: str, knowledge_ids: List[str]) -> None:
    """
    Remove the given knowledge ids from the quest's llm_knowledge list.
    Key: {zone_id}.{quest_id}.llm_knowledge. No-op for ids not in the list.
    """
    if not knowledge_ids:
        return
    if player.perm_variables is None:
        return
    key = f"{zone_id}.{quest_id}.llm_knowledge"
    current = player.perm_variables.get(key, [])
    if not isinstance(current, list):
        return
    remove_set = set(knowledge_ids)
    player.perm_variables[key] = [k for k in current if k not in remove_set]


def remove_zone_llm_knowledge(player: Any, zone_id: str, knowledge_ids: List[str]) -> None:
    """
    Remove the given knowledge ids from the zone's llm_knowledge list.
    Key: {zone_id}.llm_knowledge. No-op for ids not in the list.
    """
    if not knowledge_ids:
        return
    if player.perm_variables is None:
        return
    key = f"{zone_id}.llm_knowledge"
    current = player.perm_variables.get(key, [])
    if not isinstance(current, list):
        return
    remove_set = set(knowledge_ids)
    player.perm_variables[key] = [k for k in current if k not in remove_set]


def get_resolved_llm_knowledge(game_state: Any, player: Any) -> Dict[str, str]:
    """
    Collect all llm_knowledge list keys from player.perm_variables, resolve each
    knowledge id to content via zone.common_knowledge. Returns knowledge_id -> content.
    Later occurrence overwrites if same id appears in multiple zones (e.g. same id in zone + quest).
    """
    if not getattr(player, "perm_variables", None):
        return {}
    zones = getattr(game_state, "zones", None) or {}
    result: Dict[str, str] = {}
    for key, value in player.perm_variables.items():
        if not key.endswith(".llm_knowledge") or not isinstance(value, list):
            continue
        parts = key.split(".")
        # key is zone_id.llm_knowledge or zone_id.quest_id.llm_knowledge
        zone_id = parts[0] if parts else None
        if not zone_id or zone_id not in zones:
            continue
        zone = zones[zone_id]
        common = getattr(zone, "common_knowledge", None) or {}
        for kid in value:
            if kid in common:
                result[kid] = common[kid]
    return result

def set_quest_var(player, var_id: str, value: Any, auto_update_knowledge: bool = True,
                  game_state: Any = None, debug_setquestvar: bool = False, invoking_actor: Any = None) -> bool:
    logger = StructuredLogger(__name__, prefix="set_quest_var> ")
    full_var_id = _resolve_var_id(player, var_id, invoking_actor=invoking_actor)
    
    if debug_setquestvar:
        loc_room = getattr(player, "location_room", None)
        zone = getattr(loc_room, "zone", None) if loc_room else None
        inv_zone = _defining_zone_id(invoking_actor) if invoking_actor else None
        logger.debug(
            f"[setquestvar] set_quest_var: player.id={getattr(player, 'id', None)}, player.name={getattr(player, 'name', None)}, "
            f"var_id={var_id!r}, full_var_id={full_var_id!r}, value={value!r}; "
            f"player.location_room={loc_room}, zone={getattr(zone, 'id', None) if zone else None}, invoking_actor_zone={inv_zone}"
        )
    
    if player.perm_variables is None:
        player.perm_variables = {}

    player.perm_variables[full_var_id] = value
    logger.debug(f"Set {full_var_id} = {value} for player {player.name}")
    
    if debug_setquestvar:
        logger.debug(f"[setquestvar] wrote player.perm_variables[{full_var_id!r}] = {value!r}; id(perm_variables)={id(player.perm_variables)}")
    
    if not auto_update_knowledge:
        return True
    
    registry = QuestSchemaRegistry.get_instance()
    var_def = registry.get_variable(full_var_id)
    
    if var_def is None:
        return True
    
    zone_id, quest_id = _zone_and_quest_from_var_id(full_var_id, player, invoking_actor=invoking_actor)
    if zone_id and quest_id:
        for ku in var_def.knowledge_updates:
            # Simple equality check, can be expanded
            if str(ku.condition) == str(value) or ku.condition == value:
                # updates dict: keys are knowledge ids to add (content lives in zone common_knowledge)
                ids_to_add = list(ku.updates.keys())
                if ids_to_add:
                    add_quest_llm_knowledge(player, zone_id, quest_id, ids_to_add)
                    for kid in ids_to_add:
                        logger.debug(f"Auto-added quest knowledge '{kid}' for player {player.name}")
                if ku.replaces:
                    remove_quest_llm_knowledge(player, zone_id, quest_id, ku.replaces)
                    for kid in ku.replaces:
                        logger.debug(f"Auto-removed quest knowledge '{kid}' for player {player.name}")
    return True

def get_quest_var(player, var_id: str, default: Any = None, invoking_actor: Any = None) -> Any:
    full_var_id = _resolve_var_id(player, var_id, invoking_actor=invoking_actor)
    
    if player.perm_variables and full_var_id in player.perm_variables:
        return player.perm_variables[full_var_id]
    
    registry = QuestSchemaRegistry.get_instance()
    var_def = registry.get_variable(full_var_id)
    
    if var_def is not None:
        return var_def.get_default()
    
    return default

# ==========================================
# PART 3: NEW QUEST LOGIC (State Machine)
# ==========================================

class QuestCondition:
    """Evaluates a single condition using the variable helpers."""
    def __init__(self, variable: str, operator: str, value: Any):
        self.variable = variable
        self.operator = operator
        self.value = value

    def check(self, actor) -> bool:
        # Retrieve the actual value using the schema logic above
        current_val = get_quest_var(actor, self.variable)
        # Use utility to evaluate (matches script logic)
        condition_str = f"{current_val},{self.operator},{self.value}"
        return evaluate_if_condition(condition_str, {}, None)

class QuestStage:
    """A distinct state in a quest."""
    def __init__(self, name: str, description: str, sequence: int, conditions: List[QuestCondition]):
        self.name = name
        self.description = description
        self.sequence = sequence 
        self.conditions = conditions

    def is_active(self, actor) -> bool:
        return all(c.check(actor) for c in self.conditions)

class Quest:
    """The definition of a quest, holding all possible stages."""
    def __init__(self, id: str, title: str, stages: List[QuestStage], zone_id: str):
        self.id = id
        self.title = title
        self.zone_id = zone_id
        # Sort stages by sequence (descending) for priority checking
        self.stages = sorted(stages, key=lambda x: x.sequence, reverse=True)

    def get_active_stage(self, actor) -> Optional[QuestStage]:
        for stage in self.stages:
            if stage.is_active(actor):
                return stage
        return None

    def get_history(self, active_sequence: int) -> List[QuestStage]:
        history = [s for s in self.stages if s.sequence < active_sequence]
        return sorted(history, key=lambda x: x.sequence)
