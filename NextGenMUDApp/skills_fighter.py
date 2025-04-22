from .skills_core import Skills
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBerserkerStance, CharacterStateDefensiveStance, CharacterStateBleeding,
    CharacterStateDodgePenalty, Cooldown
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances, AttackData
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, firstcap
from .core_actions_interface import CoreActionsInterface
from collections import defaultdict


    # ***Fighter Skills***
    
class Skills_Fighter(Skills):
    @classmethod
    async def do_fighter_mighty_kick(cls, 
                                     actor: Actor, 
                                     target: Actor, 
                                     skill: CharacterSkill, 
                                     difficulty_modifier=0, 
                                     game_tick=0,
                                     nowait=False) -> bool:
        MIGHTY_KICK_CAST_TIME_TICKS = ticks_from_seconds(1)
        if actor.cooldowns.has_cooldown(actor, "mighty_kick"):
            msg = f"You can't use mighty kick again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_mighty_kick_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You wind up for a kick!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += MIGHTY_KICK_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, MIGHTY_KICK_CAST_TIME_TICKS, continue_func)
        return True

    @classmethod
    async def do_fighter_mighty_kick_finish(cls, 
                                            actor: Actor, 
                                            target: Actor, 
                                            skill: CharacterSkill, 
                                            difficulty_modifier=0, 
                                            game_tick=0) -> bool:
        KICK_DURATION_MIN = ticks_from_seconds(3)
        KICK_DURATION_MAX = ticks_from_seconds(6)
        KICK_COOLDOWN_TICKS = ticks_from_seconds(10)
        kick_duration = random.randint(KICK_DURATION_MIN, KICK_DURATION_MAX) \
            * actor.levels[CharacterClassRole.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_, target.dodge_dice_modifier_)
        cooldown = Cooldown(actor, "mighty_kick", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": KICK_COOLDOWN_TICKS})
        await cooldown.start(game_tick, KICK_COOLDOWN_TICKS)
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
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False


    @classmethod
    async def do_fighter_demoralizing_shout(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                            difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        DEMORALIZING_SHOUT_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        if actor.cooldowns.has_cooldown(actor, "demoralizing_shout"):
            msg = f"You can't use demoralizing shout again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_demoralizing_shout_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You clear your throat and prepare to shout!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += DEMORALIZING_SHOUT_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, DEMORALIZING_SHOUT_CAST_TIME_TICKS, continue_func)
        return True

    @classmethod
    async def do_fighter_demoralizing_shout_finish(cls, 
                                                    actor: Actor, 
                                                    target: Actor, 
                                                    skill: CharacterSkill, 
                                                    difficulty_modifier=0, 
                                                    game_tick=0) -> bool:
        DEMORALIZING_SHOUT_DURATION_MIN = ticks_from_seconds(6)
        DEMORALIZING_SHOUT_DURATION_MAX = ticks_from_seconds(12)
        DEMORALIZING_SHOUT_HIT_PENALTY_MIN = 10
        DEMORALIZING_SHOUT_HIT_PENALTY_MAX = 40
        DEMORALIZING_SHOUT_COOLDOWN_TICKS = ticks_from_seconds(10)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DEMORALIZING_SHOUT_DURATION_MIN, DEMORALIZING_SHOUT_DURATION_MAX) * level_mult
        hit_penalty = random.randint(DEMORALIZING_SHOUT_HIT_PENALTY_MIN, DEMORALIZING_SHOUT_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "demoralizing_shout", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": DEMORALIZING_SHOUT_COOLDOWN_TICKS})
        await cooldown.start(game_tick, DEMORALIZING_SHOUT_COOLDOWN_TICKS)
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
    async def do_fighter_intimidate(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        INTIMIDATE_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        if actor.cooldowns.has_cooldown(actor, "intimidate"):
            msg = f"You can't use intimidate again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_intimidate_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You try to look intimidating!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += INTIMIDATE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, INTIMIDATE_CAST_TIME_TICKS, continue_func)
        return True
        
    @classmethod
    async def do_fighter_intimidate_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        INTIMIDATE_DURATION_MIN = ticks_from_seconds(6)
        INTIMIDATE_DURATION_MIN = ticks_from_seconds(12)
        INTIMIDATE_HIT_PENALTY_MIN = 10
        INTIMIDATE_HIT_PENALTY_MAX = 40
        INTIMIDATE_COOLDOWN_TICKS = ticks_from_seconds(10)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(INTIMIDATE_DURATION_MIN, INTIMIDATE_DURATION_MIN) * level_mult
        hit_penalty = random.randint(INTIMIDATE_HIT_PENALTY_MIN, INTIMIDATE_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "intimidate", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": INTIMIDATE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, INTIMIDATE_COOLDOWN_TICKS)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.INTIMIDATE],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateHitPenalty(target, actor, "intimidated", hit_penalty, tick_created=game_tick)
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
                                difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        DISARM_CAST_TIME_TICKS = ticks_from_seconds(0.25)
        if actor.cooldowns.has_cooldown(actor, "disarm"):
            msg = f"You can't use disarm again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_disarm_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You focus on your disarm technique!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += DISARM_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, DISARM_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_fighter_disarm_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                difficulty_modifier=0, game_tick=0) -> bool:
        DISARM_DURATION_MIN = ticks_from_seconds(3)
        DISARM_DURATION_MAX = ticks_from_seconds(6)
        DISARM_COOLDOWN_TICKS = ticks_from_seconds(10)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(DISARM_DURATION_MIN, DISARM_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "disarm", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": DISARM_COOLDOWN_TICKS})
        await cooldown.start(game_tick, DISARM_COOLDOWN_TICKS)
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
                              difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        SLAM_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "slam"):
            msg = f"You can't use slam again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_slam_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You wind up for a slam!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += SLAM_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, SLAM_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_fighter_slam_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0) -> bool:
        SLAM_DURATION_MIN = ticks_from_seconds(1)
        SLAM_DURATION_MAX = ticks_from_seconds(4)
        SLAM_DODGE_PENALTY_MIN = 10
        SLAM_DODGE_PENALTY_MAX = 40
        SLAM_COOLDOWN_TICKS = ticks_from_seconds(10)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(SLAM_DURATION_MIN, SLAM_DURATION_MAX) * level_mult
        dodge_penalty = random.randint(SLAM_DODGE_PENALTY_MIN, SLAM_DODGE_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "slam", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": SLAM_COOLDOWN_TICKS})
        await cooldown.start(game_tick, SLAM_COOLDOWN_TICKS)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.SLAM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateDodgePenalty(target, actor, "slammed", dodge_penalty, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You slam {target.art_name}, making {target.pronoun_object} easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} slams you, making you easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} slams {target.art_name}, making {target.pronoun_object} easier to hit!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to slam {target.art_name}, but {target.pronoun_subject} resists!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to slam you, but you resist!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to slam %t%, but %t%s dodges!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False

    
    @classmethod
    async def do_fighter_bash(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        BASH_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "bash"):
            msg = f"You can't use bash again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_bash_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You wind up for a bash!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += BASH_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, BASH_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_fighter_bash_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0) -> bool:
        BASH_DURATION_MIN = ticks_from_seconds(1)
        BASH_DURATION_MAX = ticks_from_seconds(4)
        BASH_COOLDOWN_TICKS = ticks_from_seconds(10)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(BASH_DURATION_MIN, BASH_DURATION_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "bash", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": BASH_COOLDOWN_TICKS})
        await cooldown.start(game_tick, BASH_COOLDOWN_TICKS)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.SLAM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateStunned(target, actor, "bashed", tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            msg = f"You bash {target.art_name}, stunning {target.pronoun_object}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} bashes you, briefly stunning you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} bashes {target.art_name}, stunning {target.pronoun_object}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return True
        else:
            msg = f"You try to bash {target.art_name}, but you miss!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to bash you, but you dodge!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tries to bash %t%, but %t%s dodges!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target],
                                      game_state=cls.game_state)
            return False

    
    @classmethod
    async def do_fighter_rally(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                            difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        RALLY_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "rally"):
            msg = f"You can't use rally again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_rally_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You focus on your rally!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += RALLY_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, RALLY_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_fighter_rally_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                            difficulty_modifier=0, game_tick=0) -> bool:
        RALLY_DURATION_MIN = ticks_from_seconds(6)
        RALLY_DURATION_MAX = ticks_from_seconds(12)
        RALLY_HIT_BONUS_MIN = 4
        RALLY_HIT_BONUS_MAX = 8
        RALLY_COOLDOWN_TICKS = ticks_from_seconds(20)
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 4
        duration = random.randint(RALLY_DURATION_MIN, RALLY_DURATION_MAX)
        hit_bonus = random.randint(RALLY_HIT_BONUS_MIN, RALLY_HIT_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, "rally", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": RALLY_COOLDOWN_TICKS})
        await cooldown.start(game_tick, RALLY_COOLDOWN_TICKS)
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
            whomever = f"{actor.pronoun_object}self" if target == actor else target.art_name
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
                              difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        REND_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "rend"):
            msg = f"You can't use rend again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_rend_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You aim your rend..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += REND_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, REND_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod 
    async def do_fighter_rend_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                              difficulty_modifier=0, game_tick=0) -> bool:
        REND_DURATION_MIN = ticks_from_seconds(4)
        REND_DURATION_MAX = ticks_from_seconds(10)
        REND_PERIODIC_DAMAGE_MIN = 1
        REND_PERIODIC_DAMAGE_MAX = 4
        REND_COOLDOWN_TICKS = ticks_from_seconds(15)
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 2
        cooldown = Cooldown(actor, "rend", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": REND_COOLDOWN_TICKS})
        await cooldown.start(game_tick, REND_COOLDOWN_TICKS)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.REND],
                              difficulty_modifier - attrib_mod):
            duration = random.randint(REND_DURATION_MIN, REND_DURATION_MAX) * level_mult
            damage = (random.randint(REND_PERIODIC_DAMAGE_MIN, REND_PERIODIC_DAMAGE_MAX) + (attrib_mod / 2)) * level_mult
            msg = f"You tear open bloody wounds on {target.art_name}, for {damage} damage! {target.pronoun_subject} starts bleeding!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tears open bloody wounds on you, for {damage} damage! You are bleeding!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} tears open bloody wounds on {target.art_name}! {firstcap(target.pronoun_subject)} starts bleeding!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state, exceptions=[actor, target])
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
    async def do_fighter_berserker_stance(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                          difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        BERSERKER_STANCE_DODGE_PENALTY = 4
        BERSERKER_STANCE_HIT_BONUS = 8
        BERSERKER_STANCE_COOLDOWN_TICKS = ticks_from_seconds(30)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if actor.cooldowns.has_cooldown(actor, "berserker_stance"):
            msg = f"You can't use berserker stance again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 4
        skill_mod = actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.BERSERKER_STANCE]
        dodge_mod = BERSERKER_STANCE_DODGE_PENALTY * level_mult # i guess dodge penalty is only level-based
        hit_mod = (BERSERKER_STANCE_HIT_BONUS - skill_mod) * level_mult # whereas hit mod also factors in skill
        
        cooldown = Cooldown(actor, "berserker_stance", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": BERSERKER_STANCE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, BERSERKER_STANCE_COOLDOWN_TICKS)
        
        new_state = CharacterStateBerserkerStance(actor, cls.game_state, source_actor=actor,
                                                  dodge_penalty=dodge_mod, hit_bonus=hit_mod)
        new_state.apply_state(game_tick)
        msg = f"You assume berserker stance!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = f"{actor.art_name_cap} assumes berserker stance!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        return True
    
    @classmethod
    async def do_fighter_defensive_stance(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                          difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        DEFENSIVE_STANCE_COOLDOWN_TICKS = ticks_from_seconds(5)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if actor.cooldowns.has_cooldown(actor, "defensive_stance"):
            msg = f"You can't use defensive stance again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        cooldown = Cooldown(actor, "defensive_stance", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": DEFENSIVE_STANCE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, DEFENSIVE_STANCE_COOLDOWN_TICKS)
        resist_amount = actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.DEFENSIVE_STANCE] / 5
        resistances = DamageResistances(resistances_by_type=
                                        {
                                            DamageType.SLASHING: resist_amount, 
                                            DamageType.PIERCING: resist_amount, 
                                            DamageType.BLUDGEONING: resist_amount,
                                            DamageType.FIRE: resist_amount / 3,
                                            DamageType.COLD: resist_amount / 3,
                                            DamageType.LIGHTNING: resist_amount / 3,
                                            DamageType.ACID: resist_amount / 3,
                                        })
        new_state = CharacterStateDefensiveStance(actor, cls.game_state, source_actor=actor,
                                                  state_type_name="damage_resist", damage_resistances = resistances);
        new_state.apply_state(game_tick)
        return True

    @classmethod
    async def do_fighter_normal_stance(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                          difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        NORMAL_STANCE_COOLDOWN_TICKS = ticks_from_seconds(5)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if actor.cooldowns.has_cooldown(actor, "normal_stance"):
            msg = f"You can't change stances again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        cooldown = Cooldown(actor, "normal_stance", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": NORMAL_STANCE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, NORMAL_STANCE_COOLDOWN_TICKS)
        
        changed = False
        if actor.has_state(CharacterStateBerserkerStance):
            actor.remove_state(CharacterStateBerserkerStance)
            msg = f"You return to normal stance!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} returns to normal stance!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            changed = True
        if actor.has_state(CharacterStateDefensiveStance):
            actor.remove_state(CharacterStateDefensiveStance)
            msg = f"You return to normal stance!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} returns to normal stance!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            changed = True
        if changed:
            return True
        else:
            msg = "You are already in normal stance!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

    @classmethod
    async def do_fighter_cleave(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        CLEAVE_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "cleave"):
            msg = f"You can't use cleave again yet!"
            vars = set_vars(actor, actor, target, msg   )
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_cleave_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You swing back your cleave..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            actor.recovers_at += CLEAVE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, CLEAVE_CAST_TIME_TICKS, continue_func)
            return True

    @classmethod
    async def do_fighter_cleave_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        CLEAVE_COOLDOWN_TICKS = ticks_from_seconds(10)
        
        cooldown = Cooldown(actor, "cleave", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": CLEAVE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, CLEAVE_COOLDOWN_TICKS)

        # right now just two targets
        targets = [ target ]

        if actor.fighting_whom != None and actor.fighting_whom != target:
            targets.append(actor.fighting_whom)
            
        if len(targets) < 2:
            # check for nearby enemies
            nearby_enemies = actor.location_room.get_nearby_enemies(actor)
            if len(nearby_enemies) > 0:
                targets.append(nearby_enemies[0])

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.CLEAVE], difficulty_modifier):
            # Success message
            target_names = ", ".join([t.art_name for t in targets])
            msg = f"Your cleave attack strikes {target_names}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            # Hit each target with one attack multiplied by number of main hand attacks
            total_dmgs = defaultdict(int)
            
            if actor.equipped[EquipLocation.MAIN_HAND] != None \
            or actor.equipped[EquipLocation.BOTH_HANDS] != None:
                num_attacks = actor.num_main_hand_attacks
                if actor.equipped[EquipLocation.BOTH_HANDS] != None:
                    hands = "both hands"
                    weapon = actor.equipped[EquipLocation.BOTH_HANDS]
                else:
                    hands = "main hand"
                    weapon = actor.equipped[EquipLocation.MAIN_HAND]
                
                # Single attack data
                attack_data = AttackData(
                    damage_type=weapon.damage_type, 
                    damage_num_dice=weapon.damage_num_dice, 
                    damage_dice_size=weapon.damage_dice_size, 
                    damage_bonus=weapon.damage_bonus, 
                    attack_verb=weapon.damage_type.verb(), 
                    attack_noun=weapon.damage_type.noun(),
                    attack_bonus=weapon.attack_bonus
                    )
                
                for t in targets:
                    # Each target gets hit once, but damage is multiplied by number of attacks
                    base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, t, attack_data)
                    final_damage = base_damage * num_attacks
                    total_dmgs[t] = final_damage
                    # Message to the target
                    msg = f"{actor.art_name_cap}'s cleave strikes you for {final_damage} damage!"
                    vars = set_vars(actor, actor, t, msg)
                    t.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            else:
                # Natural attacks
                for natural_attack in actor.natural_attacks:
                    for t in targets:
                        # Each target gets hit once, but damage is multiplied by number of attacks
                        base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, t, natural_attack)
                        final_damage = base_damage * actor.num_main_hand_attacks
                        total_dmgs[t] = final_damage
                        # Message to the target
                        msg = f"{actor.art_name_cap}'s cleave strikes you for {final_damage} damage!"
                        vars = set_vars(actor, actor, t, msg)
                        t.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            # Message to others in the room
            msg = f"{actor.art_name_cap}'s cleave attack strikes multiple targets!"
            vars = set_vars(actor, actor, target, msg)
            exceptions = [actor] + targets
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=exceptions, game_state=cls.game_state)
            
            return True
        else:
            # Failure messages
            msg = f"You attempt a cleave attack but lose your balance!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts a cleave attack but loses {actor.pronoun_possessive} balance!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            return False

        # TODO: where are resistances/vulnerabilities handled?
        total_dmgs = defaultdict(int)
        if actor.equipped[EquipLocation.MAIN_HAND] != None \
        or actor.equipped[EquipLocation.BOTH_HANDS] != None:
            num_attacks = actor.num_main_hand_attacks
            if actor.equipped[EquipLocation.BOTH_HANDS] != None:
                hands = "both hands"
                weapon = actor.equipped[EquipLocation.BOTH_HANDS]
            else:
                hands = "main hand"
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
            logger.critical(f"character: {actor.rid} attacking {num_attacks}x with {weapon.name} in {hands})")
            logger.critical(f"weapon: +{weapon.attack_bonus} {weapon.damage_type}: {weapon.damage_num_dice}d{weapon.damage_dice_size} +{weapon.damage_bonus}")
            for n in range(num_attacks):
                attack_data = AttackData(
                    damage_type=weapon.damage_type, 
                    damage_num_dice=weapon.damage_num_dice, 
                    damage_dice_size=weapon.damage_dice_size, 
                    damage_bonus=weapon.damage_bonus, 
                    attack_verb=weapon.damage_type.verb(), 
                    attack_noun=weapon.damage_type.noun(),
                    attack_bonus=weapon.attack_bonus
                    )
                logger.critical(f"attack_data: {attack_data.to_dict()}")
                for t in targets:
                    total_dmgs[t] += await CoreActionsInterface.do_single_attack(actor, t, attack_data)
        else:
            for natural_attack in actor.natural_attacks:
                logger.critical(f"natural_attack: {natural_attack.to_dict()}")
                for t in targets:
                    total_dmgs[t] += await CoreActionsInterface.do_single_attack(actor, t, natural_attack)
            
    @classmethod
    async def do_fighter_whirlwind(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                 difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        WHIRLWIND_CAST_TIME_TICKS = ticks_from_seconds(1.5)
        if actor.cooldowns.has_cooldown(actor, "whirlwind"):
            msg = f"You can't use whirlwind again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_whirlwind_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You begin to spin with your weapon..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} begins to spin with {actor.pronoun_possessive} weapon..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += WHIRLWIND_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, WHIRLWIND_CAST_TIME_TICKS, continue_func)
        return True
        
    @classmethod
    async def do_fighter_whirlwind_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        WHIRLWIND_COOLDOWN_TICKS = ticks_from_seconds(20)
        
        cooldown = Cooldown(actor, "whirlwind", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": WHIRLWIND_COOLDOWN_TICKS})
        await cooldown.start(game_tick, WHIRLWIND_COOLDOWN_TICKS)

        # Gather all targets - all enemies in the room
        targets = []
        if target is not None:
            targets.append(target)

        # Add all enemies the actor is fighting if not already in targets
        if actor.fighting_whom is not None and actor.fighting_whom not in targets:
            targets.append(actor.fighting_whom)

        # Get all nearby enemies in the room
        nearby_enemies = actor.location_room.get_nearby_enemies(actor)
        for enemy in nearby_enemies:
            if enemy not in targets:
                targets.append(enemy)

        if not targets:
            msg = f"There are no enemies to strike with your whirlwind attack!"
            vars = set_vars(actor, actor, None, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.WHIRLWIND], difficulty_modifier):
            # Success message
            target_names = ", ".join([t.art_name for t in targets])
            msg = f"Your whirlwind attack strikes {target_names}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            # Hit each target with one attack multiplied by number of main hand attacks
            total_dmgs = defaultdict(int)
            
            if actor.equipped[EquipLocation.MAIN_HAND] != None \
            or actor.equipped[EquipLocation.BOTH_HANDS] != None:
                num_attacks = actor.num_main_hand_attacks
                if actor.equipped[EquipLocation.BOTH_HANDS] != None:
                    hands = "both hands"
                    weapon = actor.equipped[EquipLocation.BOTH_HANDS]
                else:
                    hands = "main hand"
                    weapon = actor.equipped[EquipLocation.MAIN_HAND]
                
                # Single attack data
                attack_data = AttackData(
                    damage_type=weapon.damage_type, 
                    damage_num_dice=weapon.damage_num_dice, 
                    damage_dice_size=weapon.damage_dice_size, 
                    damage_bonus=weapon.damage_bonus, 
                    attack_verb=weapon.damage_type.verb(), 
                    attack_noun=weapon.damage_type.noun(),
                    attack_bonus=weapon.attack_bonus
                    )
                
                for t in targets:
                    # Each target gets hit once, but damage is multiplied by number of attacks
                    base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, t, attack_data)
                    final_damage = base_damage * num_attacks
                    total_dmgs[t] = final_damage
                    # Message to the target
                    msg = f"{actor.art_name_cap}'s whirlwind strikes you for {final_damage} damage!"
                    vars = set_vars(actor, actor, t, msg)
                    t.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            else:
                # Natural attacks
                for natural_attack in actor.natural_attacks:
                    for t in targets:
                        # Each target gets hit once, but damage is multiplied by number of attacks
                        base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, t, natural_attack)
                        final_damage = base_damage * actor.num_main_hand_attacks
                        total_dmgs[t] = final_damage
                        # Message to the target
                        msg = f"{actor.art_name_cap}'s whirlwind strikes you for {final_damage} damage!"
                        vars = set_vars(actor, actor, t, msg)
                        t.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            # Message to others in the room
            msg = f"{actor.art_name_cap}'s whirlwind attack strikes multiple targets!"
            vars = set_vars(actor, actor, target, msg)
            exceptions = [actor] + targets
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=exceptions, game_state=cls.game_state)
            
            return True
        else:
            # Failure messages
            msg = f"You attempt a whirlwind attack but lose your balance!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts a whirlwind attack but loses {actor.pronoun_possessive} balance!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            return False

    @classmethod
    async def do_fighter_execute(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        EXECUTE_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "execute"):
            msg = f"You can't use execute again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        if not target:
            msg = f"You need a target to execute!"
            vars = set_vars(actor, actor, None, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        # Check if target is at 25% health or less
        health_percentage = (target.hit_points / target.max_hit_points) * 100
        if health_percentage > 25:
            msg = f"{target.art_name} is not weak enough to execute yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_fighter_execute_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You prepare to execute {target.art_name}..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} prepares to execute {target.art_name}..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += EXECUTE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, EXECUTE_CAST_TIME_TICKS, continue_func)
        return True
        
    @classmethod
    async def do_fighter_execute_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        EXECUTE_DAMAGE_MULTIPLIER = 2.5  # Higher damage because it can only be used on low health targets
        EXECUTE_COOLDOWN_TICKS = ticks_from_seconds(30)
        
        # Recheck if target is still at 33% health or less (might have changed during cast time)
        health_percentage = (target.hit_points / target.max_hit_points) * 100
        if health_percentage > 33:
            msg = f"{target.art_name} is not weak enough to execute anymore!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        cooldown = Cooldown(actor, "execute", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": EXECUTE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, EXECUTE_COOLDOWN_TICKS)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
            
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.EXECUTE],
                           difficulty_modifier - attrib_mod):
            # Calculate execute damage
            level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 10
            
            base_damage = 0
            damage_type = None
            
            # Determine damage based on equipped weapon or natural attacks
            if actor.equipped[EquipLocation.MAIN_HAND] is not None:
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
                damage_type = weapon.damage_type
                base_damage = roll_dice(weapon.damage_num_dice, weapon.damage_dice_size, weapon.damage_bonus)
            elif actor.equipped[EquipLocation.BOTH_HANDS] is not None:
                weapon = actor.equipped[EquipLocation.BOTH_HANDS]
                damage_type = weapon.damage_type
                base_damage = roll_dice(weapon.damage_num_dice, weapon.damage_dice_size, weapon.damage_bonus)
            elif actor.natural_attacks:
                natural_attack = actor.natural_attacks[0]  # Use first natural attack
                damage_type = natural_attack.damage_type
                base_damage = roll_dice(natural_attack.damage_num_dice, natural_attack.damage_dice_size, natural_attack.damage_bonus)
            
            if base_damage == 0:
                # Fallback damage if no weapon or natural attack
                base_damage = roll_dice(1, 6, 0)
                damage_type = DamageType.BLUDGEONING
            
            # Apply execute damage multiplier and scaling, and multiply by number of main hand attacks for all characters
            attack_multiplier = actor.num_main_hand_attacks
            final_damage = int(base_damage * EXECUTE_DAMAGE_MULTIPLIER * (1 + level_mult + (attrib_mod / 20)) * attack_multiplier)
            
            # Deal damage to target
            await CoreActionsInterface.get_instance().do_calculated_damage(
                actor, target, final_damage, damage_type, do_msg=False)
            
            # Success messages
            msg = f"You execute {target.art_name} for {final_damage} damage!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} executes you for {final_damage} damage!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} executes {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            
            return True
        else:
            # Failure messages
            msg = f"You attempt to execute {target.art_name}, but miss your strike!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts to execute you, but misses!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts to execute {target.art_name}, but misses!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            
            return False

    @classmethod
    async def do_fighter_enrage(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        ENRAGE_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        if actor.cooldowns.has_cooldown(actor, "enrage"):
            msg = f"You can't use enrage again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_fighter_enrage_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You begin to channel your rage..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} begins to channel {actor.pronoun_possessive} rage..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += ENRAGE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, ENRAGE_CAST_TIME_TICKS, continue_func)
        return True
        
    @classmethod
    async def do_fighter_enrage_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        ENRAGE_DURATION_MIN = ticks_from_seconds(6)
        ENRAGE_DURATION_MAX = ticks_from_seconds(12)
        ENRAGE_DAMAGE_BONUS_MIN = 15
        ENRAGE_DAMAGE_BONUS_MAX = 40
        ENRAGE_COOLDOWN_TICKS = ticks_from_seconds(60)  # Longer cooldown due to powerful effect
        
        cooldown = Cooldown(actor, "enrage", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": ENRAGE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, ENRAGE_COOLDOWN_TICKS)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 10
            
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.ENRAGE],
                           difficulty_modifier - attrib_mod):
            # Calculate duration and damage bonus
            duration = random.randint(ENRAGE_DURATION_MIN, ENRAGE_DURATION_MAX)
            damage_bonus = int(random.randint(ENRAGE_DAMAGE_BONUS_MIN, ENRAGE_DAMAGE_BONUS_MAX) * (1 + level_mult))
            
            # Apply the damage bonus state
            new_state = CharacterStateDamageBonus(actor, cls.game_state, source_actor=actor, 
                                                state_type_name="enraged", affect_amount=damage_bonus, 
                                                tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            
            return True
        else:
            # Failure messages
            msg = f"You try to channel your rage, but fail to focus it!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} tries to channel {actor.pronoun_possessive} rage, but fails to focus it!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            
            return False

    @classmethod
    async def do_fighter_massacre(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        MASSACRE_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        if actor.cooldowns.has_cooldown(actor, "massacre"):
            msg = f"You can't use massacre again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        if not target:
            msg = f"You need a target to massacre!"
            vars = set_vars(actor, actor, None, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_fighter_massacre_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You prepare to massacre {target.art_name}..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} prepares to massacre {target.art_name}..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += MASSACRE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, MASSACRE_CAST_TIME_TICKS, continue_func)
        return True
        
    @classmethod
    async def do_fighter_massacre_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        MASSACRE_DAMAGE_MULTIPLIER = 3.5  # Higher than execute's 2.5
        MASSACRE_COOLDOWN_TICKS = ticks_from_seconds(45)  # Longer cooldown than execute
        
        cooldown = Cooldown(actor, "massacre", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": MASSACRE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, MASSACRE_COOLDOWN_TICKS)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
            
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.MASSACRE],
                           difficulty_modifier - attrib_mod):
            # Calculate massacre damage
            level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 10
            
            base_damage = 0
            damage_type = None
            
            # Determine damage based on equipped weapon or natural attacks
            if actor.equipped[EquipLocation.MAIN_HAND] is not None:
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
                damage_type = weapon.damage_type
                base_damage = roll_dice(weapon.damage_num_dice, weapon.damage_dice_size, weapon.damage_bonus)
            elif actor.equipped[EquipLocation.BOTH_HANDS] is not None:
                weapon = actor.equipped[EquipLocation.BOTH_HANDS]
                damage_type = weapon.damage_type
                base_damage = roll_dice(weapon.damage_num_dice, weapon.damage_dice_size, weapon.damage_bonus)
            elif actor.natural_attacks:
                natural_attack = actor.natural_attacks[0]  # Use first natural attack
                damage_type = natural_attack.damage_type
                base_damage = roll_dice(natural_attack.damage_num_dice, natural_attack.damage_dice_size, natural_attack.damage_bonus)
            
            if base_damage == 0:
                # Fallback damage if no weapon or natural attack
                base_damage = roll_dice(1, 6, 0)
                damage_type = DamageType.BLUDGEONING
            
            # Apply massacre damage multiplier and scaling, and multiply by number of main hand attacks for all characters
            attack_multiplier = actor.num_main_hand_attacks
            final_damage = int(base_damage * MASSACRE_DAMAGE_MULTIPLIER * (1 + level_mult + (attrib_mod / 20)) * attack_multiplier)
            
            # Deal damage to target
            await CoreActionsInterface.get_instance().do_calculated_damage(
                actor, target, final_damage, damage_type, do_msg=False)
            
            # Success messages
            msg = f"You massacre {target.art_name} for {final_damage} damage!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} massacres you for {final_damage} damage!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} massacres {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            
            return True
        else:
            # Failure messages
            msg = f"You attempt to massacre {target.art_name}, but miss your strike!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts to massacre you, but misses!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} attempts to massacre {target.art_name}, but misses!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
            
            return False

    @classmethod
    async def do_fighter_shield_block(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        SHIELD_BLOCK_CAST_TIME_TICKS = ticks_from_seconds(0.5)  # Quick cast time
        SHIELD_BLOCK_DURATION_TICKS = ticks_from_seconds(10)  # 10 second duration
        SHIELD_BLOCK_COOLDOWN_TICKS = ticks_from_seconds(30)  # 30 second cooldown
        
        if actor.cooldowns.has_cooldown(actor, "shield_block"):
            msg = f"You can't use shield block again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_fighter_shield_block_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You prepare to raise your shield..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} prepares to raise {actor.pronoun_possessive} shield..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += SHIELD_BLOCK_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, SHIELD_BLOCK_CAST_TIME_TICKS, continue_func)
        return True

    @classmethod
    async def do_fighter_shield_block_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0) -> bool:
        SHIELD_BLOCK_DURATION_TICKS = ticks_from_seconds(10)  # 10 second duration
        SHIELD_BLOCK_COOLDOWN_TICKS = ticks_from_seconds(30)  # 30 second cooldown
        
        cooldown = Cooldown(actor, "shield_block", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": SHIELD_BLOCK_COOLDOWN_TICKS})
        await cooldown.start(game_tick, SHIELD_BLOCK_COOLDOWN_TICKS)
        
        # Calculate resistances based on skill level and strength
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 10
        resist_amount = (actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.SHIELD_BLOCK] / 3) * (1 + level_mult)
        
        resistances = DamageResistances(resistances_by_type=
                                    {
                                        DamageType.SLASHING: resist_amount,
                                        DamageType.PIERCING: resist_amount,
                                        DamageType.BLUDGEONING: resist_amount,
                                        DamageType.FIRE: resist_amount / 2,
                                        DamageType.COLD: resist_amount / 2,
                                        DamageType.LIGHTNING: resist_amount / 2,
                                        DamageType.ACID: resist_amount / 2,
                                    })
        
        new_state = CharacterStateShielded(actor, cls.game_state, source_actor=actor,
                                        state_type_name="shield block", resistances=resistances, tick_created=game_tick)
        new_state.apply_state(game_tick, SHIELD_BLOCK_DURATION_TICKS)
        
        msg = f"You raise your shield, increasing your defenses!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = f"{actor.art_name_cap} raises {actor.pronoun_possessive} shield, increasing {actor.pronoun_possessive} defenses!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        return True

    # Add to SKILL_COMMANDS:
    # {'commands': ["shield block", "shieldblock", "block", "sb"], 'skill': FighterSkills.SHIELD_BLOCK, "function": do_fighter_shield_block} 

    @classmethod
    async def do_fighter_shield_sweep(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        SHIELD_SWEEP_CAST_TIME_TICKS = ticks_from_seconds(0.5)  # Quick cast time
        SHIELD_SWEEP_COOLDOWN_TICKS = ticks_from_seconds(20)  # 20 second cooldown
        
        if actor.cooldowns.has_cooldown(actor, "shield_sweep"):
            msg = f"You can't use shield sweep again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        continue_func = lambda: cls.do_fighter_shield_sweep_finish(actor, target, skill, difficulty_modifier, game_tick)
        if nowait:
            continue_func()
        else:
            msg = f"You prepare to sweep your shield in a wide arc..."
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} prepares to sweep {actor.pronoun_possessive} shield in a wide arc..."
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            actor.recovers_at += SHIELD_SWEEP_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, SHIELD_SWEEP_CAST_TIME_TICKS, continue_func)
        return True

    @classmethod
    async def do_fighter_shield_sweep_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0) -> bool:
        SHIELD_SWEEP_COOLDOWN_TICKS = ticks_from_seconds(20)  # 20 second cooldown
        STUN_DURATION_TICKS = ticks_from_seconds(2)  # 2 second stun (shorter than bash)
        
        cooldown = Cooldown(actor, "shield_sweep", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": SHIELD_SWEEP_COOLDOWN_TICKS})
        await cooldown.start(game_tick, SHIELD_SWEEP_COOLDOWN_TICKS)
        
        # Calculate base damage based on skill level, strength, and character level
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / 10
        base_damage = (actor.skills_by_class[CharacterClassRole.FIGHTER][FighterSkills.SHIELD_SLAM] / 4) * (1 + level_mult)
        damage = max(1, base_damage + attrib_mod)  # Ensure at least 1 damage
        
        # Get all nearby enemies
        nearby_enemies = actor._location_room.get_nearby_enemies(actor)
        
        if not nearby_enemies:
            msg = f"You sweep your shield but hit nothing!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} sweeps {actor.pronoun_possessive} shield but hits nothing!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
            return True
        
        # Apply damage and stun to all nearby enemies
        for enemy in nearby_enemies:
            # Apply damage
            potential_damage = PotentialDamage(damage, DamageType.BLUDGEONING)
            enemy.take_damage(potential_damage, actor)
            
            # Apply stun
            new_state = CharacterStateStunned(enemy, cls.game_state, source_actor=actor,
                                            state_type_name="shield sweep stun", tick_created=game_tick)
            new_state.apply_state(game_tick, STUN_DURATION_TICKS)
            
            # Echo damage and stun messages
            msg = f"You sweep your shield, hitting {enemy.art_name} for {damage} damage and stunning {enemy.pronoun_objective}!"
            vars = set_vars(actor, actor, enemy, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} sweeps {actor.pronoun_possessive} shield, hitting you for {damage} damage and stunning you!"
            vars = set_vars(actor, actor, enemy, msg)
            enemy.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            
            msg = f"{actor.art_name_cap} sweeps {actor.pronoun_possessive} shield, hitting {enemy.art_name} for {damage} damage and stunning {enemy.pronoun_objective}!"
            vars = set_vars(actor, actor, enemy, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, enemy], game_state=cls.game_state)
        
        return True

    # Add to SKILL_COMMANDS:
    # {'commands': ["shield sweep", "shieldsweep", "sweep", "ss"], 'skill': FighterSkills.SHIELD_SLAM, "function": do_fighter_shield_sweep} 
