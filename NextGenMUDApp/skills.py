from enum import Enum
import random
from .basic_types import DescriptiveFlags
from .communication import CommTypes
from .constants import CharacterClassRole
from .core_actions_interface import CoreActionsInterface
from .nondb_models.actor_states import Cooldown, CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStealthed, CharacterStateStunned
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation, PermanentCharacterFlags, TemporaryCharacterFlags
from .nondb_models.characters import Character, CharacterSkill
from .utility import roll_dice, set_vars, seconds_from_ticks, ticks_from_seconds



class FighterSkills(Enum):
    MIGHTY_KICK = 1
    DEMORALIZING_SHOUT = 2
    INTIMIDATE = 3
    DISARM = 4
    SLAM = 5
    RALLY = 6

    def __str__(self):
        return self.name.replace("_", " ").title()

class MageSkills(Enum):
    CAST_FIREBALL = 1
    CAST_MAGIC_MISSILE = 2
    CAST_LIGHT = 3
    CAST_SHIELD = 4
    CAST_SLEEP = 5
    CAST_CHARM = 6

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
            FighterSkills.RALLY: 1
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
        kick_duration = random.randint(KICK_DURATION_MIN, KICK_DURATION_MAX) * actor.levels[CharacterClassRole.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_, target.dodge_dice_modifier_)
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClassRole.FIGHTER][FighterSkills.MIGHTY_KICK], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "kicked", game_tick, kick_duration)
            new_state.apply_state(game_tick, kick_duration)
            msg = f"You kick {target.art_name} to the ground!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} kicks you to the ground!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} kicks %t% to the ground!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to kick {target.art_name}, but %r% dodges!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to kick you, but you dodge!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to kick {target.art_name}, but {target.pronoun_subject} dodges!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False


    @classmethod
    async def do_fighter_demoralizing_shout(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        DEMORALIZING_SHOUT_DURATION_MIN = ticks_from_seconds(6)
        DEMORALIZING_SHOUT_DURATION_MAX = ticks_from_seconds(12)
        DEMORALIZING_SHOUT_HIT_PENALTY_MIN = 10
        DEMORALIZING_SHOUT_HIT_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DEMORALIZING_SHOUT_DURATION_MIN, DEMORALIZING_SHOUT_DURATION_MAX) * level_mult
        hit_penalty = random.randint(DEMORALIZING_SHOUT_HIT_PENALTY_MIN, DEMORALIZING_SHOUT_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClassRole.FIGHTER][FighterSkills.DEMORALIZING_SHOUT], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "demoralized", hit_penalty, game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You shout at {target.art_name}, demoralizing {target.pronoun_object}!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name} shouts at you, demoralizing you!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name} shouts at {target.art_name}, demoralizing {target.pronoun_object}!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to shout at {target.art_name}, but {target.pronoun_object} resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to shout at you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to shout at {target.art_name}, but {target.pronoun_subject} resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
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
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClassRole.FIGHTER][FighterSkills.INTIMIDATE], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "intimidated", dodge_penalty, game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You intimidate {target.art_name}, making {target.pronoun_possessive} attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state)
            actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"{actor.art_name_cap} intimidates you, making your attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state)
            target.echo(CommTypes.DYNAMIC, msg, vars)
            msg = f"{actor.art_name_cap} intimidates {target.art_name}, making {target.pronoun_possessive} attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        else:
            msg = f"You try to intimidate {target.art_name}, but {actor.pronoun_subject} resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = "{actor.art_name_cap} tries to intimidate you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = "{actor.art_name_cap} tries to intimidate {target.art_name}, but {target.pronoun_subject_} resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            return False
        

    @classmethod
    async def do_fighter_disarm(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        DISARM_DURATION_MIN = ticks_from_seconds(3)
        DISARM_DURATION_MAX = ticks_from_seconds(6)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DISARM_DURATION_MIN, DISARM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.DISARM], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "disarmed", game_tick, duration)
            new_state.apply_state(game_tick, duration)
            msg = f"You disarm {target.art_name}!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} disarms you!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} disarms {target.art_name}!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True

    @classmethod
    async def do_fighter_slam(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        SLAM_DURATION_MIN = ticks_from_seconds(1)
        SLAM_DURATION_MAX = ticks_from_seconds(4)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(SLAM_DURATION_MIN, SLAM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClassRole.FIGHTER][FighterSkills.SLAM], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateStunned(target, actor, "slammed", game_tick, duration)
            new_state.apply_state(game_tick, duration)
            msg = f"You slam {target.art_name}, making {target.pronoun_object} easier to hit!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} intimidates you, making you easier to hit!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} intimidates {target.art_name}, making {target.pronoun_object} easier to hit!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to intimidate {target.art_name}, but {target.pronoun_subject} resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to intimidate you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to intimidate %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
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
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClassRole.ROGUE][RogueSkills.BACKSTAB], difficulty_modifier):
            damage = roll_dice(mhw.damage_dice_number_, mhw.damage_dice_size_, mhw.damage_dice_modifier_) * BACKSTAB_DAMAGE_MULT
            msg = f"You backstab {target.art_name} for {damage} damage!"
            set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs you for {damage} damage!"
            set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} backstabs {target.art_name}!"
            set_vars(actor, actor, target, msg, cls.game_state, {'d': damage})
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            await CoreActionsInterface.get_instance().do_damage(actor, target, damage, mhw.damage_type_)
            return True
        else:
            msg = f"You try to backstab {target.art_name}, but fumble your attack!"
            set_vars(actor, actor, target, msg, cls.game_state)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab you, but fumbles {actor.pronoun_possessive} attack!"
            set_vars(actor, actor, target, msg, cls.game_state)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to backstab {target.art_name}, but fumbles {actor.pronoun_possessive} attack!"
            set_vars(actor, actor, target, msg, cls.game_state)
            actor.location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False


    @classmethod
    async def do_rogue_stealth(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        STEALTH_RETRY_COOLDOWN_SEC = 3
        RETRY_SKILL_CHECK_SEC = 10
        last_cooldown = actor.last_cooldown(actor, Cooldown.last_cooldown(actor.cooldowns_, cooldown_source=cls.do_rogue_stealth))
        if last_cooldown:
            secs_remaining = seconds_from_ticks(last_cooldown.ticks_remaining(game_tick))
            msg = f"You can't retry stealth for another {secs_remaining} seconds!"
            set_vars(actor, actor, target, msg, {'d': secs_remaining})
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
        return cls.do_skill_check(sneaker, sneaker.skills_by_class_[CharacterClassRole.ROGUE][RogueSkills.STEALTH], difficulty_modifier)
    

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
        for viewer in sneaker.location_room:
            if viewer == sneaker:
                continue
            if not cls.stealthcheck(sneaker, viewer):
                msg = f"You notice {sneaker.art_name} trying to hide!"
                set_vars(sneaker, sneaker, viewer, msg, cls.game_state)
                viewer.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
                if viewer.has_perm_flags(PermanentCharacterFlags.IS_AGGRESSIVE):
                    msg = f"{viewer.art_name} notices you and attacks!"
                    set_vars(sneaker, viewer, sneaker, msg)
                    sneaker.echo(CommTypes.DYNAMIC, msg, vars, game_state=cls.game_state)
                    msg = f"{viewer.art_name_cap} notices {sneaker.art_name} and attacks!"
                    set_vars(sneaker, sneaker, viewer, msg)
                    sneaker.location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[sneaker, viewer], game_state=cls.game_state)
                    cls.remove_stealth(sneaker)
                    CoreActionsInterface.get_instance().start_fighting(viewer,sneaker)
                    CoreActionsInterface.get_instance().start_fighting(sneaker,viewer)
                retval = False
        

    @classmethod
    async def do_rogue_evade(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_rogue_pickpocket(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_mage_cast_fireball(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_mage_cast_magic_missile(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_mage_cast_light(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

    @classmethod
    async def do_mage_cast_shield(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

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

