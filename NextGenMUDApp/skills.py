from enum import Enum
import random
from .basic_types import DescriptiveFlags
from .communication import CommTypes
from .constants import CharacterClassRole
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actor_states import Cooldown, CharacterStateForcedSitting, CharacterStateHitPenalty, \
    CharacterStateStealthed, CharacterStateStunned, CharacterStateBleeding, CharacterStateHitBonus, \
    CharacterStateDodgeBonus
from .nondb_models.actors import Actor
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances, PotentialDamage
from .nondb_models.character_interface import CharacterAttributes, EquipLocation,\
    PermanentCharacterFlags, TemporaryCharacterFlags
from .nondb_models.characters import Character, CharacterSkill
from .utility import roll_dice, set_vars, seconds_from_ticks, ticks_from_seconds, firstcap



class FighterSkills(Enum):
    MIGHTY_KICK = 1
    DEMORALIZING_SHOUT = 2
    INTIMIDATE = 3
    DISARM = 4
    SLAM = 5
    RALLY = 6
    REND = 7

    def __str__(self):
        return self.name.replace("_", " ").title()

class MageSkills(Enum):
    CAST_FIREBALL = 1
    CAST_MAGIC_MISSILE = 2
    CAST_LIGHT = 3
    CAST_SHIELD = 4
    CAST_SLEEP = 5
    CAST_CHARM = 6
    CAST_RESIST_MAGIC = 7

    def __str__(self):
        return self.name[5:].replace("_", " ").title()

class RogueSkills(Enum):
    BACKSTAB = 1
    STEALTH = 2
    EVADE = 3
    PICKPOCKET = 4
    SAP = 5

    def __str__(self):
        return self.name.replace("_", " ").title()

class ClericSkills(Enum):
    CURE_LIGHT_WOUNDS = 1
    CURE_SERIOUS_WOUNDS = 2
    CURE_CRITICAL_WOUNDS = 3
    HEAL = 4
    ANIMATE_DEAD = 5
    SMITE = 6
    BLESS = 7
    AEGIS = 8
    SANCTUARY = 9

    def __str__(self):
        return self.name.replace("_", " ").title()

