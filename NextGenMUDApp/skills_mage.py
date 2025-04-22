from .skills_core import Skills
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation
from .nondb_models.actor_states import (
    CharacterStateShielded, Cooldown
)
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageResistances
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds
from .core_actions_interface import CoreActionsInterface

class Skills_Mage(Skills):
    @classmethod
    async def do_spell_fizzle(actor: Actor, target: Actor, spell_name: str, vars: dict=None,
                               game_state: 'ComprehensiveGameState'=None):
        msg = f"Your {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, game_state)
        msg = f"{actor.art_name_cap}'s {spell_name} spell fizzles!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=game_state)

    @classmethod
    async def do_mage_cast_fireball(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                    difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        FIREBALL_CAST_TIME_TICKS = ticks_from_seconds(1.0)
        
        if actor.cooldowns.has_cooldown(actor, "fireball"):
            msg = f"You can't cast fireball again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_fireball_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You start to cast fireball!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} starts to cast fireball!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            msg = f"{actor.art_name_cap} starts to cast a spell!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: not target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            actor.recovers_at += FIREBALL_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, FIREBALL_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_fireball_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                   difficulty_modifier=0, game_tick=0) -> bool:
        FIREBALL_DMG_DICE_LEVEL_MULT = 1/4
        FIREBALL_DMG_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * FIREBALL_DMG_DICE_LEVEL_MULT
        FIREBALL_DMG_DICE_SIZE = 6
        FIREBALL_COOLDOWN_TICKS = ticks_from_seconds(30)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        FIREBALL_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 8

        cooldown = Cooldown(actor, "fireball", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": FIREBALL_COOLDOWN_TICKS})
        await cooldown.start(game_tick, FIREBALL_COOLDOWN_TICKS)

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
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
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
            await cls.do_spell_fizzle(actor, target, "fireball", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_magic_missile(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                         difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        MAGIC_MISSILE_CAST_TIME_TICKS = ticks_from_seconds(0.5)
        
        if actor.cooldowns.has_cooldown(actor, "magic_missile"):
            msg = f"You can't cast magic missile again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_magic_missile_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You start to cast magic missile!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} starts to cast magic missile!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            msg = f"{actor.art_name_cap} starts to cast a spell!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: not target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            actor.recovers_at += MAGIC_MISSILE_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, MAGIC_MISSILE_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_magic_missile_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                               difficulty_modifier=0, game_tick=0) -> bool:
        MAGIC_MISSILE_DMG_DICE_LEVEL_MULT = 1/4
        MAGIC_MISSILE_DICE_NUM = actor.levels_[CharacterClassRole.MAGE] * MAGIC_MISSILE_DMG_DICE_LEVEL_MULT
        MAGIC_MISSILE__DMG_DICE_SIZE = 6
        MAGIC_MISSILE_COOLDOWN_TICKS = ticks_from_seconds(10)
        
        attrib_mod = (actor.attributes_[CharacterAttributes.INTELLIGENCE] - Skills.ATTRIBUTE_AVERAGE) \
            * Skills.ATTRIBUTE_SKILL_MODIFIER_PER_POINT
        MAGIC_MISSILE_DMG_BONUS = attrib_mod * actor.levels_[CharacterClassRole.MAGE] / 4

        cooldown = Cooldown(actor, "magic_missile", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": MAGIC_MISSILE_COOLDOWN_TICKS})
        await cooldown.start(game_tick, MAGIC_MISSILE_COOLDOWN_TICKS)

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
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.ARCANE)
            return True
        else:
            await cls.do_spell_fizzle(actor, target, "magic missile", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_light(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting light is not yet implemented!", cls.game_state)
        pass

    @classmethod
    async def do_mage_cast_arcane_barrier(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                  difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        ARCANE_BARRIER_CAST_TIME_TICKS = ticks_from_seconds(0.25)
        
        if actor.cooldowns.has_cooldown(actor, "arcane_barrier"):
            msg = f"You can't cast arcane barrier again yet!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_mage_cast_arcane_barrier_finish(actor, target, skill, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            continue_func()
        else:
            msg = f"You start to cast arcane barrier!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} starts to cast arcane barrier!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            msg = f"{actor.art_name_cap} starts to cast a spell!"
            vars = set_vars(actor, actor, target, msg)
            filter_fn = lambda target: not target.has_class(CharacterClassRole.MAGE)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor],
                                      game_state=cls.game_state, filter_fn=filter_fn)
            actor.recovers_at += ARCANE_BARRIER_CAST_TIME_TICKS
            await cls.start_casting(actor, skill, ARCANE_BARRIER_CAST_TIME_TICKS, continue_func)
        return True
    
    @classmethod
    async def do_mage_cast_arcane_barrier_finish(cls, actor: Actor, target: Actor, skill: CharacterSkill,
                                         difficulty_modifier=0, game_tick=0) -> bool:
        DAMAGE_REDUCTION_AMOUNT = actor.levels_[CharacterClassRole.MAGE]
        ARCANE_BARRIER_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        cooldown = Cooldown(actor, "arcane_barrier", cls.game_state, cooldown_source=actor, cooldown_vars={"duration": ARCANE_BARRIER_COOLDOWN_TICKS})
        await cooldown.start(game_tick, ARCANE_BARRIER_COOLDOWN_TICKS)
        
        if cls.do_skill_check(actor, actor.skills_by_class[CharacterClassRole.MAGE][MageSkills.CAST_ARCANE_BARRIER],
                              difficulty_modifier):
            msg = f"You cast arcane barrier on yourself!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts arcane barrier on you! You feel shielded!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} casts arcane barrier on {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor,target], game_state=cls.game_state)
            reductions = DamageReduction(reductions_by_type={
                DamageType.BLUDGEONING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.PIERCING: DAMAGE_REDUCTION_AMOUNT,
                DamageType.SLASHING: DAMAGE_REDUCTION_AMOUNT
            })
            new_state = CharacterStateShielded(target, actor, "magic barrier", resistances=None, reductions=reductions,
                                               tick_created=game_tick)
            new_state.apply_state(game_tick, 0)
            return True
        else:
            await cls.do_spell_fizzle(actor, target, "arcane barrier", cls.game_state)
            return False

    @classmethod
    async def do_mage_cast_sleep(cls, actor: Actor, target: Actor, skill: CharacterSkill, difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Casting sleep is not yet implemented!", cls.game_state) 