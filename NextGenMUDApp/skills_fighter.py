from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill
from .skills_interface import Skill
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
import random


class Skills_Fighter(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["normal stance", "mighty kick", "demoralizing shout", 
                        "intimidate", "slam", "bash", "cleave"]
        tier2_skills = ["disarm", "defensive stance", "rally", "shield block", 
                        "shield sweep", "rend"]
        tier3_skills = ["berserker stance", "enrage", "whirlwind"]
        tier4_skills = ["execute", "massacre"]
        
        skill_name = skill_name.lower()
        
        if skill_name in tier1_skills:
            return Skills.TIER1_MIN_LEVEL
        elif skill_name in tier2_skills:
            return Skills.TIER2_MIN_LEVEL
        elif skill_name in tier3_skills:
            return Skills.TIER3_MIN_LEVEL
        elif skill_name in tier4_skills:
            return Skills.TIER4_MIN_LEVEL
        else:
            return Skills.TIER1_MIN_LEVEL  # Default
    
    # The get_skill_by_name method can be removed as it's handled by the registry
    
    NORMAL_STANCE = Skill(
        name="normal stance",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name=None,
        cooldown_ticks=0,
        cast_time_ticks=0,
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You prepare for battle!",
        message_success_subject="You return to normal stance!",
        message_success_target=None,
        message_success_room=None,
        message_failure_subject=None,
        message_failure_target=None,
        message_failure_room=None,
        message_apply_subject=None,
        message_apply_target=None,
        message_apply_room=None,
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=Skills.do_fighter_normal_stance
    )
    
    MIGHTY_KICK = Skill(
        name="mighty kick",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="mighty_kick",
        cooldown_ticks=ticks_from_seconds(10),
        cast_time_ticks=ticks_from_seconds(0.5),
        duration_min_ticks=ticks_from_seconds(3),
        duration_max_ticks=ticks_from_seconds(6),
        message_prepare="You wind up for a kick!",
        message_success_subject="You let loose with a mighty kick!",
        message_success_target="$cap(%a%) lets loose with a mighty kick!",
        message_success_room="$cap(%a%) lets loose with a mighty kick!",
        message_failure_subject="You fumble your kick!",
        message_failure_target="$cap(%a%) fumbles %Q% kick!",
        message_failure_room="$cap(%a%) fumbles %Q% kick!",
        message_apply_subject="You kick %t% to the ground!",
        message_apply_target="$cap(%a%) kicks you to the ground!",
        message_apply_room="$cap(%a%) kicks %t% to the ground!",
        message_resist_subject="You try to kick %t%, but %r% dodges!",
        message_resist_target="$cap(%a%) tries to kick you, but you dodge!",
        message_resist_room="$cap(%a%) tries to kick %t%, but %r% dodges!",
        skill_function=Skills.do_fighter_mighty_kick
    )

    DEMORALIZING_SHOUT = Skill(
        name="demoralizing shout",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="demoralizing_shout",
        cooldown_ticks=ticks_from_seconds(15),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(5),
        duration_max_ticks=ticks_from_seconds(10),
        message_prepare="You take a deep breath...",
        message_success_subject="You let out a demoralizing shout!",
        message_success_target="$cap(%a%) lets out a demoralizing shout!",
        message_success_room="$cap(%a%) lets out a demoralizing shout!",
        message_failure_subject="You fail to muster the strength for a shout!",
        message_failure_target="$cap(%a%) fails to muster the strength for a shout!",
        message_failure_room="$cap(%a%) fails to muster the strength for a shout!",
        message_apply_subject="Your shout demoralizes %t%!",
        message_apply_target="$cap(%a%)'s shout demoralizes you!",
        message_apply_room="$cap(%a%)'s shout demoralizes %t%!",
        message_resist_subject="You try to demoralize %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to demoralize you, but you resist!",
        message_resist_room="$cap(%a%) tries to demoralize %t%, but %r% resists!",
        skill_function=Skills.do_fighter_demoralizing_shout
    )

    INTIMIDATE = Skill(
        name="intimidate",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="intimidate",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(5),
        duration_max_ticks=ticks_from_seconds(10),
        message_prepare="You prepare to intimidate your target...",
        message_success_subject="You intimidate your target!",
        message_success_target="$cap(%a%) intimidates you!",
        message_success_room="$cap(%a%) intimidates %t%!",
        message_failure_subject="You fail to intimidate your target!",
        message_failure_target="$cap(%a%) fails to intimidate you!",
        message_failure_room="$cap(%a%) fails to intimidate %t%!",
        message_apply_subject="Your intimidation reduces %t%'s combat effectiveness!",
        message_apply_target="$cap(%a%)'s intimidation reduces your combat effectiveness!",
        message_apply_room="$cap(%a%)'s intimidation reduces %t%'s combat effectiveness!",
        message_resist_subject="You try to intimidate %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to intimidate you, but you resist!",
        message_resist_room="$cap(%a%) tries to intimidate %t%, but %r% resists!",
        skill_function=Skills.do_fighter_intimidate
    )

    DISARM = Skill(
        name="disarm",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="disarm",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(5),
        duration_max_ticks=ticks_from_seconds(10),
        message_prepare="You prepare to disarm your target...",
        message_success_subject="You disarm your target!",
        message_success_target="$cap(%a%) disarms you!",
        message_success_room="$cap(%a%) disarms %t%!",
        message_failure_subject="You fail to disarm your target!",
        message_failure_target="$cap(%a%) fails to disarm you!",
        message_failure_room="$cap(%a%) fails to disarm %t%!",
        message_apply_subject="You disarm %t%!",
        message_apply_target="$cap(%a%) disarms you!",
        message_apply_room="$cap(%a%) disarms %t%!",
        message_resist_subject="You try to disarm %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to disarm you, but you resist!",
        message_resist_room="$cap(%a%) tries to disarm %t%, but %r% resists!",
        skill_function=Skills.do_fighter_disarm
    )

    SLAM = Skill(
        name="slam",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="slam",
        cooldown_ticks=ticks_from_seconds(10),
        cast_time_ticks=ticks_from_seconds(0.5),
        duration_min_ticks=ticks_from_seconds(2),
        duration_max_ticks=ticks_from_seconds(4),
        message_prepare="You prepare to slam your target...",
        message_success_subject="You slam your target!",
        message_success_target="$cap(%a%) slams you!",
        message_success_room="$cap(%a%) slams %t%!",
        message_failure_subject="You fail to slam your target!",
        message_failure_target="$cap(%a%) fails to slam you!",
        message_failure_room="$cap(%a%) fails to slam %t%!",
        message_apply_subject="You slam %t%!",
        message_apply_target="$cap(%a%) slams you!",
        message_apply_room="$cap(%a%) slams %t%!",
        message_resist_subject="You try to slam %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to slam you, but you resist!",
        message_resist_room="$cap(%a%) tries to slam %t%, but %r% resists!",
        skill_function=Skills.do_fighter_slam
    )

    BASH = Skill(
        name="bash",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="bash",
        cooldown_ticks=ticks_from_seconds(15),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(2),
        duration_max_ticks=ticks_from_seconds(4),
        message_prepare="You prepare to bash your target...",
        message_success_subject="You bash your target!",
        message_success_target="$cap(%a%) bashes you!",
        message_success_room="$cap(%a%) bashes %t%!",
        message_failure_subject="You fail to bash your target!",
        message_failure_target="$cap(%a%) fails to bash you!",
        message_failure_room="$cap(%a%) fails to bash %t%!",
        message_apply_subject="You bash %t%!",
        message_apply_target="$cap(%a%) bashes you!",
        message_apply_room="$cap(%a%) bashes %t%!",
        message_resist_subject="You try to bash %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to bash you, but you resist!",
        message_resist_room="$cap(%a%) tries to bash %t%, but %r% resists!",
        skill_function=Skills.do_fighter_bash
    )

    RALLY = Skill(
        name="rally",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="rally",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(10),
        duration_max_ticks=ticks_from_seconds(20),
        message_prepare="You prepare to rally your allies...",
        message_success_subject="You rally your allies!",
        message_success_target="$cap(%a%) rallies you!",
        message_success_room="$cap(%a%) rallies %t%!",
        message_failure_subject="You fail to rally your allies!",
        message_failure_target="$cap(%a%) fails to rally you!",
        message_failure_room="$cap(%a%) fails to rally %t%!",
        message_apply_subject="You rally %t%!",
        message_apply_target="$cap(%a%) rallies you!",
        message_apply_room="$cap(%a%) rallies %t%!",
        message_resist_subject="You try to rally %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to rally you, but you resist!",
        message_resist_room="$cap(%a%) tries to rally %t%, but %r% resists!",
        skill_function=Skills.do_fighter_rally
    )

    REND = Skill(
        name="rend",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="rend",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(5),
        duration_max_ticks=ticks_from_seconds(10),
        message_prepare="You prepare to rend your target...",
        message_success_subject="You rend your target!",
        message_success_target="$cap(%a%) rends you!",
        message_success_room="$cap(%a%) rends %t%!",
        message_failure_subject="You fail to rend your target!",
        message_failure_target="$cap(%a%) fails to rend you!",
        message_failure_room="$cap(%a%) fails to rend %t%!",
        message_apply_subject="You rend %t%!",
        message_apply_target="$cap(%a%) rends you!",
        message_apply_room="$cap(%a%) rends %t%!",
        message_resist_subject="You try to rend %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to rend you, but you resist!",
        message_resist_room="$cap(%a%) tries to rend %t%, but %r% resists!",
        skill_function=Skills.do_fighter_rend
    )

    CLEAVE = Skill(
        name="cleave",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="cleave",
        cooldown_ticks=ticks_from_seconds(15),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You prepare to cleave through your enemies...",
        message_success_subject="You cleave through your enemies!",
        message_success_target="$cap(%a%) cleaves through you!",
        message_success_room="$cap(%a%) cleaves through %t%!",
        message_failure_subject="You fail to cleave through your enemies!",
        message_failure_target="$cap(%a%) fails to cleave through you!",
        message_failure_room="$cap(%a%) fails to cleave through %t%!",
        message_apply_subject="You cleave through %t%!",
        message_apply_target="$cap(%a%) cleaves through you!",
        message_apply_room="$cap(%a%) cleaves through %t%!",
        message_resist_subject="You try to cleave through %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to cleave through you, but you resist!",
        message_resist_room="$cap(%a%) tries to cleave through %t%, but %r% resists!",
        skill_function=Skills.do_fighter_cleave
    )

    WHIRLWIND = Skill(
        name="whirlwind",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="whirlwind",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(1.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You prepare to whirlwind through your enemies...",
        message_success_subject="You whirlwind through your enemies!",
        message_success_target="$cap(%a%) whirlwinds through you!",
        message_success_room="$cap(%a%) whirlwinds through %t%!",
        message_failure_subject="You fail to whirlwind through your enemies!",
        message_failure_target="$cap(%a%) fails to whirlwind through you!",
        message_failure_room="$cap(%a%) fails to whirlwind through %t%!",
        message_apply_subject="You whirlwind through %t%!",
        message_apply_target="$cap(%a%) whirlwinds through you!",
        message_apply_room="$cap(%a%) whirlwinds through %t%!",
        message_resist_subject="You try to whirlwind through %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to whirlwind through you, but you resist!",
        message_resist_room="$cap(%a%) tries to whirlwind through %t%, but %r% resists!",
        skill_function=Skills.do_fighter_whirlwind
    )

    EXECUTE = Skill(
        name="execute",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="execute",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You prepare to execute your target...",
        message_success_subject="You execute your target!",
        message_success_target="$cap(%a%) executes you!",
        message_success_room="$cap(%a%) executes %t%!",
        message_failure_subject="You fail to execute your target!",
        message_failure_target="$cap(%a%) fails to execute you!",
        message_failure_room="$cap(%a%) fails to execute %t%!",
        message_apply_subject="You execute %t%!",
        message_apply_target="$cap(%a%) executes you!",
        message_apply_room="$cap(%a%) executes %t%!",
        message_resist_subject="You try to execute %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to execute you, but you resist!",
        message_resist_room="$cap(%a%) tries to execute %t%, but %r% resists!",
        skill_function=Skills.do_fighter_execute
    )

    ENRAGE = Skill(
        name="enrage",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="enrage",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(10),
        duration_max_ticks=ticks_from_seconds(20),
        message_prepare="You prepare to enrage yourself...",
        message_success_subject="You enrage yourself!",
        message_success_target="$cap(%a%) enrages %Q%self!",
        message_success_room="$cap(%a%) enrages %Q%self!",
        message_failure_subject="You fail to enrage yourself!",
        message_failure_target="$cap(%a%) fails to enrage %Q%self!",
        message_failure_room="$cap(%a%) fails to enrage %Q%self!",
        message_apply_subject="You are enraged!",
        message_apply_target="$cap(%a%) is enraged!",
        message_apply_room="$cap(%a%) is enraged!",
        message_resist_subject="You try to enrage yourself, but fail!",
        message_resist_target="$cap(%a%) tries to enrage %Q%self, but fails!",
        message_resist_room="$cap(%a%) tries to enrage %Q%self, but fails!",
        skill_function=Skills.do_fighter_enrage
    )

    MASSACRE = Skill(
        name="massacre",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="massacre",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You focus on your massacre...",
        message_success_subject="You let loose with a devastating massacre!",
        message_success_target="$cap(%a%) lets loose with a devastating massacre!",
        message_success_room="$cap(%a%) lets loose with a devastating massacre!",
        message_failure_subject="You lose your focus and fail to massacre!",
        message_failure_target="$cap(%a%) loses %Q% focus and fails to massacre!",
        message_failure_room="$cap(%a%) loses %Q% focus and fails to massacre!",
        message_apply_subject="You massacre %t%!",
        message_apply_target="$cap(%a%) massacres you!",
        message_apply_room="$cap(%a%) massacres %t%!",
        message_resist_subject="You try to massacre %t%, but %r% resists!",
        message_resist_target="$cap(%a%) tries to massacre you, but you resist!",
        message_resist_room="$cap(%a%) tries to massacre %t%, but %r% resists!",
        skill_function=Skills.do_fighter_massacre
    )

    SHIELD_BLOCK = Skill(
        name="shield block",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="shield_block",
        cooldown_ticks=ticks_from_seconds(15),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(5),
        duration_max_ticks=ticks_from_seconds(10),
        message_prepare="You raise your shield to block!",
        message_success_subject="You raise your shield to block!",
        message_success_target="$cap(%a%) raises %Q% shield to block!",
        message_success_room="$cap(%a%) raises %Q% shield to block!",
        message_failure_subject="You fail to raise your shield in time!",
        message_failure_target="$cap(%a%) fails to raise %Q% shield in time!",
        message_failure_room="$cap(%a%) fails to raise %Q% shield in time!",
        message_apply_subject="Your shield blocks incoming attacks!",
        message_apply_target="$cap(%a%)'s shield blocks incoming attacks!",
        message_apply_room="$cap(%a%)'s shield blocks incoming attacks!",
        message_resist_subject="You try to block with your shield, but fail!",
        message_resist_target="$cap(%a%) tries to block with %Q% shield, but fails!",
        message_resist_room="$cap(%a%) tries to block with %Q% shield, but fails!",
        skill_function=Skills.do_fighter_shield_block
    )

    SHIELD_SWEEP = Skill(
        name="shield sweep",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="shield_sweep",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(2),
        duration_max_ticks=ticks_from_seconds(4),
        message_prepare="You prepare to sweep with your shield...",
        message_success_subject="You sweep with your shield!",
        message_success_target="$cap(%a%) sweeps with %Q% shield!",
        message_success_room="$cap(%a%) sweeps with %Q% shield!",
        message_failure_subject="You fail to sweep with your shield!",
        message_failure_target="$cap(%a%) fails to sweep with %Q% shield!",
        message_failure_room="$cap(%a%) fails to sweep with %Q% shield!",
        message_apply_subject="You sweep %t% with your shield!",
        message_apply_target="$cap(%a%) sweeps you with %Q% shield!",
        message_apply_room="$cap(%a%) sweeps %t% with %Q% shield!",
        message_resist_subject="You try to sweep %t% with your shield, but %r% resists!",
        message_resist_target="$cap(%a%) tries to sweep you with %Q% shield, but you resist!",
        message_resist_room="$cap(%a%) tries to sweep %t% with %Q% shield, but %r% resists!",
        skill_function=Skills.do_fighter_shield_sweep
    )

    BERSERKER_STANCE = Skill(
        name="berserker stance",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="berserker_stance",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(10),
        duration_max_ticks=ticks_from_seconds(20),
        message_prepare="You prepare to enter berserker stance...",
        message_success_subject="You enter berserker stance!",
        message_success_target="$cap(%a%) enters berserker stance!",
        message_success_room="$cap(%a%) enters berserker stance!",
        message_failure_subject="You fail to enter berserker stance!",
        message_failure_target="$cap(%a%) fails to enter berserker stance!",
        message_failure_room="$cap(%a%) fails to enter berserker stance!",
        message_apply_subject="You are in berserker stance!",
        message_apply_target="$cap(%a%) is in berserker stance!",
        message_apply_room="$cap(%a%) is in berserker stance!",
        message_resist_subject="You try to enter berserker stance, but fail!",
        message_resist_target="$cap(%a%) tries to enter berserker stance, but fails!",
        message_resist_room="$cap(%a%) tries to enter berserker stance, but fails!",
        skill_function=Skills.do_fighter_berserker_stance
    )

    DEFENSIVE_STANCE = Skill(
        name="defensive stance",
        base_class=CharacterClassRole.FIGHTER,
        cooldown_name="defensive_stance",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(10),
        duration_max_ticks=ticks_from_seconds(20),
        message_prepare="You prepare to enter defensive stance...",
        message_success_subject="You enter defensive stance!",
        message_success_target="$cap(%a%) enters defensive stance!",
        message_success_room="$cap(%a%) enters defensive stance!",
        message_failure_subject="You fail to enter defensive stance!",
        message_failure_target="$cap(%a%) fails to enter defensive stance!",
        message_failure_room="$cap(%a%) fails to enter defensive stance!",
        message_apply_subject="You are in defensive stance!",
        message_apply_target="$cap(%a%) is in defensive stance!",
        message_apply_room="$cap(%a%) is in defensive stance!",
        message_resist_subject="You try to enter defensive stance, but fail!",
        message_resist_target="$cap(%a%) tries to enter defensive stance, but fails!",
        message_resist_room="$cap(%a%) tries to enter defensive stance, but fails!",
        skill_function=Skills.do_fighter_defensive_stance
    )

    @classmethod
    async def do_fighter_normal_stance(cls, actor: Actor, target: Actor, 
                                      difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.NORMAL_STANCE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_normal_stance_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_normal_stance_finish(cls, actor: Actor, target: Actor, 
                                             difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.NORMAL_STANCE
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        
        changed = False
        if actor.has_state(CharacterStateBerserkerStance):
            actor.remove_state(CharacterStateBerserkerStance)
            changed = True
        if actor.has_state(CharacterStateDefensiveStance):
            actor.remove_state(CharacterStateDefensiveStance)
            changed = True
            
        if changed:
            send_success_message(actor, [actor], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [actor], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_defensive_stance(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DEFENSIVE_STANCE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_defensive_stance_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_defensive_stance_finish(cls, actor: Actor, target: Actor, 
                                                difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DEFENSIVE_STANCE
        DEFENSIVE_STANCE_DODGE_BONUS = 10
        DEFENSIVE_STANCE_RESIST_AMOUNT = 5
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        dodge_bonus = DEFENSIVE_STANCE_DODGE_BONUS * level_mult
        resist_amount = DEFENSIVE_STANCE_RESIST_AMOUNT * level_mult
        resistances = DamageResistances({
            DamageType.SLASHING: resist_amount,
            DamageType.PIERCING: resist_amount,
            DamageType.BLUDGEONING: resist_amount,
            DamageType.FIRE: resist_amount / 3,
            DamageType.COLD: resist_amount / 3,
            DamageType.LIGHTNING: resist_amount / 3,
            DamageType.ACID: resist_amount / 3,
        })
        attrib_mod = (actor.attributes_[CharacterAttributes.CONSTITUTION] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.DEFENSIVE_STANCE],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateDodgeBonus(actor, actor, "defensive stance", dodge_bonus, tick_created=game_tick)
            new_state.apply_state(game_tick)
            new_state = CharacterStateShielded(actor, actor, "defensive stance", resistances, tick_created=game_tick)
            new_state.apply_state(game_tick)
            send_success_message(actor, [actor], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [actor], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_shield_block(cls, actor: Actor, target: Actor, 
                                     difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SHIELD_BLOCK
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_shield_block_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_shield_block_finish(cls, actor: Actor, target: Actor, 
                                            difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SHIELD_BLOCK
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        resist_amount = actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.SHIELD_BLOCK] / 5
        resistances = DamageResistances({
            DamageType.SLASHING: resist_amount,
            DamageType.PIERCING: resist_amount,
            DamageType.BLUDGEONING: resist_amount,
            DamageType.FIRE: resist_amount / 3,
            DamageType.COLD: resist_amount / 3,
            DamageType.LIGHTNING: resist_amount / 3,
            DamageType.ACID: resist_amount / 3,
        })
        attrib_mod = (actor.attributes_[CharacterAttributes.CONSTITUTION] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.SHIELD_BLOCK],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateShielded(actor, actor, "shielded", resistances, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, [actor], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [actor], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_shield_sweep(cls, actor: Actor, target: Actor, 
                                     difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SHIELD_SWEEP
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_shield_sweep_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_shield_sweep_finish(cls, actor: Actor, target: Actor, 
                                            difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SHIELD_SWEEP
        SHIELD_SWEEP_DAMAGE_MIN = 5
        SHIELD_SWEEP_DAMAGE_MAX = 15
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        damage = random.randint(SHIELD_SWEEP_DAMAGE_MIN, SHIELD_SWEEP_DAMAGE_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.SHIELD_SWEEP],
                              difficulty_modifier - attrib_mod):
            # Get all nearby enemies
            targets = actor.room.get_nearby_enemies(actor)
            if not targets:
                send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
                return False
            # Hit all targets
            for target in targets:
                new_state = CharacterStateStunned(target, actor, "shield swept", tick_created=game_tick)
                new_state.apply_state(game_tick, duration)
                vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=damage)
                target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            send_success_message(actor, targets, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_mighty_kick(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.MIGHTY_KICK
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_mighty_kick_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_mighty_kick_finish(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.MIGHTY_KICK
        kick_duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) \
            * actor.levels[CharacterClassRole.FIGHTER] / target.total_levels()
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = roll_dice(target.dodge_dice_number_, target.dodge_dice_size_, target.dodge_dice_modifier_)
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        skill_roll = random.randint(1, 100)
        
        if success_by := check_skill_roll(skill_roll, actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK],
                              difficulty_modifier - attrib_mod) >= 0:
            send_success_message(actor, [target], THIS_SKILL_DATA, vars)
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)    
            return False
        if does_resist(actor, actor.attributes_[CharacterAttributes.STRENGTH],
                       actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK].skill_level, 
                       target, target.attributes_[CharacterAttributes.STRENGTH], difficulty_modifier):
            send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
            return False
        else:
            send_apply_message(actor, [target], THIS_SKILL_DATA, vars)
            new_state = CharacterStateForcedSitting(target, actor, "kicked", tick_created=game_tick)
            new_state.apply_state(game_tick, kick_duration)
            send_success_message(actor, [target], THIS_SKILL_DATA, vars)
            return True

    @classmethod
    async def do_fighter_demoralizing_shout(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DEMORALIZING_SHOUT
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        if success_by := check_skill_roll(skill_roll, actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK],
                              difficulty_modifier - attrib_mod) >= 0:
            send_success_message(actor, [target], THIS_SKILL_DATA, vars)
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)    
            return False
        continue_func = lambda: cls.do_fighter_demoralizing_shout_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_demoralizing_shout_finish(cls, actor: Actor, target: Actor, 
                                                 difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DEMORALIZING_SHOUT
        DEMORALIZING_SHOUT_HIT_PENALTY_MIN = 10
        DEMORALIZING_SHOUT_HIT_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        hit_penalty = random.randint(DEMORALIZING_SHOUT_HIT_PENALTY_MIN, DEMORALIZING_SHOUT_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        targets = actor.room.get_nearby_enemies(actor)
        skill_roll = random.randint(1, 100)
        if success_by := check_skill_roll(skill_roll, actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK],
                              difficulty_modifier - attrib_mod) >= 0:
            send_success_message(actor, targets, THIS_SKILL_DATA, vars)
        else:
            send_failure_message(actor, targets, THIS_SKILL_DATA, vars)    
            return False
        for target in targets:
            if does_resist(actor, actor.attributes_[CharacterAttributes.STRENGTH],
                        actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MIGHTY_KICK].skill_level, 
                        target, target.attributes_[CharacterAttributes.WISDOM], difficulty_modifier):
                send_resist_message(actor, [target], THIS_SKILL_DATA, vars)
            else:
                send_apply_message(actor, [target], THIS_SKILL_DATA, vars)
                new_state = CharacterStateHitPenalty(target, actor, "demoralized", hit_penalty, tick_created=game_tick)
                new_state.apply_state(game_tick, duration)
                send_success_message(actor, [target], THIS_SKILL_DATA, vars)
        return True

    @classmethod
    async def do_fighter_intimidate(cls, actor: Actor, target: Actor, 
                                   difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.INTIMIDATE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_intimidate_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_intimidate_finish(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.INTIMIDATE
        INTIMIDATE_HIT_PENALTY_MIN = 10
        INTIMIDATE_HIT_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        hit_penalty = random.randint(INTIMIDATE_HIT_PENALTY_MIN, INTIMIDATE_HIT_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        targets = actor.room.get_nearby_enemies(actor)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.INTIMIDATE],
                              difficulty_modifier - attrib_mod + target_mod):
            for target in targets:
                new_state = CharacterStateHitPenalty(target, actor, "intimidated", hit_penalty, tick_created=game_tick)
                new_state.apply_state(game_tick, duration)
            send_success_message(actor, targets, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, targets, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_disarm(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DISARM
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_disarm_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_disarm_finish(cls, actor: Actor, target: Actor, 
                                       difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.DISARM
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.WISDOM] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.DISARM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateForcedSitting(target, actor, "disarmed", tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, target, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, target, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_slam(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SLAM
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_slam_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_slam_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.SLAM
        SLAM_DODGE_PENALTY_MIN = 10
        SLAM_DODGE_PENALTY_MAX = 40
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        dodge_penalty = random.randint(SLAM_DODGE_PENALTY_MIN, SLAM_DODGE_PENALTY_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.SLAM],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateDodgePenalty(target, actor, "slammed", dodge_penalty, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, target, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, target, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_bash(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.BASH
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_bash_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_bash_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.BASH
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.DEXTERITY] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.BASH],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateStunned(target, actor, "bashed", tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, target, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, target, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_rally(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.RALLY
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_rally_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_rally_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.RALLY
        RALLY_HIT_BONUS_MIN = 5
        RALLY_HIT_BONUS_MAX = 20
        RALLY_DAMAGE_BONUS_MIN = 5
        RALLY_DAMAGE_BONUS_MAX = 20
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        hit_bonus = random.randint(RALLY_HIT_BONUS_MIN, RALLY_HIT_BONUS_MAX) * level_mult
        damage_bonus = random.randint(RALLY_DAMAGE_BONUS_MIN, RALLY_DAMAGE_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.CHARISMA] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        targets = actor.room.get_nearby_allies(actor)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.RALLY],
                              difficulty_modifier - attrib_mod):
            for target in targets:
                new_state = CharacterStateHitBonus(target, actor, "rallied", hit_bonus, tick_created=game_tick)
                new_state.apply_state(game_tick, duration)
                new_state = CharacterStateDamageBonus(target, actor, "rallied", damage_bonus, tick_created=game_tick)
                new_state.apply_state(game_tick, duration)
            send_success_message(actor, targets, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, targets, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_rend(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.REND
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_rend_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_rend_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.REND
        REND_DAMAGE_MIN = 5
        REND_DAMAGE_MAX = 15
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        damage = random.randint(REND_DAMAGE_MIN, REND_DAMAGE_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        target_mod = (target.attributes_[CharacterAttributes.CONSTITUTION] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.REND],
                              difficulty_modifier - attrib_mod + target_mod):
            new_state = CharacterStateBleeding(target, actor, "rended", damage, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, target, THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, target, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_cleave(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.CLEAVE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_cleave_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_cleave_finish(cls, actor: Actor, target: Actor, 
                                      difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.CLEAVE
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.CLEAVE],
                              difficulty_modifier - attrib_mod):
            # Get all nearby enemies
            targets = actor.room.get_nearby_enemies(actor)
            if len(targets) < 2:
                send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
                return False
            # Hit the first two targets
            for i in range(min(2, len(targets))):
                target = targets[i]
                if actor.equipped[EquipLocation.MAIN_HAND] != None:
                    weapon = actor.equipped[EquipLocation.MAIN_HAND]
                    attack_data = AttackData(
                        damage_type=weapon.damage_type,
                        damage_num_dice=weapon.damage_num_dice,
                        damage_dice_size=weapon.damage_dice_size,
                        damage_bonus=weapon.damage_bonus,
                        attack_verb=weapon.damage_type.verb(),
                        attack_noun=weapon.damage_type.noun(),
                        attack_bonus=weapon.attack_bonus
                    )
                    base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, attack_data)
                    final_damage = base_damage * actor.num_main_hand_attacks
                    vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                    target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
                else:
                    for natural_attack in actor.natural_attacks:
                        base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, natural_attack)
                        final_damage = base_damage * actor.num_main_hand_attacks
                        vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                        target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            send_success_message(actor, targets[:2], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_whirlwind(cls, actor: Actor, target: Actor, 
                                  difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.WHIRLWIND
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_whirlwind_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_whirlwind_finish(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.WHIRLWIND
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)

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

        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.WHIRLWIND], difficulty_modifier):
            # Success message
            target_names = ", ".join([t.art_name for t in targets])
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_subject)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_subject, vars, cls.game_state)
            
            # Hit each target with one attack multiplied by number of main hand attacks
            total_dmgs = defaultdict(int)
            
            if actor.equipped[EquipLocation.MAIN_HAND] != None:
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
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
                    final_damage = base_damage * actor.num_main_hand_attacks
                    total_dmgs[t] = final_damage
                    # Message to the target
                    vars = set_vars(actor, actor, t, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                    t.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            else:
                # Natural attacks
                for natural_attack in actor.natural_attacks:
                    for t in targets:
                        # Each target gets hit once, but damage is multiplied by number of attacks
                        base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, t, natural_attack)
                        final_damage = base_damage * actor.num_main_hand_attacks
                        total_dmgs[t] = final_damage
                        # Message to the target
                        vars = set_vars(actor, actor, t, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                        t.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
        
            # Message to others in the room
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_room)
            actor._location_room.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_room, vars, cls.game_state, exceptions=targets)
            return True
        else:
            send_failure_message(actor, targets, THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_execute(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.EXECUTE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_execute_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_execute_finish(cls, actor: Actor, target: Actor, 
                                       difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.EXECUTE
        # Check if target is below 25% health
        if target.current_hit_points > target.max_hit_points * 0.25:
            msg = f"Your target is not weak enough to execute!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False

        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.EXECUTE],
                              difficulty_modifier - attrib_mod):
            if actor.equipped[EquipLocation.MAIN_HAND] != None:
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
                attack_data = AttackData(
                    damage_type=weapon.damage_type,
                    damage_num_dice=weapon.damage_num_dice,
                    damage_dice_size=weapon.damage_dice_size,
                    damage_bonus=weapon.damage_bonus,
                    attack_verb=weapon.damage_type.verb(),
                    attack_noun=weapon.damage_type.noun(),
                    attack_bonus=weapon.attack_bonus
                )
                base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, attack_data)
                final_damage = base_damage * actor.num_main_hand_attacks * 2  # Double damage for execute
                vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            else:
                for natural_attack in actor.natural_attacks:
                    base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, natural_attack)
                    final_damage = base_damage * actor.num_main_hand_attacks * 2  # Double damage for execute
                    vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                    target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            send_success_message(actor, [target], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_enrage(cls, actor: Actor, target: Actor, 
                               difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.ENRAGE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_enrage_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_enrage_finish(cls, actor: Actor, target: Actor, 
                                       difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.ENRAGE
        ENRAGE_DAMAGE_BONUS_MIN = 20
        ENRAGE_DAMAGE_BONUS_MAX = 50
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        duration = random.randint(THIS_SKILL_DATA.duration_min_ticks, THIS_SKILL_DATA.duration_max_ticks) * level_mult
        damage_bonus = random.randint(ENRAGE_DAMAGE_BONUS_MIN, ENRAGE_DAMAGE_BONUS_MAX) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.ENRAGE],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateDamageBonus(actor, actor, "enraged", damage_bonus, tick_created=game_tick)
            new_state.apply_state(game_tick, duration)
            send_success_message(actor, [actor], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [actor], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_massacre(cls, actor: Actor, target: Actor, 
                                 difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.MASSACRE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_massacre_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_massacre_finish(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.MASSACRE
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.MASSACRE],
                              difficulty_modifier - attrib_mod):
            if actor.equipped[EquipLocation.MAIN_HAND] != None:
                weapon = actor.equipped[EquipLocation.MAIN_HAND]
                attack_data = AttackData(
                    damage_type=weapon.damage_type,
                    damage_num_dice=weapon.damage_num_dice,
                    damage_dice_size=weapon.damage_dice_size,
                    damage_bonus=weapon.damage_bonus,
                    attack_verb=weapon.damage_type.verb(),
                    attack_noun=weapon.damage_type.noun(),
                    attack_bonus=weapon.attack_bonus
                )
                base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, attack_data)
                final_damage = base_damage * actor.num_main_hand_attacks * 3  # Triple damage for massacre
                vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            else:
                for natural_attack in actor.natural_attacks:
                    base_damage = await CoreActionsInterface.get_instance().do_single_attack(actor, target, natural_attack)
                    final_damage = base_damage * actor.num_main_hand_attacks * 3  # Triple damage for massacre
                    vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_success_target, damage=final_damage)
                    target.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_success_target, vars, cls.game_state)
            send_success_message(actor, [target], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [target], THIS_SKILL_DATA, vars)
            return False

    @classmethod
    async def do_fighter_berserker_stance(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.BERSERKER_STANCE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        continue_func = lambda: cls.do_fighter_berserker_stance_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True

    @classmethod
    async def do_fighter_berserker_stance_finish(cls, actor: Actor, target: Actor, 
                                                 difficulty_modifier=0, game_tick=0) -> bool:
        THIS_SKILL_DATA = Skills_Fighter.BERSERKER_STANCE
        BERSERKER_STANCE_DODGE_PENALTY = 10
        BERSERKER_STANCE_HIT_BONUS = 20
        level_mult = actor.levels_[CharacterClassRole.FIGHTER] / target.total_levels_()
        skill_mod = actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.BERSERKER_STANCE] / 5
        dodge_mod = BERSERKER_STANCE_DODGE_PENALTY * level_mult
        hit_mod = (BERSERKER_STANCE_HIT_BONUS - skill_mod) * level_mult
        attrib_mod = (actor.attributes_[CharacterAttributes.STRENGTH] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        cooldown = Cooldown(actor, THIS_SKILL_DATA.cooldown_name, cls.game_state, cooldown_source=actor, cooldown_vars=None)
        await cooldown.start(game_tick, THIS_SKILL_DATA.cooldown_ticks)
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.FIGHTER][Skills_Fighter.BERSERKER_STANCE],
                              difficulty_modifier - attrib_mod):
            new_state = CharacterStateBerserkerStance(actor, actor, "berserker stance", dodge_mod, hit_mod, tick_created=game_tick)
            new_state.apply_state(game_tick)
            send_success_message(actor, [actor], THIS_SKILL_DATA, vars)
            return True
        else:
            send_failure_message(actor, [actor], THIS_SKILL_DATA, vars)
            return False

    def __str__(self):
        return self.name.replace("_", " ").title()