class Skills:

    game_state: 'ComprehensiveGameState' = None

    ATTRIBUTE_AVERAGE = 10
    ATTRIBUTE_SKILL_MODIFIER_PER_POINT = 4

    SKILL_LEVEL_REQUIREMENTS = {
        CharacterClassRole.FIGHTER: {
            FighterSkills.MIGHTY_KICK: 1,
            FighterSkills.DEMORALIZING_SHOUT: 1,
            FighterSkills.INTIMIDATE: 1,
            FighterSkills.DISARM: 1,
            FighterSkills.SLAM: 1,
            FighterSkills.RALLY: 1,
            FighterSkills.REND: 1
        },
        CharacterClassRole.ROGUE: {

            RogueSkills.BACKSTAB: 1,
            RogueSkills.STEALTH: 1,
            RogueSkills.EVADE: 1,
            RogueSkills.PICKPOCKET: 1,
        },
        CharacterClassRole.MAGE: {
            MageSkills.CAST_FIREBALL: 1,
            MageSkills.CAST_MAGIC_MISSILE: 1,
            MageSkills.CAST_LIGHT: 1,
            MageSkills.CAST_SHIELD: 1,
            MageSkills.CAST_SLEEP: 1
        },
        CharacterClassRole.CLERIC: {
            ClericSkills.CURE_LIGHT_WOUNDS: 1,
            ClericSkills.CURE_SERIOUS_WOUNDS: 1,
            ClericSkills.CURE_CRITICAL_WOUNDS: 1,
            ClericSkills.HEAL: 1
        }
    }

    @classmethod
    def set_game_state(cls, game_state: 'ComprehensiveGameState'):
        cls.game_state = game_state

    @classmethod
    def do_skill_check(cls, actor: Actor, skill: CharacterSkill, difficulty_mod: int=0, args: dict=None):
        skill_roll = random.randint(1, 100)
        return skill_roll < skill.skill_level - difficulty_mod

    @classmethod
    async def do_fighter_mighty_kick(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        KICK_DURATION_MIN = ticks_from_seconds(3)
        KICK_DURATION_MAX = ticks_from_seconds(6)
        kick_duration = random.randint(KICK_DURATION_MIN, KICK_DURATION_MAX) \
            * actor.levels[CharacterClassRole.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_, target.dodge_dice_modifier_)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.MIGHTY_KICK],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "kicked", tick_created=game_tick)
            new_state.apply_state(game_tick, kick_duration)
            msg = f"You kick {target.art_name} to the ground!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} kicks you to the ground!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} kicks %t% to the ground!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to kick {target.art_name}, but %r% dodges!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to kick you, but you dodge!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to kick {target.art_name}, but {target.pronoun_subject} dodges!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False


    @classmethod
    async def do_fighter_demoralizing_shout(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                            difficulty_modifier=0, game_tick=0) -> bool:
        DEMORALIZING_SHOUT_DURATION_MIN = ticks_from_seconds(6)
        DEMORALIZING_SHOUT_DURATION_MAX = ticks_from_seconds(12)
        DEMORALIZING_SHOUT_HIT_PENALTY_MIN = 10
        DEMORALIZING_SHOUT_HIT_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DEMORALIZING_SHOUT_DURATION_MIN, DEMORALIZING_SHOUT_DURATION_MAX) * level_mult
        hit_penalty = random.randint(DEMORALIZING_SHOUT_HIT_PENALTY_MIN, DEMORALIZING_SHOUT_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.DEMORALIZING_SHOUT],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "demoralized", hit_penalty, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You shout at {target.art_name}, demoralizing {target.pronoun_object}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name} shouts at you, demoralizing you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name} shouts at {target.art_name}, demoralizing {target.pronoun_object}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to shout at {target.art_name}, but {target.pronoun_object} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to shout at you, but you resist!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to shout at {target.art_name}, but {target.pronoun_subject} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False


    @classmethod
    async def do_fighter_intimidate(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        INTIMIDATE_DURATION_MIN = ticks_from_seconds(6)
        INTIMIDATE_DURATION_MIN = ticks_from_seconds(12)
        INTIMIDATE_DODGE_PENALTY_MIN = 10
        INTIMIDATE_DODGE_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(INTIMIDATE_DURATION_MIN, INTIMIDATE_DURATION_MIN) * level_mult
        dodge_penalty = random.randint(INTIMIDATE_DODGE_PENALTY_MIN, INTIMIDATE_DODGE_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.INTIMIDATE],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "intimidated", dodge_penalty, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You intimidate {target.art_name}, making {target.pronoun_possessive} attacks less accurate!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"{actor.art_name_cap} intimidates you, making your attacks less accurate!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            target.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"{actor.art_name_cap} intimidates {target.art_name}, making {target.pronoun_possessive} attacks less accurate!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        else:
            msg = f"You try to intimidate {target.art_name}, but {actor.pronoun_subject} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = "{actor.art_name_cap} tries to intimidate you, but you resist!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = "{actor.art_name_cap} tries to intimidate {target.art_name}, but {target.pronoun_subject_} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            return False
        

    @classmethod
    async def do_fighter_disarm(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                difficulty_modifier=0, game_tick=0) -> bool:
        DISARM_DURATION_MIN = ticks_from_seconds(3)
        DISARM_DURATION_MAX = ticks_from_seconds(6)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DISARM_DURATION_MIN, DISARM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.DISARM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "disarmed", tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You disarm {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} disarms you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} disarms {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True

    @classmethod
    async def do_fighter_slam(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0) -> bool:
        SLAM_DURATION_MIN = ticks_from_seconds(1)
        SLAM_DURATION_MAX = ticks_from_seconds(4)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(SLAM_DURATION_MIN, SLAM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.SLAM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateStunned(target, actor, "slammed", tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You slam {target.art_name}, making {target.pronoun_object} easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} intimidates you, making you easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} intimidates {target.art_name}, making {target.pronoun_object} easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to intimidate {target.art_name}, but {target.pronoun_subject} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to intimidate you, but you resist!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to intimidate %t%, but %t%s resists!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False

    
    @classmethod
    async def do_fighter_rally(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                            difficulty_modifier=0, game_tick=0) -> bool:
        RALLY_DURATION_MIN = ticks_from_seconds(6)
        RALLY_DURATION_MAX = ticks_from_seconds(12)
        RALLY_HIT_BONUS_MIN = 4
        RALLY_HIT_BONUS_MAX = 8
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 4
        duration = random.randint(RALLY_DURATION_MIN, RALLY_DURATION_MAX)
        hit_bonus = random.randint(RALLY_HIT_BONUS_MIN, RALLY_HIT_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.RALLY],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateHitBonus(target, actor, "rallied", hit_bonus, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            whomever = "yourself" if target == actor else target.art_name
            msg = f"You rally {whomever}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            if target != actor:
                msg = f"{actor.art_name_cap} rallies you!"
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            whomever = f"{actor.pronoun_object}self" if target == actor else target.art_name}"
            msg = f"{actor.art_name} rallies {whomever}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            whomever = "yourself" if target == actor else target.art_name
            msg = f"You try to rally {whomever}, but fail!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            if target != actor:
                msg = f"{actor.art_name_cap} tries to rally you, but it doesn't work!"
                vars = set_vars(actor, actor, target, msg)
                target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            whomever = f"{actor.pronoun_object}self" if target == actor else target.art_name
            msg = f"{actor.art_name_cap} tries to rally {whomever}, but fails!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False

    @classmethod 
    async def do_fighter_rend(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0) -> bool:
        REND_DURATION_MIN = ticks_from_seconds(4)
        REND_DURATION_MAX = ticks_from_seconds(10)
        REND_PERIODIC_DAMAGE_MIN = 1
        REND_PERIODIC_DAMAGE_MAX = 4
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.REND],
                              difficulty_modifier - attrib_mod):
            duration = random.randint(REND_DURATION_MIN, REND_DURATION_MAX) * level_mult
            level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 2
            damage = (random.randint(REND_PERIODIC_DAMAGE_MIN, REND_PERIODIC_DAMAGE_MAX) + (attrib_mod / 2)) * level_mult
            msg = f"You tear open bloody wounds on {target.art_name}, for {damage} damage! {target.pronoun_subject} starts bleeding!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tears open bloody wounds on you, for {damage} damage! You are bleeding!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tears open bloody wounds on {target.art_name}! {firstcap(target.pronoun_subject)} starts bleeding!"
            vars = set_vars(actor, actor, target, msg)
            CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, 
                                                                     DescriptiveFlags.DAMAGE_TYPE_RAW, do_msg=False)
            new_state = CharacterStateBleeding(target, actor, "bleeding", game_tick, duration)
            new_state.apply_state(game_tick, duration)
            return True
        else:
            msg = f"Your attempt to rend didn't succeed!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False


    @classmethod
    async def do_rogue_backstab(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        BACKSTAB_DAMAGE_MULT = 4
        BACKSTAB_COOLDOWN_TICKS = 60
        if not actor.has_temp_flags(TemporaryCharacterFlags.HIDDEN):
            msg = "You must be hidden to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        if target == None:
            msg = "You must specify a target to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        if actor.equipped_[EquipLocation.BOTH_HANDS]:
            msg = "You can't backstab with a two-handed weapon!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        mhw = actor.equipped_[EquipLocation.MAIN_HAND]
        if not mhw:
            msg = "You must have a weapon equipped to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state)
            return False
        
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        attrib_mod = (actor.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.BACKSTAB], difficulty_modifier):
            damage = roll_dice(mhw.damage_dice_number_, mhw.damage_dice_size_, mhw.damage_dice_modifier_) * BACKSTAB_DAMAGE_MULT
            msg = f"You backstab {target.art_name} for {damage} damage!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs you for {damage} damage!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs {target.art_name}!"
            vars = set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, mhw.damage_type_)
            return True
        else:
            msg = f"You try to backstab {target.art_name}, but fumble your attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab you, but fumbles {actor.pronoun_possessive} attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab {target.art_name}, but fumbles {actor.pronoun_possessive} attack!"
            vars = set_vars(actor, actor, target, msg, cls.game_state)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False


    @classmethod
    async def do_rogue_stealth(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        STEALTH_RETRY_COOLDOWN_SEC = 3
        RETRY_SKILL_CHECK_SEC = 10
        last_cooldown = actor.last_cooldown(actor, Cooldown.last_cooldown(actor.cooldowns_, cooldown_source=cls.do_rogue_stealth))
        if last_cooldown:
            secs_remaining = seconds_from_ticks(last_cooldown.ticks_remaining(game_tick))
            msg = f"You can't retry stealth for another {secs_remaining} seconds!"
            vars = set_vars(actor, actor, target, msg, {'d': secs_remaining})
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        # cooldown before re-trying to stealth
        new_cooldown = Cooldown(actor, "stealth", cls.game_state, cooldown_source=cls.do_rogue_stealth)
        actor.add_cooldown(new_cooldown)
        new_cooldown.start(game_tick, ticks_from_seconds(STEALTH_RETRY_COOLDOWN_SEC))
        # have to re-try skill check
        new_cooldown = Cooldown(actor, "recheck stealth", cls.game_state, cooldown_source=cls.do_rogue_stealth, 
                                cooldown_vars=None, cooldown_end_fn=lambda cd: cls.recheck_stealth(actor,cd))
        actor.add_cooldown(new_cooldown)
        new_cooldown.start(game_tick, ticks_from_seconds(RETRY_SKILL_CHECK_SEC))
        return True

    @classmethod
    def stealthcheck(cls, sneaker: Actor, viewer: Actor, difficulty_modifier=0) -> bool:
        """
        Returns True if the actor successfully stealths, False otherwise"""
        level_mult = sneaker.levels_[CharacterClassRole.ROGUE] / viewer.total_levels_()
        attrib_mod = (sneaker.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        return cls.do_skill_check(sneaker, sneaker.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.STEALTH], difficulty_modifier)
    

    @classmethod
    def remove_stealth(cls, actor: Actor):
        actor.remove_temp_flags(TemporaryCharacterFlags.IS_STEALTHED)
        states = [s for s in actor.current_states if s is CharacterStateStealthed]
        for s in actor.remove_state:
            actor.remove_state(s)
        cds = [cd for cd in actor.cooldowns_ if cd.cooldown_source_ == cls.do_rogue_stealth]

    @classmethod
    def recheck_stealth(cls, sneaker: Actor, cooldown: Cooldown=None):
        if not sneaker.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
            retval = False
        for viewer in sneaker._location_room:
            if viewer == sneaker:
                continue
            if not cls.stealthcheck(sneaker, viewer):
                msg = f"You notice {sneaker.art_name} trying to hide!"
                vars = set_vars(sneaker, sneaker, viewer, msg, cls.game_state)
                viewer.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                if viewer.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE):
                    msg = f"{viewer.art_name} notices you and attacks!"
                    vars = set_vars(sneaker, viewer, sneaker, msg)
                    sneaker.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                    msg = f"{viewer.art_name_cap} notices {sneaker.art_name} and attacks!"
                    vars = set_vars(sneaker, sneaker, viewer, msg)
                    sneaker._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[sneaker, viewer], game_state=cls.game_state)
                    cls.remove_stealth(sneaker)
                    CoreActionsInterface.get_instance().start_fighting(viewer,sneaker)
                    CoreActionsInterface.get_instance().start_fighting(sneaker,viewer)
                retval = False
        

    @classmethod
    async def do_rogue_evade(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                             difficulty_modifier=0, game_tick=0) -> bool:
        EVADE_DURATION_MIN = ticks_from_seconds(6)
        EVADE_DURATION_MAX = ticks_from_seconds(12)
        EVADE_DODGE_BONUS_MIN = 4
        EVADE_DODGE_BONUS_MAX = 8
        level_mult = actor.levels_[CharacterClassRole.ROGUE] / 4
        duration = random.randint(EVADE_DURATION_MIN, EVADE_DURATION_MAX)
        dodge_bonus = random.randint(EVADE_DODGE_BONUS_MIN, EVADE_DODGE_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.ROGUE][RogueSkills.EVADE],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateHitBonus(target, actor, "evading", dodge_bonus, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You focus on evading blows!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try being evasive, but fail!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

    @classmethod
    async def do_rogue_pickpocket(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Pickpocketing is not yet implemented!", cls.game_state)
        return False


    @classmethod
    async def do_spell_fizzile(actor: Actor, target: Actor, spell_name: str, vars: dict=None,
                               game_state: 'ComprehensiveGameState'=None):
        msg = f"Your {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, game_state)
        msg = f"{actor.art_name_cap}'s {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=game_state)

    @classmethod
    async def do_mage_cast_fireball(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        FIREBALL_DMG_DICE_LEVEL_MULT = 1/4
        FIREBALL_DMG_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * FIREBALL_DMG_DICE_LEVEL_MULT
        FIREBALL_DMG_DICE_SIZE = 6
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        FIREBALL_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 8

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_FIREBALL],
                              difficulty_modifier - attrib_mod):
            damage = roll_dice(FIREBALL_DMG_DICE_NUM, FIREBALL_DMG_DICE_SIZE) + FIREBALL_DMG_BONUS
            msg = f"You cast a fireball at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a fireball at you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a fireball at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target] cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.FIRE)
            for c in actor.location_room:
                if c != actor and c != target:
                    msg = f"Your fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits you!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    c.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                    msg = f"{actor.art_name_cap}'s fireball also hits {c.art_name}!"
                    vars = set_vars(actor, actor, c, msg, { 'd': damage })
                    actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, c], game_state=cls.game_state)
                    await CoreActionsInterface.get_instance().do_calculated_damage(actor, c, damage, DamageType.FIRE)
            return True
        else:
            await cls.do_spell_fizzile(actor, target, "fireball", cls.game_state)
            return False


    @classmethod
    async def do_mage_cast_magic_missile(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        MAGIC_MISSILE_DMG_DICE_LEVEL_MULT = 1/4
        MAGIC_MISSILE_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * MAGIC_MISSILE_DMG_DICE_LEVEL_MULT
        MAGIC_MISSILE__DMG_DICE_SIZE = 6
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        MAGIC_MISSILE_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 4

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_FIREBALL],
                              difficulty_modifier - attrib_mod):
            damage = roll_dice(MAGIC_MISSILE_DICE_NUM, MAGIC_MISSILE__DMG_DICE_SIZE) + MAGIC_MISSILE_DMG_BONUS
            msg = f"You cast a magic missile at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a magic missile at you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a magic missile at {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target] cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.ARCANE)
            return True
        else:
            await cls.do_spell_fizzile(actor, target, "magic missile", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_light(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting light is not yet implemented!", cls.game_state)
        pass

    @classmethod
    async def do_mage_cast_shield(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        DAMAGE_REDUCTION_AMOUNT = actor.levels_[CharacterClassRole.MAGE]
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_SHIELD],
                              difficulty_modifier):
            msg = f"You cast a shield spell on yourself!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a shield spell on you! You feel shielded!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts a shield spell on {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target] cls.game_state)
            reductions = DamageReduction(reductions_by_type={
                DamageType.BLUDGEONING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.PIERCING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.SLASHING: DAMAGE_REDUCTION_AMOUNT
            }
            new_state = CharacterStateDamageReduction(target, actor, "shielded", DAMAGE_REDUCTION_AMOUNT, tick_created=game_tick)
            new_state.apply_state(game_tick, 0)
            return True
        else:
            await cls.do_spell_fizzile(actor, target, "shield", cls.game_state)
            return False


    @classmethod
    async def do_cleric_cure_light_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_cleric_cure_serious_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_cleric_cure_critical_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_cleric_heal(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    SKILL_COMMANDS = [
        {'commands': ["mighty kick", "mightykick", "kick", "mk"], 'skill': FighterSkills.MIGHTY_KICK, "function": do_fighter_mighty_kick},
        {'commands': ["demoralizing shout", "demoralizingshout", "shout", "ds"], 'skill': FighterSkills.DEMORALIZING_SHOUT, "function": do_fighter_demoralizing_shout},
        {'commands': ["intimidate", "intimidation", "intimidating", "intimidator", "intimidator"], 'skill': FighterSkills.INTIMIDATE, "function": do_fighter_intimidate},
        {'commands': ["disarm", "disarming", "disarmer", "disarmament", "disarmament"], 'skill': FighterSkills.DISARM, "function": do_fighter_disarm},
        {'commands': ["slam", "slamming", "slammer", "slammed", "slammed"], 'skill': FighterSkills.SLAM, "function": do_fighter_slam},
        {'commands': ["rally", "rallying", "rallier", "rallied", "rallied"], 'skill': FighterSkills.RALLY, "function": do_fighter_rally},
        {'commands': ["rend", "rending", "render", "rended", "rended"], 'skill': FighterSkills.REND, "function": do_fighter_rend},
        {'commands': ["backstab", "backstabbing", "backstabber", "backstabbed", "backstabbed"], 'skill': RogueSkills.BACKSTAB, "function": do_rogue_backstab},
        {'commands': ["stealth", "stealthy", "stealthily", "stealthiness", "stealthiness"], 'skill': RogueSkills.STEALTH, "function": do_rogue_stealth},
        {'commands': ["evade", "evading", "evader", "evaded", "evaded"], 'skill': RogueSkills.EVADE, "function": do_rogue_evade},
        {'commands': ["pickpocket", "pickpocketing", "pickpocketer", "pickpocketed", "pickpocketed"], 'skill': RogueSkills.PICKPOCKET, "function": do_rogue_pickpocket},
        {'commands': ["cast fireball", "castfireball", "fireball", "cf"], 'skill': MageSkills.CAST_FIREBALL, "function": do_mage_cast_fireball},
        {'commands': ["cast magic missile", "castmagicmissile", "magic missile", "cmm"], 'skill': MageSkills.CAST_MAGIC_MISSILE, "function": do_mage_cast_magic_missile},
        {'commands': ["cast light", "castlight", "light", "cl"], 'skill': MageSkills.CAST_LIGHT, "function": do_mage_cast_light},
        {'commands': ["cast shield", "castshield", "shield", "cs"], 'skill': MageSkills.CAST_SHIELD, "function": do_mage_cast_shield},
        {'commands': ["cast sleep", "castsleep", "sleep", "cs"], 'skill': MageSkills.CAST_SLEEP, "function": do_mage_cast_sleep},
        {'commands': ["cure light wounds", "curelightwounds", "light wounds", "clw"], 'skill': ClericSkills.CURE_LIGHT_WOUNDS, "function": do_cleric_cure_light_wounds},
        {'commands': ["cure serious wounds", "cureseriouswounds", "serious wounds", "csw"], 'skill': ClericSkills.CURE_SERIOUS_WOUNDS, "function": do_cleric_cure_serious_wounds},
        {'commands': ["cure critical wounds", "curecriticalwounds", "critical wounds", "ccw"], 'skill': ClericSkills.CURE_CRITICAL_WOUNDS, "function": do_cleric_cure_critical_wounds},
        {'commands': ["heal", "healing", "healer", "healed", "healed"], 'skill': ClericSkills.HEAL, "function": do_cleric_heal},
    ]

