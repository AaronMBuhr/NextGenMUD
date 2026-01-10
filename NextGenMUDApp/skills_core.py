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
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageMultipliers, PotentialDamage
from .nondb_models.character_interface import CharacterAttributes, EquipLocation,\
    PermanentCharacterFlags, TemporaryCharacterFlags
from .utility import roll_dice, set_vars, seconds_from_ticks, ticks_from_seconds, firstcap
from .structured_logger import StructuredLogger


from typing import Any, Generic, TypeVar, Optional, List, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .nondb_models.characters import Character, CharacterSkill
# Import the interface and Skill class
from .skills_interface import SkillsInterface, SkillsRegistryInterface

# Skills Registry to hold all skills from all classes
class SkillsRegistry(SkillsRegistryInterface):
    _skills = {}
    _skills_by_name = {}
    _classes_registered = False
    
    @classmethod
    def register_skill_classes(cls):
        """Register all skill classes"""
        logger = StructuredLogger(__name__, prefix="register_skill_classes()> ")
        logger.info("Registering skill classes")
        if cls._classes_registered:
            logger.debug3("Skill classes already registered")
            return
            
        from .skills_fighter import Skills_Fighter
        from .skills_cleric import Skills_Cleric
        from .skills_mage import Skills_Mage
        from .skills_rogue import Skills_Rogue
        from .skills_universal import Skills_Universal
        
        cls._classes_registered = True
    
    @classmethod
    def register_skill_class(cls, class_name, skills_dict):
        """Register a set of skills for a class"""
        normalized_class = class_name.lower()
        cls._skills[normalized_class] = skills_dict
        for skill_name, skill_data in skills_dict.items():
            normalized_skill = skill_name.lower()
            cls._skills_by_name[normalized_skill] = skill_data
    
    @classmethod
    def get_skill(cls, class_name, skill_name):
        """Get a skill by class and name"""
        normalized_class = class_name.lower()
        normalized_skill = skill_name.lower()
        return cls._skills.get(normalized_class, {}).get(normalized_skill)
    
    @classmethod
    def get_class_skills(cls, class_name):
        """Get all skills for a class"""
        normalized_class = class_name.lower()
        return cls._skills.get(normalized_class, {})
    
    @classmethod
    def get_all_skills(cls):
        """Get the entire skills registry"""
        return cls._skills
    
    @classmethod
    def parse_skill_name_from_input(cls, input: str) -> Tuple[Optional[str], str]:
        """Parse a skill name from input, returning the skill name and the remainder of the input
        
        Returns:
            Tuple[Optional[str], str]: (skill_name, remainder) - skill_name will be None if no match found
        """
        logger = StructuredLogger(__name__, prefix="parse_skill_name_from_input()> ")
        logger.debug3(f"parse_skill_name_from_input() input: {input}")
        normalized_input = input.lower().strip()
        words = normalized_input.split()
        if not words:
            logger.debug3(f"no words found in input: {input}")
            return None, ""
            
        # If direct match, return it
        skill = cls._skills_by_name.get(normalized_input)
        logger.debug3(f"direct match: {skill}")
        if skill:
            return skill.name, ""
            
        logger.debug3(f"no direct match, trying partial match against {len(cls._skills_by_name)} skills")
        # Try partial matching
        matches = []
        for skill_name in cls._skills_by_name.keys():
            logger.debug3(f"checking skill: {skill_name}")
            # Try to match the beginning of the skill name with the input
            input_chars = list(normalized_input)
            skill_chars = list(skill_name)
            
            # Match character by character
            match_length = 0
            for i in range(min(len(input_chars), len(skill_chars))):
                if input_chars[i] == skill_chars[i]:
                    match_length += 1
                else:
                    break
            
            logger.debug3(f"match length: {match_length}")
            # If we matched at least 4 characters at the beginning
            if match_length >= 4:
                logger.debug3(f"Partial match found: {skill_name} ({match_length} characters matched)")
                matches.append((skill_name, match_length))
        
        # Find the longest unique match
        if matches:
            # Sort by match length (descending)
            matches.sort(key=lambda x: x[1], reverse=True)
            
            # If we have a unique longest match
            if len(matches) == 1 or matches[0][1] > matches[1][1]:
                logger.debug3(f"Unique match found: {matches[0][0]} ({matches[0][1]} characters matched)")
                matched_skill_name = matches[0][0]
                matched_skill = cls._skills_by_name.get(matched_skill_name)
                
                # Calculate the remainder - everything after the matched portion
                matched_portion = normalized_input[:matches[0][1]]
                logger.debug3(f"Matched portion: {matched_portion}")
                
                # If the matched portion ends with a space, or is the whole input
                if matches[0][1] >= len(normalized_input):
                    remainder = ""
                elif normalized_input[matches[0][1]:].strip() == "":
                    remainder = ""
                else:
                    # Skip any spaces after the matched portion
                    remainder_start = matches[0][1]
                    while remainder_start < len(normalized_input) and normalized_input[remainder_start].isspace():
                        remainder_start += 1
                    remainder = normalized_input[remainder_start:]
                logger.debug3(f"Remainder: {remainder}")
                return matched_skill.name, remainder
        
        return None, normalized_input
    
    @classmethod
    async def invoke_skill_by_name(cls, game_state: GameStateInterface, actor: Actor, skill_name: str, skill_args: str, difficulty_modifier: int=0) -> bool:
        """Invoke a skill by name, handling target resolution and async execution."""
        from .structured_logger import StructuredLogger
        logger = StructuredLogger(__name__, prefix="invoke_skill_by_name()> ")
        
        normalized_skill = skill_name.lower()
        skill = cls._skills_by_name.get(normalized_skill)
        if not skill:
            logger.debug(f"Skill not found: {skill_name}")
            return False
        
        # Resolve skill_function if it's a string reference
        skill_func = skill.skill_function
        if isinstance(skill_func, str):
            # Look up the method in the registered skill classes
            skill_func = cls._resolve_skill_function(skill_func, skill.base_class)
        
        if not skill_func:
            logger.debug(f"Skill {skill_name} has no function implementation")
            return False
        
        # Resolve target
        target = None
        if skill_args:
            target = game_state.find_target_character(actor, skill_args)
            if not target:
                target = game_state.find_target_object(skill_args)
        
        # If no target specified but skill requires one, default to fighting_whom
        if not target and skill.requires_target:
            if hasattr(actor, 'fighting_whom') and actor.fighting_whom:
                target = actor.fighting_whom
                logger.debug(f"Using fighting_whom as default target: {target.name}")
        
        # Check if skill requires target and we still don't have one
        if skill.requires_target and not target:
            from .communication import CommTypes
            await actor.send_text(CommTypes.DYNAMIC, f"Who do you want to use {skill.name} on?")
            return False
        
        try:
            # Get current tick for skill timing
            current_tick = game_state.world_clock_tick if hasattr(game_state, 'world_clock_tick') else 0
            
            # Call the skill function with proper parameters
            result = await skill_func(
                actor, 
                target, 
                difficulty_modifier=difficulty_modifier, 
                game_tick=current_tick,
                nowait=False
            )
            
            # Consume resources if skill succeeded
            if result and (skill.mana_cost > 0 or skill.stamina_cost > 0):
                await Skills.consume_resources(actor, skill)
            
            return result
        except Exception as e:
            logger.error(f"Error executing skill {skill_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    @classmethod
    def _resolve_skill_function(cls, func_name: str, base_class: 'CharacterClassRole') -> callable:
        """Resolve a string skill function name to the actual callable."""
        from .structured_logger import StructuredLogger
        logger = StructuredLogger(__name__, prefix="_resolve_skill_function()> ")
        
        # Map base_class to skill class
        class_map = {
            CharacterClassRole.FIGHTER: 'Skills_Fighter',
            CharacterClassRole.MAGE: 'Skills_Mage',
            CharacterClassRole.ROGUE: 'Skills_Rogue',
            CharacterClassRole.CLERIC: 'Skills_Cleric',
        }
        
        skill_class_name = class_map.get(base_class)
        if not skill_class_name:
            logger.error(f"Unknown base class: {base_class}")
            return None
        
        # Import the skill class dynamically
        try:
            if skill_class_name == 'Skills_Fighter':
                from .skills_fighter import Skills_Fighter
                skill_class = Skills_Fighter
            elif skill_class_name == 'Skills_Mage':
                from .skills_mage import Skills_Mage
                skill_class = Skills_Mage
            elif skill_class_name == 'Skills_Rogue':
                from .skills_rogue import Skills_Rogue
                skill_class = Skills_Rogue
            elif skill_class_name == 'Skills_Cleric':
                from .skills_cleric import Skills_Cleric
                skill_class = Skills_Cleric
            else:
                return None
            
            # Get the method from the class
            if hasattr(skill_class, func_name):
                return getattr(skill_class, func_name)
            else:
                logger.error(f"Method {func_name} not found on {skill_class_name}")
                return None
        except Exception as e:
            logger.error(f"Error resolving skill function {func_name}: {e}")
            return None

# Skill class definition with all properties
class SkillAICondition:
    """Conditions for when an NPC should consider using a skill."""
    ALWAYS = "always"                   # Always consider this skill
    SELF_HP_BELOW_25 = "self_hp<25"     # Self HP below 25%
    SELF_HP_BELOW_50 = "self_hp<50"     # Self HP below 50%
    SELF_HP_ABOVE_75 = "self_hp>75"     # Self HP above 75%
    TARGET_HP_BELOW_25 = "target_hp<25" # Target HP below 25%
    TARGET_HP_BELOW_50 = "target_hp<50" # Target HP below 50%
    TARGET_NOT_STUNNED = "target_not_stunned"
    IN_COMBAT = "in_combat"             # Must be in combat
    NOT_IN_COMBAT = "not_in_combat"     # Must NOT be in combat

class SkillType:
    """Classification of skill effects for AI decision making."""
    DAMAGE = "damage"           # Direct damage
    DOT = "dot"                 # Damage over time
    HEAL_SELF = "heal_self"     # Heals the caster
    HEAL_OTHER = "heal_other"   # Heals another
    BUFF_SELF = "buff_self"     # Buffs the caster
    BUFF_OTHER = "buff_other"   # Buffs another
    DEBUFF = "debuff"           # Debuffs enemy
    STUN = "stun"               # Stuns/incapacitates
    STANCE = "stance"           # Combat stance change
    UTILITY = "utility"         # Other effects


class Skill:
    def __init__(self, 
                 name: str, 
                 base_class: 'CharacterClassRole', 
                 cooldown_name: Optional[str] = None,
                 cooldown_ticks: int = 0,
                 cast_time_ticks: int = 0,
                 duration_min_ticks: int = 0,
                 duration_max_ticks: int = 0,
                 mana_cost: int = 0,
                 stamina_cost: int = 0,
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
                 message_resist_room: Optional[str] = None,
                 skill_function: Optional[callable] = None,
                 # AI properties for NPC skill usage
                 ai_priority: int = 50,
                 ai_condition: str = SkillAICondition.ALWAYS,
                 skill_type: str = SkillType.DAMAGE,
                 requires_target: bool = True):
        self.name = name
        self.base_class = base_class
        self.cooldown_name = cooldown_name
        self.cooldown_ticks = cooldown_ticks
        self.cast_time_ticks = cast_time_ticks
        self.duration_min_ticks = duration_min_ticks
        self.duration_max_ticks = duration_max_ticks
        self.mana_cost = mana_cost
        self.stamina_cost = stamina_cost
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
        self.skill_function = skill_function
        # AI properties
        self.ai_priority = ai_priority          # Higher = more likely to use (0-100)
        self.ai_condition = ai_condition        # When to consider using
        self.skill_type = skill_type            # What type of effect
        self.requires_target = requires_target  # Needs a target to use


class ClassSkills(GenericEnumWithAttributes):
    # NOTE: Do not add any members here - an enum with members cannot be subclassed
    # Skill subclasses (Skills_Fighter, Skills_Mage, etc.) will define their own members
    
    @abstractmethod
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        pass
        
    def __init_subclass__(cls, **kwargs):
        """Automatically register skills when a subclass is defined"""
        super().__init_subclass__(**kwargs)
        
        logger = StructuredLogger(__name__, prefix="init_subclass()> ")
        logger.debug3(f"Initializing subclass: {cls.__name__}")
        
        # Collect all Skill instances from class attributes first
        # Since this is an enum, attributes are enum members - we need to check their values
        skills_dict = {}
        class_role = None
        for attr_name in dir(cls):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(cls, attr_name)
                # Check if it's an enum member with a Skill value
                if hasattr(attr, 'value') and isinstance(attr.value, Skill):
                    skill = attr.value
                    skill_name = skill.name.lower()
                    skills_dict[skill_name] = skill
                    # Extract class role from the skill's base_class if available
                    if class_role is None and skill.base_class is not None:
                        class_role = skill.base_class.name.lower()
                # Also check direct Skill instances (for non-enum cases)
                elif isinstance(attr, Skill):
                    skill_name = attr.name.lower()
                    skills_dict[skill_name] = attr
                    # Extract class role from the skill's base_class if available
                    if class_role is None and attr.base_class is not None:
                        class_role = attr.base_class.name.lower()
            except Exception:
                pass  # Skip attributes that can't be accessed
        
        # Fallback: Get the class role name from the class name if we couldn't determine it from skills
        # Handle patterns like: Skills_Fighter -> fighter, MageSkills -> mage, ClericSkills -> cleric
        if class_role is None:
            class_name = cls.__name__.lower()
            if class_name.startswith("skills_"):
                class_role = class_name.replace("skills_", "")
            elif class_name.endswith("skills"):
                class_role = class_name.replace("skills", "")
            else:
                class_role = class_name
        
        # Register with the central registry
        if skills_dict:
            SkillsRegistry.register_skill_class(class_role, skills_dict)
            logger.info(f"Registered {len(skills_dict)} skills for {class_role}")


class Skills(SkillsInterface):

    _game_state = None
    _initialized = False

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
    
    # Skill cap progression constants
    SKILL_CAP_BASE = 25  # Starting cap when skill becomes available
    SKILL_CAP_MAX = 100  # Maximum skill level
    SKILL_CAP_LEVELS_TO_MAX = 10  # Number of levels to go from base to max
    SKILL_CAP_PER_LEVEL = 7.5  # (100 - 25) / 10 = 7.5 points per level
    
    @classmethod
    def calculate_skill_cap(cls, character_level: int, skill_requirement_level: int, 
                           override_cap: int = None) -> int:
        """
        Calculate the maximum skill level a character can train a skill to.
        
        The formula creates a progression where:
        - Level 1 skills (treated as level 0): max 32 at level 1, max 100 at level 10
        - Level 10 skills: max 25 at level 10, max 100 at level 20
        - Level 20 skills: max 25 at level 20, max 100 at level 30
        - Level 30 skills: max 25 at level 30, max 100 at level 40
        - etc.
        
        Args:
            character_level: The character's current level
            skill_requirement_level: The level requirement to unlock the skill
            override_cap: Optional YAML-defined cap override (if set, returns this value)
            
        Returns:
            The maximum skill level the character can train to (0-100)
        """
        # YAML override takes precedence
        if override_cap is not None:
            return min(override_cap, cls.SKILL_CAP_MAX)
        
        # Level 1 skills are treated as level 0 for calculation purposes
        effective_requirement = 0 if skill_requirement_level <= 1 else skill_requirement_level
        
        # Character must meet the actual requirement to have the skill at all
        if character_level < skill_requirement_level:
            return 0
        
        # Calculate levels of progress beyond the requirement
        levels_beyond = character_level - effective_requirement
        
        # Calculate cap: 25 base + 7.5 per level beyond requirement
        cap = cls.SKILL_CAP_BASE + (levels_beyond * cls.SKILL_CAP_PER_LEVEL)
        
        # Clamp to max
        return min(int(cap), cls.SKILL_CAP_MAX)
    
    @classmethod
    def _get_game_state(cls):
        """Get the game state instance, lazily initializing if needed"""
        if cls._game_state is None:
            cls._game_state = GameStateInterface.get_instance()
            if not cls._initialized:
                SkillsRegistry.register_skill_classes()
                cls._initialized = True
        return cls._game_state
       
    @classmethod
    async def start_casting(cls, actor: Actor, duration_ticks: int, cast_function: callable):
        game_tick = cls._get_game_state().get_current_tick()
        new_state = CharacterStateCasting(actor, cls._get_game_state(), actor, "casting", tick_created=game_tick, casting_finish_func=cast_function)
        new_state.apply_state(game_tick, duration_ticks)
        return True

    @classmethod
    def check_skill_roll(cls, skill_roll: int, actor: Actor, skill: 'CharacterSkill', difficulty_mod: int=0) -> int:
        return skill_roll - skill.skill_level - difficulty_mod
    
    @classmethod
    def do_skill_check(cls, actor: Actor, skill: 'CharacterSkill', difficulty_mod: int=0) -> bool:
        """
        Perform a skill check by rolling 1-100 and comparing against skill level.
        Returns True if the check succeeds (roll >= skill_level + difficulty_mod).
        """
        skill_roll = random.randint(1, 100)
        result = cls.check_skill_roll(skill_roll, actor, skill, difficulty_mod)
        return result >= 0 
    
    @classmethod
    def does_resist(cls, actor: Actor, initiator_attribute: int, skill_level: int, target: Actor, 
                    target_attribute: int, difficulty_modifier: int) -> Tuple[bool, int]:
        """
        Calculate success chance for a skill check against resistance.
        
        Spell power from caster levels makes spells harder to resist.
        Higher level casters overcome resistance better than lower level ones.
        
        Parameters:
        - actor: The character using the skill/spell
        - initiator_attribute: Relevant attribute score for skill user (1-20)
        - skill_level: Proficiency in the skill (1-100)
        - target: The character resisting
        - target_attribute: Relevant attribute score for target (1-20)
        - difficulty_modifier: Situational modifier (-20 to +20)
        
        Returns:
        - success: Boolean indicating if the target RESISTED (True = resisted, False = affected)
        - margin: How much the check succeeded or failed by
        """
        # Get spell power from caster (level-based bonus for Mage/Cleric)
        spell_power = getattr(actor, 'spell_power', 0)
        
        # Base success value from initiator (higher = more likely to overcome resistance)
        # Spell power directly adds to the caster's effectiveness
        initiator_base = (skill_level * 0.6) + (initiator_attribute * 3) + (actor.level * 0.5) + (spell_power * 0.8)
        
        # Base resistance value from target (higher = harder to affect)
        target_base = (target_attribute * 4) + (target.level * 0.8) + (difficulty_modifier * 1.5)
        
        # Random element (1-100)
        random_roll = random.randint(1, 100)
        
        # Calculate success threshold (higher means harder to overcome resistance)
        # If initiator_base > target_base, threshold drops (easier to affect target)
        success_threshold = 50 + (target_base - initiator_base) * 0.5
        
        # Ensure threshold stays within reasonable bounds (5-95)
        success_threshold = max(5, min(95, success_threshold))
        
        # Calculate margin of success/failure
        margin = random_roll - success_threshold
        
        # Determine if target resisted (roll >= threshold means caster succeeded, target failed to resist)
        resisted = random_roll < success_threshold
        return resisted, margin    
    
    @classmethod
    def check_ready(cls, actor: Actor, cooldown_name: str=None, skill: Skill=None) -> Tuple[bool, str]:
        can_act, msg = actor.can_act()
        if not can_act:
            return False, msg
        if cooldown_name and actor.has_cooldown(cooldown_name):
            return False, "You can't use that skill again yet!"
        
        # Check resource costs if skill provided
        if skill:
            if skill.mana_cost > 0 and actor.current_mana < skill.mana_cost:
                return False, f"You don't have enough mana! (need {skill.mana_cost}, have {int(actor.current_mana)})"
            if skill.stamina_cost > 0 and actor.current_stamina < skill.stamina_cost:
                return False, f"You don't have enough stamina! (need {skill.stamina_cost}, have {int(actor.current_stamina)})"
        
        return True, ""
    
    @classmethod
    async def consume_resources(cls, actor: Actor, skill: Skill) -> None:
        """Consume mana/stamina for using a skill. Call this after skill succeeds."""
        from .nondb_models.character_interface import PermanentCharacterFlags
        changed = False
        if skill.mana_cost > 0:
            actor.use_mana(skill.mana_cost)
            changed = True
        if skill.stamina_cost > 0:
            actor.use_stamina(skill.stamina_cost)
            changed = True
        # Send status update if resources were consumed and actor is a PC
        if changed and actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await actor.send_status_update()

    @classmethod
    def send_success_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_success_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_success_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_success_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state(), exceptions=targets)
        
    @classmethod
    def send_failure_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_failure_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_failure_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_failure_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state(), exceptions=targets)

    @classmethod
    def send_apply_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_apply_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_apply_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_apply_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state(), exceptions=targets)
        
    @classmethod
    def send_resist_message(cls, actor: Actor, targets: List[Actor], skill_data: dict, vars: dict) -> None:
        msg = skill_data["message_resist_subject"]
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_resist_target"]
        if msg and targets and len(targets) > 0:
            for target in targets:
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state())
        msg = skill_data["message_resist_room"]
        if msg:
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls._get_game_state(), exceptions=targets)
