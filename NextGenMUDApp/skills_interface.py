from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Optional, Dict, List, Callable, Tuple, TypeVar, Generic, Any, TYPE_CHECKING


# Import the essentials only, to avoid circular dependencies
from .constants import CharacterClassRole
from .comprehensive_game_state_interface import GameStateInterface
from .nondb_models.actor_interface import ActorInterface

class SkillsInterface(metaclass=ABCMeta):
    
    # Tier level constants
    TIER1_MIN_LEVEL = 1   # Tier 1 skills (levels 1-9)
    TIER2_MIN_LEVEL = 10  # Tier 2 skills (levels 10-19)
    TIER3_MIN_LEVEL = 20  # Tier 3 skills (levels 20-29) - specialization skills
    TIER4_MIN_LEVEL = 30  # Tier 4 skills (levels 30-39) - specialization skills
    TIER5_MIN_LEVEL = 40  # Tier 5 skills (levels 40-49) - specialization skills
    TIER6_MIN_LEVEL = 50  # Tier 6 skills (levels 50-59) - specialization skills
    TIER7_MIN_LEVEL = 60  # Tier 7 skills (level 60) - specialization ultimate skills
    
    # Attributes
    ATTRIBUTE_AVERAGE = 10
    ATTRIBUTE_SKILL_MODIFIER_PER_POINT = 4
    
    @classmethod
    @abstractmethod
    def set_game_state(cls, game_state):
        """Set the game state for the skills system"""
        raise NotImplementedError
    
    @classmethod
    @abstractmethod
    async def start_casting(cls, actor, duration_ticks: int, cast_function: callable):
        """Start casting a skill with the given duration"""
        raise NotImplementedError
    
    @classmethod
    @abstractmethod
    def check_skill_roll(cls, skill_roll: int, actor, skill, difficulty_mod: int=0) -> int:
        """Check if a skill roll is successful, returns the result value"""
        raise NotImplementedError
    
    @classmethod
    @abstractmethod
    def does_resist(cls, actor, initiator_attribute: int, skill_level: int, target, 
                    target_attribute: int, difficulty_modifier: int) -> Tuple[bool, int]:
        """Check if a target resists a skill, returns (resisted, roll_value)"""
        raise NotImplementedError
    
    @classmethod
    @abstractmethod
    def check_ready(cls, actor, cooldown_name: str=None) -> Tuple[bool, str]:
        """Check if an actor is ready to use a skill, returns (ready, reason)"""
        raise NotImplementedError
    
    @classmethod
    def send_success_message(cls, actor, targets: list, skill_data: dict, vars: dict) -> None:
        """Send success messages for a skill to the appropriate targets"""
        pass
    
    @classmethod
    def send_failure_message(cls, actor, targets: list, skill_data: dict, vars: dict) -> None:
        """Send failure messages for a skill to the appropriate targets"""
        pass
    
    @classmethod
    def send_apply_message(cls, actor, targets: list, skill_data: dict, vars: dict) -> None:
        """Send apply effect messages for a skill to the appropriate targets"""
        pass
    
    @classmethod
    def send_resist_message(cls, actor, targets: list, skill_data: dict, vars: dict) -> None:
        """Send resist messages for a skill to the appropriate targets"""
        pass

    @classmethod
    def get_skill_name_list(cls) -> list[str]:
        """Get a list of all skill names (for all classes and specs)"""
        raise NotImplementedError
    
    @classmethod
    def invoke_skill(cls, actor: ActorInterface, input: str) -> None:
        """Invoke a skill by name"""
        raise NotImplementedError
   

class SkillsRegistryInterface(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def get_skill_name_list(cls) -> list[str]:
        """Get a list of all skill names (for all classes and specs)"""
        raise NotImplementedError

    @classmethod
    def parse_skill_name_from_input(cls, input: str) -> Tuple[Optional[str], str]:
        """Parse a skill name from input, returning the skill name and the remainder of the input"""
        raise NotImplementedError

    @classmethod
    def invoke_skill_by_name(cls, game_state: GameStateInterface, actor: ActorInterface, skill_name: str, skill_args: str, difficulty_modifier: int=0) -> bool:
        """Invoke a skill by name"""
        raise NotImplementedError