"""
Combat AI for NPC skill and ability usage.

This module provides AI decision-making for NPCs in combat, determining
what skills to use and when based on the situation.
"""

import random
from typing import Optional, List, Tuple, TYPE_CHECKING
from .structured_logger import StructuredLogger
from .skills_core import Skill, SkillAICondition, SkillType, SkillsRegistry
from .constants import CharacterClassRole
from .nondb_models.character_interface import TemporaryCharacterFlags, PermanentCharacterFlags

if TYPE_CHECKING:
    from .nondb_models.characters import Character


class CombatAI:
    """
    Handles combat decision-making for NPCs.
    
    Evaluates the combat situation and determines whether the NPC should
    use a skill or perform a basic attack.
    """
    
    # Chance to use a skill vs auto-attack when skills are available (0-100)
    BASE_SKILL_USE_CHANCE = 60
    
    # HP thresholds for healing priority
    CRITICAL_HP_THRESHOLD = 25
    LOW_HP_THRESHOLD = 50
    
    @classmethod
    def get_hp_percent(cls, character: 'Character') -> int:
        """Get character's HP as a percentage."""
        if character.max_hit_points <= 0:
            return 0
        return int((character.current_hit_points / character.max_hit_points) * 100)
    
    @classmethod
    def check_condition(cls, condition: str, actor: 'Character', target: 'Character' = None) -> bool:
        """
        Check if an AI condition is met.
        
        Args:
            condition: The condition string to evaluate
            actor: The NPC considering the skill
            target: The NPC's current target (if any)
            
        Returns:
            True if the condition is met, False otherwise
        """
        if condition == SkillAICondition.ALWAYS:
            return True
        
        actor_hp_pct = cls.get_hp_percent(actor)
        target_hp_pct = cls.get_hp_percent(target) if target else 0
        
        if condition == SkillAICondition.SELF_HP_BELOW_25:
            return actor_hp_pct < 25
        elif condition == SkillAICondition.SELF_HP_BELOW_50:
            return actor_hp_pct < 50
        elif condition == SkillAICondition.SELF_HP_ABOVE_75:
            return actor_hp_pct > 75
        elif condition == SkillAICondition.TARGET_HP_BELOW_25:
            return target and target_hp_pct < 25
        elif condition == SkillAICondition.TARGET_HP_BELOW_50:
            return target and target_hp_pct < 50
        elif condition == SkillAICondition.TARGET_NOT_STUNNED:
            return target and not target.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED)
        elif condition == SkillAICondition.IN_COMBAT:
            return actor.fighting_whom is not None
        elif condition == SkillAICondition.NOT_IN_COMBAT:
            return actor.fighting_whom is None
        
        return True  # Unknown conditions default to True
    
    @classmethod
    def can_use_skill(cls, actor: 'Character', skill: Skill, target: 'Character' = None) -> Tuple[bool, str]:
        """
        Check if an NPC can use a specific skill.
        
        Args:
            actor: The NPC
            skill: The skill to check
            target: The target for the skill
            
        Returns:
            Tuple of (can_use, reason_if_not)
        """
        # Check cooldown
        if skill.cooldown_name and actor.has_cooldown(skill.cooldown_name):
            return False, "on cooldown"
        
        # Check mana
        if skill.mana_cost > 0 and actor.current_mana < skill.mana_cost:
            return False, "not enough mana"
        
        # Check stamina
        if skill.stamina_cost > 0 and actor.current_stamina < skill.stamina_cost:
            return False, "not enough stamina"
        
        # Check if skill requires target
        if skill.requires_target and not target:
            return False, "no target"
        
        # Check AI condition
        if not cls.check_condition(skill.ai_condition, actor, target):
            return False, "condition not met"
        
        # Check if skill function exists
        if not skill.skill_function:
            return False, "skill not implemented"
        
        return True, ""
    
    @classmethod
    def get_available_skills(cls, actor: 'Character', target: 'Character' = None) -> List[Tuple[Skill, int]]:
        """
        Get all skills the NPC can currently use, with their effective priorities.
        
        Args:
            actor: The NPC
            target: The NPC's current target
            
        Returns:
            List of (skill, effective_priority) tuples, sorted by priority descending
        """
        available = []
        actor_hp_pct = cls.get_hp_percent(actor)
        
        # Get skills from all classes the NPC has
        for role, level in actor.levels_by_role.items():
            if level <= 0:
                continue
            
            # Get the class name for registry lookup
            class_name = role.name.lower()
            class_skills = SkillsRegistry.get_class_skills(class_name)
            
            for skill_name, skill in class_skills.items():
                can_use, reason = cls.can_use_skill(actor, skill, target)
                if not can_use:
                    continue
                
                # Calculate effective priority based on situation
                effective_priority = skill.ai_priority
                
                # Boost healing priority when low HP
                if skill.skill_type == SkillType.HEAL_SELF:
                    if actor_hp_pct < cls.CRITICAL_HP_THRESHOLD:
                        effective_priority += 50  # Major boost when critical
                    elif actor_hp_pct < cls.LOW_HP_THRESHOLD:
                        effective_priority += 25  # Moderate boost when low
                
                # Boost execute-type skills when target is low
                if target and skill.skill_type == SkillType.DAMAGE:
                    target_hp_pct = cls.get_hp_percent(target)
                    if target_hp_pct < 25:
                        effective_priority += 15
                
                # Boost stuns when target is not already stunned
                if skill.skill_type == SkillType.STUN:
                    if target and not target.has_temp_flags(TemporaryCharacterFlags.IS_STUNNED):
                        effective_priority += 20
                    else:
                        effective_priority -= 50  # Don't stun already stunned targets
                
                # Reduce stance priorities if already in that stance
                if skill.skill_type == SkillType.STANCE:
                    effective_priority -= 30  # Stances are lower priority in general combat
                
                available.append((skill, effective_priority))
        
        # Sort by effective priority (descending)
        available.sort(key=lambda x: x[1], reverse=True)
        return available
    
    @classmethod
    def choose_skill(cls, actor: 'Character', target: 'Character' = None) -> Optional[Skill]:
        """
        Choose a skill for the NPC to use this combat round.
        
        Uses weighted random selection based on skill priorities, with a chance
        to just auto-attack instead.
        
        Args:
            actor: The NPC
            target: The NPC's current target
            
        Returns:
            The skill to use, or None to auto-attack
        """
        logger = StructuredLogger(__name__, prefix="choose_skill()> ")
        
        available_skills = cls.get_available_skills(actor, target)
        
        if not available_skills:
            return None
        
        # Check if we should use a skill at all (vs auto-attack)
        # Higher level NPCs are smarter about skill usage
        total_level = sum(actor.levels_by_role.values())
        skill_use_chance = min(90, cls.BASE_SKILL_USE_CHANCE + total_level)
        
        if random.randint(1, 100) > skill_use_chance:
            logger.debug(f"{actor.name} choosing auto-attack over skill")
            return None
        
        # Weighted random selection from available skills
        # Higher priority skills are more likely to be chosen
        total_weight = sum(max(1, priority) for _, priority in available_skills)
        
        roll = random.randint(1, total_weight)
        cumulative = 0
        
        for skill, priority in available_skills:
            cumulative += max(1, priority)
            if roll <= cumulative:
                logger.debug(f"{actor.name} choosing skill: {skill.name} (priority {priority})")
                return skill
        
        # Fallback to highest priority
        return available_skills[0][0] if available_skills else None
    
    @classmethod
    def queue_combat_action(cls, actor: 'Character', target: 'Character') -> bool:
        """
        Queue a combat action for the NPC via the command handler.
        
        This routes NPC actions through the same command system as players,
        giving them command duration, queueing, and all standard behaviors.
        
        Args:
            actor: The NPC taking the turn
            target: The NPC's target
            
        Returns:
            True if a command was queued, False if auto-attack should proceed
        """
        logger = StructuredLogger(__name__, prefix="queue_combat_action()> ")
        
        # Only use AI for NPCs, not players
        if actor.has_perm_flags(PermanentCharacterFlags.IS_PC):
            return False
        
        # Check if NPC has any class levels
        total_levels = sum(actor.levels_by_role.values())
        if total_levels <= 0:
            return False  # No classes, just auto-attack
        
        # Choose a skill
        skill = cls.choose_skill(actor, target)
        
        if skill is None:
            return False  # Auto-attack
        
        # Build the command string
        # Skills are invoked by name, with target if needed
        if skill.requires_target and target:
            # Use target's name or a reference that the command handler can resolve
            command = f"{skill.name} {target.name}"
        else:
            command = skill.name
        
        logger.debug(f"NPC {actor.name} queueing command: {command}")
        
        # Queue the command - it will be processed by the main loop
        actor.command_queue.append(command)
        
        return True
