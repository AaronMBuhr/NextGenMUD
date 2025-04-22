from enum import Enum
import random
from .basic_types import DescriptiveFlags
from .communication import CommTypes
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
from .skills_interface import SkillsInterface, FighterSkills, RogueSkills, MageSkills, ClericSkills
from .utility import roll_dice, set_vars, seconds_from_ticks, ticks_from_seconds, firstcap

class Skills(SkillsInterface):

    game_state: 'ComprehensiveGameState' = None

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

    # Base class skill requirements - these are available without specialization
    SKILL_LEVEL_REQUIREMENTS = {
        # Fighter base skills (Tiers 1-2)
        CharacterClassRole.FIGHTER: {
            # Tier 1 (Levels 1-9)
            FighterSkills.NORMAL_STANCE: TIER1_MIN_LEVEL,
            FighterSkills.SHIELD_BASH: TIER1_MIN_LEVEL,
            FighterSkills.HEROIC_STRIKE: TIER1_MIN_LEVEL,
            FighterSkills.TAUNT: TIER1_MIN_LEVEL,
            FighterSkills.CHARGE: TIER1_MIN_LEVEL,
            
            # Tier 2 (Levels 10-19)
            FighterSkills.DUAL_WIELD: TIER2_MIN_LEVEL,
            FighterSkills.DEFENSIVE_STANCE: TIER2_MIN_LEVEL,
            FighterSkills.BATTLE_SHOUT: TIER2_MIN_LEVEL,
            FighterSkills.SECOND_WIND: TIER2_MIN_LEVEL,
            FighterSkills.DISARM: TIER2_MIN_LEVEL
        },
        
        # Rogue base skills (Tiers 1-2)
        CharacterClassRole.ROGUE: {
            # Tier 1 (Levels 1-9)
            RogueSkills.STEALTH: TIER1_MIN_LEVEL,
            RogueSkills.BACKSTAB: TIER1_MIN_LEVEL,
            RogueSkills.PICK_LOCK: TIER1_MIN_LEVEL,
            RogueSkills.DETECT_TRAPS: TIER1_MIN_LEVEL,
            RogueSkills.EVADE: TIER1_MIN_LEVEL,
            
            # Tier 2 (Levels 10-19)
            RogueSkills.DUAL_WIELD: TIER2_MIN_LEVEL,
            RogueSkills.POISONED_WEAPON: TIER2_MIN_LEVEL,
            RogueSkills.DISARM_TRAP: TIER2_MIN_LEVEL,
            RogueSkills.ACROBATICS: TIER2_MIN_LEVEL,
            RogueSkills.FEINT: TIER2_MIN_LEVEL
        },
        
        # Mage base skills (Tiers 1-2)
        CharacterClassRole.MAGE: {
            # Tier 1 (Levels 1-9)
            MageSkills.MAGIC_MISSILE: TIER1_MIN_LEVEL,
            MageSkills.ARCANE_BARRIER: TIER1_MIN_LEVEL,
            MageSkills.BURNING_HANDS: TIER1_MIN_LEVEL,
            MageSkills.MANA_SHIELD: TIER1_MIN_LEVEL,
            MageSkills.DISPEL_MAGIC: TIER1_MIN_LEVEL,
            
            # Tier 2 (Levels 10-19)
            MageSkills.DETECT_MAGIC: TIER2_MIN_LEVEL,
            MageSkills.IDENTIFY: TIER2_MIN_LEVEL,
            MageSkills.ARCANE_INTELLECT: TIER2_MIN_LEVEL,
            MageSkills.BLINK: TIER2_MIN_LEVEL,
            MageSkills.FROST_NOVA: TIER2_MIN_LEVEL
        },
        
        # Cleric base skills (Tiers 1-2)
        CharacterClassRole.CLERIC: {
            # Tier 1 (Levels 1-9)
            ClericSkills.CURE_LIGHT_WOUNDS: TIER1_MIN_LEVEL,
            ClericSkills.BLESS: TIER1_MIN_LEVEL,
            ClericSkills.DIVINE_FAVOR: TIER1_MIN_LEVEL,
            ClericSkills.RADIANT_LIGHT: TIER1_MIN_LEVEL,
            ClericSkills.SANCTUARY: TIER1_MIN_LEVEL,
            
            # Tier 2 (Levels 10-19)
            ClericSkills.CURE_MODERATE_WOUNDS: TIER2_MIN_LEVEL,
            ClericSkills.REMOVE_CURSE: TIER2_MIN_LEVEL,
            ClericSkills.DIVINE_PROTECTION: TIER2_MIN_LEVEL,
            ClericSkills.SMITE: TIER2_MIN_LEVEL,
            ClericSkills.DIVINE_GUIDANCE: TIER2_MIN_LEVEL
        },
        
        # Fighter specialization: Berserker (Tiers 3-7)
        CharacterClassRole.BERSERKER: {
            # Tier 3 (Levels 20-29)
            FighterSkills.BERSERKER_STANCE: TIER3_MIN_LEVEL,
            FighterSkills.RAGE: TIER3_MIN_LEVEL,
            FighterSkills.CLEAVE: TIER3_MIN_LEVEL,
            FighterSkills.BLOODTHIRST: TIER3_MIN_LEVEL,
            FighterSkills.INTIMIDATE: TIER3_MIN_LEVEL,
            
            # Tier 4 (Levels 30-39)
            FighterSkills.WHIRLWIND: TIER4_MIN_LEVEL,
            FighterSkills.RAMPAGE: TIER4_MIN_LEVEL,
            FighterSkills.EXECUTE: TIER4_MIN_LEVEL,
            FighterSkills.DEATHWISH: TIER4_MIN_LEVEL,
            FighterSkills.ENRAGE: TIER4_MIN_LEVEL,
            
            # Tier 5 (Levels 40-49)
            FighterSkills.UNSTOPPABLE: TIER5_MIN_LEVEL,
            FighterSkills.BLOODBATH: TIER5_MIN_LEVEL,
            FighterSkills.RECKLESSNESS: TIER5_MIN_LEVEL,
            FighterSkills.BRUTAL_STRIKE: TIER5_MIN_LEVEL,
            FighterSkills.DEATH_WISH: TIER5_MIN_LEVEL,
            
            # Tier 6 (Levels 50-59)
            FighterSkills.BERSERKER_FURY: TIER6_MIN_LEVEL,
            FighterSkills.TITANS_GRIP: TIER6_MIN_LEVEL,
            FighterSkills.MEAT_CLEAVER: TIER6_MIN_LEVEL,
            FighterSkills.BLOOD_FRENZY: TIER6_MIN_LEVEL,
            FighterSkills.MASSACRE: TIER6_MIN_LEVEL,
            
            # Tier 7 (Level 60)
            FighterSkills.AVATAR: TIER7_MIN_LEVEL
        },
        
        # The rest of the specializations will be added similarly
    }

    @classmethod
    def set_game_state(cls, game_state: 'ComprehensiveGameState'):
        cls.game_state = game_state
        
    @classmethod
    async def start_casting(cls, actor: Actor, skill: CharacterSkill, duration_ticks: int, cast_function: callable):
        game_tick = cls.game_state.current_tick
        new_state = CharacterStateCasting(actor, cls.game_state, actor, "casting", tick_created=game_tick, cast_function=cast_function)
        new_state.apply_state(game_tick, duration_ticks)
        return True

    @classmethod
    def do_skill_check(cls, actor: Actor, skill: CharacterSkill, difficulty_mod: int=0, args: dict=None):
        skill_roll = random.randint(1, 100)
        return skill_roll < skill.skill_level - difficulty_mod 
    
    @classmethod
    def is_state_actable(cls, actor: Actor):
        if actor.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            msg = f"You can't do that while you're sitting!"
            vars = set_vars(actor, actor, actor, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        elif actor.has_state(CharacterStateStunned):
            msg = f"You can't do that while you're stunned!"
            vars = set_vars(actor, actor, actor, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        elif actor.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            msg = f"You can't do that while you're asleep!"
            vars = set_vars(actor, actor, actor, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        else:
            return True
