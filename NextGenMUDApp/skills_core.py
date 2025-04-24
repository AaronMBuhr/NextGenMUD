from enum import Enum
import random
from abc import abstractmethod
from .basic_types import DescriptiveFlags, GenericEnumWithAttributes
from .communication import CommTypes
from .comprehensive_game_state_interface import GameStateInterface
from .constants import CharacterClassRole, Constants
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actor_states import Cooldown, CharacterStateForcedSitting, CharacterStateHitPenalty, \
    CharacterStateStealthed, CharacterStateStunned, CharacterStateBleeding, CharacterStateHitBonus, \
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus, CharacterStateBerserkerStance, CharacterStateCasting
from .nondb_models.actors import Actor
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances, PotentialDamage
from .nondb_models.character_interface import CharacterAttributes, EquipLocation,\
    PermanentCharacterFlags, TemporaryCharacterFlags
from .nondb_models.characters import Character, CharacterSkill
from .utility import roll_dice, set_vars, seconds_from_ticks, ticks_from_seconds, firstcap


from typing import Any, Generic, TypeVar, Optional, List, Tuple, Dict
# Import the interface and Skill class
from .skills_interface import SkillsInterface

# Skill class definition with all properties
class Skill:
    def __init__(self, 
                 name: str, 
                 base_class: 'CharacterClassRole', 
                 cooldown_name: Optional[str] = None,
                 cooldown_ticks: int = 0,
                 cast_time_ticks: int = 0,
                 duration_min_ticks: int = 0,
                 duration_max_ticks: int = 0,
                 message_prepare: Optional[str] = None,
                 message_success_subject: Optional[str] = None,
                 message_success_target: Optional[str] = None,
                 message_success_room: Optional[str] = None,
                 message_failure_subject: Optional[str] = None,
                 message_failure_target: Optional[str] = None,
                 message_failure_room: Optional[str] = None,
                 message_apply_subject: Optional[str] = None,
                 message_apply_target: Optional[str] = None,
                 message_apply_room: Optional[str] = None,
                 message_resist_subject: Optional[str] = None,
                 message_resist_target: Optional[str] = None,
                 message_resist_room: Optional[str] = None):
        self.name = name
        self.base_class = base_class
        self.cooldown_name = cooldown_name
        self.cooldown_ticks = cooldown_ticks
        self.cast_time_ticks = cast_time_ticks
        self.duration_min_ticks = duration_min_ticks
        self.duration_max_ticks = duration_max_ticks
        self.message_prepare = message_prepare
        self.message_success_subject = message_success_subject
        self.message_success_target = message_success_target
        self.message_success_room = message_success_room
        self.message_failure_subject = message_failure_subject
        self.message_failure_target = message_failure_target
        self.message_failure_room = message_failure_room
        self.message_apply_subject = message_apply_subject
        self.message_apply_target = message_apply_target
        self.message_apply_room = message_apply_room
        self.message_resist_subject = message_resist_subject
        self.message_resist_target = message_resist_target
        self.message_resist_room = message_resist_room




class ClassSkills(GenericEnumWithAttributes):
    # Add a dummy member with a valid Skill instance to make the enum valid
    BASE_SKILL = Skill(
        name="base skill",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name=None,
        cooldown_ticks=0,
        cast_time_ticks=0,
        duration_min_ticks=0,
        duration_max_ticks=0
    )
    
    @abstractmethod
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        pass

# class RogueSkills(ClassSkills):
#     pass

# class MageSkills(ClassSkills):
#     pass

# class ClericSkills(ClassSkills):
#     pass



class Skills(SkillsInterface):

    game_state: GameStateInterface = None

    ATTRIBUTE_AVERAGE = 10
    ATTRIBUTE_SKILL_MODIFIER_PER_POINT = 4

    # Tier 1 skills (levels 1-9)
    TIER1_MIN_LEVEL = 1

    # Tier 2 skills (levels 10-19)
    TIER2_MIN_LEVEL = 10

    # Tier 3 skills (levels 20-29) - specialization skills
    TIER3_MIN_LEVEL = 20

    # Tier 4 skills (levels 30-39) - specialization skills
    TIER4_MIN_LEVEL = 30

    # Tier 5 skills (levels 40-49) - specialization skills
    TIER5_MIN_LEVEL = 40

    # Tier 6 skills (levels 50-59) - specialization skills
    TIER6_MIN_LEVEL = 50

    # Tier 7 skills (level 60) - specialization ultimate skills
    TIER7_MIN_LEVEL = 60

   
    @classmethod
    def set_game_state(cls, game_state: GameStateInterface):
        cls.game_state = game_state
        
    @classmethod
    async def start_casting(cls, actor: Actor, duration_ticks: int, cast_function: callable):
        game_tick = cls.game_state.current_tick
        new_state = CharacterStateCasting(actor, cls.game_state, actor, "casting", tick_created=game_tick, cast_function=cast_function)
        new_state.apply_state(game_tick, duration_ticks)
        return True

    @classmethod
    def check_skill_roll(cls, skill_roll: int, actor: Actor, skill: CharacterSkill, difficulty_mod: int=0) -> int:
        return skill_roll - skill.skill_level - difficulty_mod 
    
    @classmethod
    def does_resist(cls, actor: Actor, initiator_attribute: int, skill_level: int, target: Actor, 
                    target_attribute: int, difficulty_modifier: int) -> Tuple[bool, int]:
        """
        Calculate success chance for a skill check against resistance.
        
        Parameters:
        - initiator_level: Level of character using skill (1-60)
        - initiator_attribute: Relevant attribute score for skill user (1-20)
        - skill_level: Proficiency in the skill (1-100)
        - target_level: Level of the target resisting (1-60)
        - target_attribute: Relevant attribute score for target (1-20)
        - difficulty_modifier: Situational modifier (-20 to +20)
        
        Returns:
        - success: Boolean indicating success or failure
        - margin: How much the check succeeded or failed by
        """
        # Base success value from initiator
        initiator_base = (skill_level * 0.6) + (initiator_attribute * 3) + (actor.level * 0.5)
        # Base resistance value from target
        target_base = (target_attribute * 4) + (target.level * 0.8) + (difficulty_modifier * 1.5)
        # Random element (1-100)
        random_roll = random.randint(1, 100)
        # Calculate success threshold (higher means harder)
        success_threshold = 50 + (target_base - initiator_base) * 0.5
        # Ensure threshold stays within reasonable bounds (5-95)
        success_threshold = max(5, min(95, success_threshold))
        # Calculate margin of success/failure
        margin = random_roll - success_threshold
        # Determine if successful
        success = random_roll >= success_threshold
        return success, margin    
    
    @classmethod
    def check_ready(cls, actor: Actor, cooldown_name: str=None) -> Tuple[bool, str]:
        can_act, msg = actor.can_act()
        if not can_act:
            return False, msg
        if cooldown_name and actor.has_cooldown(cooldown_name):
            return False, "You can't use that skill again yet!"
        
        return True, ""

    @classmethod
    def send_success_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_success_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_success_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_success_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state, exceptions=targets)
        
    @classmethod
    def send_failure_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_failure_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_failure_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_failure_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state, exceptions=targets)

    @classmethod
    def send_apply_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_apply_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_apply_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_apply_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state, exceptions=targets)
        
    @classmethod
    def send_resist_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_resist_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_resist_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = skill_data["message_resist_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state, exceptions=targets)
