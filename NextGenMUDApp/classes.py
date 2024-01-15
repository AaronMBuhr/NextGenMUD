from enum import Enum
import random
from .nondb_models.actors import Character, CharacterClass, CharacterSkill, ActorState, \
    CharacterStateForcedSitting, CharacterAttributes, CharacterStateHitPenalty, CharacterStateStunned, \
    TemporaryCharacterFlags, EquipLocation
from .utility import DescriptiveFlags, roll_dice, set_vars
from .nondb_models.actors import Actor
from .communication import CommTypes
from .constants import Constants
from .interfaces import GameStateInterface
from .core_actions import CoreActions


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

    def __str__(self):
        return self.name.replace("_", " ").title()

class RogueSkills(Enum):
    BACKSTAB = 1
    STEALTH = 2
    EVADE = 3
    PICKPOCKET = 4

    def __str__(self):
        return self.name.replace("_", " ").title()

class ClericSkills(Enum):
    CURE_LIGHT_WOUNDS = 1
    CURE_SERIOUS_WOUNDS = 2
    CURE_CRITICAL_WOUNDS = 3
    HEAL = 4

    def __str__(self):
        return self.name.replace("_", " ").title()



class Skills:

    game_state_: GameStateInterface = None

    ATTRIBUTE_AVERAGE = 10
    ATTRIBUTE_SKILL_MODIFIER_PER_POINT = 4

    SKILL_COMMANDS = {
        ["mighty kick", "mightykick", "kick", "mk"]: [FighterSkills.MIGHTY_KICK, "do_fighter_mighty_kick"],
        ["demoralizing shout", "demoralizingshout", "shout", "ds"]: [FighterSkills.DEMORALIZING_SHOUT, "do_fighter_demoralizing_shout"],
        ["intimidate", "intimidation", "intimidating", "intimidator", "intimidator"]: [FighterSkills.INTIMIDATE, "do_fighter_intimidate"],
        ["disarm", "disarming", "disarmer", "disarmament", "disarmament"]: [FighterSkills.DISARM, "do_fighter_disarm"],
        ["slam", "slamming", "slammer", "slammed", "slammed"]: [FighterSkills.SLAM, "do_fighter_slam"],
        ["rally", "rallying", "rallier", "rallied", "rallied"]: [FighterSkills.RALLY, "do_fighter_rally"],
        ["backstab", "backstabbing", "backstabber", "backstabbed", "backstabbed"]: [RogueSkills.BACKSTAB, "do_rogue_backstab"],
        ["stealth", "stealthy", "stealthily", "stealthiness", "stealthiness"]: [RogueSkills.STEALTH, "do_rogue_stealth"],
        ["evade", "evading", "evader", "evaded", "evaded"]: [RogueSkills.EVADE, "do_rogue_evade"],
        ["pickpocket", "pickpocketing", "pickpocketer", "pickpocketed", "pickpocketed"]: [RogueSkills.PICKPOCKET, "do_rogue_pickpocket"],
        ["cast fireball", "castfireball", "fireball", "cf"]: [MageSkills.CAST_FIREBALL, "do_mage_cast_fireball"],
        ["cast magic missile", "castmagicmissile", "magic missile", "cmm"]: [MageSkills.CAST_MAGIC_MISSILE, "do_mage_cast_magic_missile"],
        ["cast light", "castlight", "light", "cl"]: [MageSkills.CAST_LIGHT, "do_mage_cast_light"],
        ["cast shield", "castshield", "shield", "cs"]: [MageSkills.CAST_SHIELD, "do_mage_cast_shield"],
        ["cast sleep", "castsleep", "sleep", "cs"]: [MageSkills.CAST_SLEEP, "do_mage_cast_sleep"],
        ["cure light wounds", "curelightwounds", "light wounds", "clw"]: [ClericSkills.CURE_LIGHT_WOUNDS, "do_cleric_cure_light_wounds"],
        ["cure serious wounds", "cureseriouswounds", "serious wounds", "csw"]: [ClericSkills.CURE_SERIOUS_WOUNDS, "do_cleric_cure_serious_wounds"],
        ["cure critical wounds", "curecriticalwounds", "critical wounds", "ccw"]: [ClericSkills.CURE_CRITICAL_WOUNDS, "do_cleric_cure_critical_wounds"],
        ["heal", "healing", "healer", "healed", "healed"]: [ClericSkills.HEAL, "do_cleric_heal"],
    }

    @classmethod
    def set_game_state(cls, game_state: GameStateInterface):
        cls.game_state_ = game_state

    @classmethod
    def do_skill_check(cls, actor: Actor, skill: CharacterSkill, difficulty_mod: int=0, args: dict=None):
        skill_roll = random.randint(1, 100)
        return skill_roll < skill.skill_level_ - difficulty_mod

    @classmethod
    async def do_fighter_mighty_kick(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        KICK_DURATION_MIN = 4 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        KICK_DURATION_MAX = 8 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        kick_duration = random.randint(KICK_DURATION_MIN, KICK_DURATION_MAX) * actor.levels[CharacterClass.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_, target.dodge_dice_modifier_)
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClass.FIGHTER][FighterSkills.MIGHTY_KICK], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "kicked", game_tick, kick_duration)
            new_state.apply_state(game_tick, kick_duration)
            msg = "You kick %t% to the ground!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) kicks you to the ground!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) kicks %t% to the ground!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return True
        else:
            msg = "You try to kick %t%, but %r% dodges!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to kick you, but you dodge!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to kick %t%, but %r% dodges!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return False


    @classmethod
    async def do_fighter_demoralizing_shout(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        DEMORALIZING_SHOUT_DURATION_MIN = 6 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        DEMORALIZING_SHOUT_DURATION_MAX = 12/ (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        DEMORALIZING_SHOUT_HIT_PENALTY_MIN = 10
        DEMORALIZING_SHOUT_HIT_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClass.FIGHTER] / target.total_levels_()
        duration = random.randint(DEMORALIZING_SHOUT_DURATION_MIN, DEMORALIZING_SHOUT_DURATION_MAX) * level_mult
        hit_penalty = random.randint(DEMORALIZING_SHOUT_HIT_PENALTY_MIN, DEMORALIZING_SHOUT_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClass.FIGHTER][FighterSkills.DEMORALIZING_SHOUT], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "demoralized", hit_penalty, game_tick)
            new_state.apply_state(game_tick, duration)
            msg = "You shout at %t%, demoralizing %t%!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) shouts at you, demoralizing you!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) shouts at %t%, demoralizing %R%!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return True
        else:
            msg = "You try to shout at %t%, but %t% resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to shout at you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to shout at %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], cls.game_state_)
            return False


    @classmethod
    async def do_fighter_intimidate(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        INTIMIDATE_DURATION_MIN = 6 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        INTIMIDATE_DURATION_MIN = 12 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        INTIMIDATE_DODGE_PENALTY_MIN = 10
        INTIMIDATE_DODGE_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClass.FIGHTER] / target.total_levels_()
        duration = random.randint(INTIMIDATE_DURATION_MIN, INTIMIDATE_DURATION_MIN) * level_mult
        dodge_penalty = random.randint(INTIMIDATE_DODGE_PENALTY_MIN, INTIMIDATE_DODGE_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClass.FIGHTER][FighterSkills.INTIMIDATE], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "intimidated", dodge_penalty, game_tick)
            new_state.apply_state(game_tick, duration)
            msg = "You intimidate %t%, making %R% attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.echo(CommTypes.DYNAMIC, msg, vars)
            msg = "$cap(%a%) intimidates you, making your attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            target.echo(CommTypes.DYNAMIC, msg, vars)
            msg = "$cap(%a%) intimidates %t%, making %R% attacks less accurate!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars)
            return True
        else:
            msg = "You try to intimidate %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to intimidate you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to intimidate %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], cls.game_state_)
            return False
        

    @classmethod
    async def do_fighter_disarm(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        DISARM_DURATION_MIN = 3 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        DISARM_DURATION_MAX = 6 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        level_mult = actor.levels_[CharacterClass.FIGHTER] / target.total_levels_()
        duration = random.randint(DISARM_DURATION_MIN, DISARM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClass.FIGHTER][FighterSkills.DISARM], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "disarmed", game_tick, duration)
            new_state.apply_state(game_tick, duration)
            msg = "You disarm %t%!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) disarms you!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) disarms %t%!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return True

    @classmethod
    async def do_fighter_slam(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        STUN_DURATION_MIN = 1 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        INTIMIDATE_DURATION_MIN = 4 / (Constants.GAME_TICK_SEC * Constants.TICKS_PER_ROUND)
        level_mult = actor.levels_[CharacterClass.FIGHTER] / target.total_levels_()
        duration = random.randint(INTIMIDATE_DURATION_MIN, INTIMIDATE_DURATION_MIN) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClass.FIGHTER][FighterSkills.SLAM], difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateStunned(target, actor, "slammed", game_tick, duration)
            new_state.apply_state(game_tick, duration)
            msg = "You slam %t%, making %t% easier to hit!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) intimidates you, making you easier to hit!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) intimidates %t%, making %t% easier to hit!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return True
        else:
            msg = "You try to intimidate %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "%a% tries to intimidate you, but you resist!"
            set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "%a% tries to intimidate %t%, but %t%s resists!"
            set_vars(actor, actor, target, msg)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], cls.game_state_)
            return False

    @classmethod
    async def do_rogue_backstab(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        BACKSTAB_DAMAGE_MULT = 4
        if not actor.temporary_character_flags_.are_flags_set(TemporaryCharacterFlags.HIDDEN):
            msg = "You must be hidden to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state_)
            return False
        if target == None:
            msg = "You must specify a target to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state_)
            return False
        if actor.equipped_[EquipLocation.BOTH_HANDS]:
            msg = "You can't backstab with a two-handed weapon!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state_)
            return False
        mhw = actor.equipped_[EquipLocation.MAIN_HAND]
        if not mhw:
            msg = "You must have a weapon equipped to backstab!"
            actor.echo(CommTypes.DYNAMIC, msg, cls.game_state_)
            return False
        level_mult = actor.levels_[CharacterClass.FIGHTER] / target.total_levels_()
        attrib_mod = (actor.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        difficulty_modifier = attrib_mod + (level_mult * 10)
        if cls.do_skill_check(actor, actor.skills_by_class_[CharacterClass.ROGUE][RogueSkills.BACKSTAB], difficulty_modifier):
            damage = roll_dice(mhw.damage_dice_number_, mhw.damage_dice_size_, mhw.damage_dice_modifier_) * BACKSTAB_DAMAGE_MULT
            msg = "You backstab %t% for %d% damage!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) backstabs you for %d% damage!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) backstabs %t%!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            await CoreActions.do_damage(actor, target, damage, mhw.damage_type_)
            return True
        else:
            msg = "You try to backstab %t%, but fumble your attack!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to backstab you, but fumbles %Q% attack!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            msg = "$cap(%a%) tries to backstab %t%, but fumbles %Q% attack!"
            set_vars(actor, actor, target, msg, cls.game_state_)
            actor.location_room_.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state_)
            return False



    @classmethod
    async def do_rogue_stealth(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        pass

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
