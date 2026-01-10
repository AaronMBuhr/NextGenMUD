from .basic_types import GenericEnumWithAttributes
from .skills_core import Skills, ClassSkills, Skill, SkillType, SkillAICondition
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes, EquipLocation
from .nondb_models.actor_states import (
    CharacterStateForcedSitting, CharacterStateHitPenalty, CharacterStateStunned,
    CharacterStateDodgeBonus, CharacterStateShielded, CharacterStateDamageBonus,
    CharacterStateBleeding, CharacterStateHitBonus, CharacterStateArmorBonus, 
    CharacterStateRegenerating, CharacterStateZealotry, CharacterStateConsecrated, Cooldown
)
from .core_actions_interface import CoreActionsInterface
from .nondb_models.attacks_and_damage import DamageType, DamageReduction, DamageMultipliers
# CharacterSkill import removed - not used in this file
from .constants import CharacterClassRole
from .communication import CommTypes
from .utility import roll_dice, set_vars, ticks_from_seconds, firstcap
import random

        # CharacterClassRole.CLERIC: {
        #     # Tier 1 (Levels 1-9)
        #     ClericSkills.CURE_LIGHT_WOUNDS: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.BLESS: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.DIVINE_FAVOR: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.RADIANT_LIGHT: SkillsInterface.TIER1_MIN_LEVEL,
        #     ClericSkills.SANCTUARY: SkillsInterface.TIER1_MIN_LEVEL,
            
        #     # Tier 2 (Levels 10-19)
        #     ClericSkills.CURE_MODERATE_WOUNDS: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.REMOVE_CURSE: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.DIVINE_PROTECTION: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.SMITE: SkillsInterface.TIER2_MIN_LEVEL,
        #     ClericSkills.DIVINE_GUIDANCE: SkillsInterface.TIER2_MIN_LEVEL
        # },
        # CharacterClassRole.WARPRIEST: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.WARPRIEST_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Cleric specialization: Restorer (Tiers 3-7)
        # CharacterClassRole.RESTORER: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.RESTORER_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # },
        
        # # Cleric specialization: Ritualist (Tiers 3-7)
        # CharacterClassRole.RITUALIST: {
        #     # Tier 3 (Levels 20-29)
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.CLEAVE: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.REND: SkillsInterface.TIER3_MIN_LEVEL,
        #     ClericSkills.DEMORALIZING_SHOUT: SkillsInterface.TIER3_MIN_LEVEL,
            
        #     # Tier 4 (Levels 30-39)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER4_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER4_MIN_LEVEL,
            
        #     # Tier 5 (Levels 40-49)
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER5_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER5_MIN_LEVEL,
            
        #     # Tier 6 (Levels 50-59)
        #     ClericSkills.RITUALIST_STANCE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.WHIRLWIND: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.MASSACRE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.ENRAGE: SkillsInterface.TIER6_MIN_LEVEL,
        #     ClericSkills.EXECUTE: SkillsInterface.TIER6_MIN_LEVEL,
            
        #     # Tier 7 (Level 60)
        #     ClericSkills.MASSACRE: SkillsInterface.TIER7_MIN_LEVEL
        # }



class Skills_Cleric(Skills):
    @classmethod
    async def do_cleric_cure_light_wounds(cls, actor: Actor, target: Actor, 
                                         difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure light wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_serious_wounds(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure serious wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_critical_wounds(cls, actor: Actor, target: Actor, 
                                            difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure critical wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_heal(cls, actor: Actor, target: Actor, 
                            difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast heal on self or target, restoring hit points."""
        THIS_SKILL_DATA = ClericSkills.HEAL
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        # Default to self if no target
        if target is None:
            target = actor
            
        continue_func = lambda: cls.do_cleric_heal_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_heal_finish(cls, actor: Actor, target: Actor, 
                                   difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the heal spell, restoring hit points."""
        HEAL_DICE_NUM = 2
        HEAL_DICE_SIZE = 8
        HEAL_BASE_BONUS = 5
        HEAL_PER_LEVEL = 1.5
        HEAL_COOLDOWN_TICKS = ticks_from_seconds(8)
        
        # Calculate healing based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        heal_bonus = int(HEAL_BASE_BONUS + (cleric_level * HEAL_PER_LEVEL))
        heal_amount = roll_dice(HEAL_DICE_NUM, HEAL_DICE_SIZE) + heal_bonus
        
        cooldown = Cooldown(actor, "heal", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": HEAL_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, HEAL_COOLDOWN_TICKS)

        # Apply healing
        old_hp = target.current_hit_points
        target.current_hit_points = min(target.max_hit_points, target.current_hit_points + heal_amount)
        actual_heal = int(target.current_hit_points - old_hp)
        
        # Send messages
        if target == actor:
            msg = f"Divine energy washes over you, healing {actual_heal} hit points!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"Divine energy washes over {actor.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        else:
            msg = f"You channel divine energy into {target.art_name}, healing {actual_heal} hit points!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} channels divine energy into you, healing {actual_heal} hit points!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} channels divine energy into {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
        
        # Send status update to target if they're a PC
        from .nondb_models.character_interface import PermanentCharacterFlags
        if target.has_perm_flags(PermanentCharacterFlags.IS_PC):
            await target.send_status_update()
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.HEAL)
        return True

    @classmethod
    async def do_cleric_smite(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast smite on target, dealing holy damage with bonus vs undead."""
        THIS_SKILL_DATA = ClericSkills.SMITE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        if target is None:
            msg = "Who do you want to smite?"
            actor.echo(CommTypes.DYNAMIC, msg, {}, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_cleric_smite_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_smite_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the smite spell, dealing holy damage with bonus vs undead."""
        SMITE_DICE_NUM = 2
        SMITE_DICE_SIZE = 8
        SMITE_BASE_BONUS = 2
        SMITE_PER_LEVEL = 0.8
        SMITE_UNDEAD_MULTIPLIER = 1.5  # 50% more damage vs undead
        SMITE_COOLDOWN_TICKS = ticks_from_seconds(8)
        
        # Calculate damage based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        damage_bonus = int(SMITE_BASE_BONUS + (cleric_level * SMITE_PER_LEVEL))
        damage = roll_dice(SMITE_DICE_NUM, SMITE_DICE_SIZE) + damage_bonus
        
        # Check if target is undead (check name for "zombie", "skeleton", "undead", etc.)
        is_undead = any(word in target.name.lower() for word in ['zombie', 'skeleton', 'undead', 'ghoul', 'vampire', 'lich', 'wraith', 'ghost', 'specter'])
        if is_undead:
            damage = int(damage * SMITE_UNDEAD_MULTIPLIER)
        
        cooldown = Cooldown(actor, "smite", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": SMITE_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, SMITE_COOLDOWN_TICKS)

        # Send messages
        if is_undead:
            msg = f"You smite {target.art_name} with divine fury! The undead creature recoils!"
        else:
            msg = f"You smite {target.art_name} with holy power!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        
        msg = f"{actor.art_name_cap} smites you with holy power!"
        vars = set_vars(actor, actor, target, msg)
        target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        
        msg = f"{actor.art_name_cap} smites {target.art_name} with holy power!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
        
        # Deal holy damage
        await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.HOLY)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.SMITE)
        return True

    @classmethod
    async def do_cleric_bless(cls, actor: Actor, target: Actor, 
                             difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast bless on self or target, granting hit and damage bonus."""
        THIS_SKILL_DATA = ClericSkills.BLESS
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        # Default to self if no target
        if target is None:
            target = actor
            
        continue_func = lambda: cls.do_cleric_bless_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_bless_finish(cls, actor: Actor, target: Actor, 
                                    difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the bless spell, applying hit and damage bonuses."""
        BLESS_HIT_BONUS_BASE = 5
        BLESS_HIT_BONUS_PER_LEVEL = 0.3
        BLESS_DAMAGE_BONUS_BASE = 2
        BLESS_DAMAGE_BONUS_PER_LEVEL = 0.2
        BLESS_DURATION_TICKS = ticks_from_seconds(180)  # 3 minutes
        BLESS_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        # Calculate bonuses based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        hit_bonus = int(BLESS_HIT_BONUS_BASE + (cleric_level * BLESS_HIT_BONUS_PER_LEVEL))
        damage_bonus = int(BLESS_DAMAGE_BONUS_BASE + (cleric_level * BLESS_DAMAGE_BONUS_PER_LEVEL))
        
        cooldown = Cooldown(actor, "bless", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": BLESS_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, BLESS_COOLDOWN_TICKS)

        # Apply the bless effect
        if target == actor:
            msg = "Divine favor surrounds you!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"Divine favor surrounds {actor.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        else:
            msg = f"You bestow divine blessings upon {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} bestows divine blessings upon you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} bestows divine blessings upon {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
        
        # Apply hit bonus
        hit_state = CharacterStateHitBonus(target, cls.game_state, actor, "blessed", 
                                          affect_amount=hit_bonus, tick_created=game_tick)
        hit_state.apply_state(game_tick or cls.game_state.current_tick, BLESS_DURATION_TICKS)
        
        # Apply damage bonus
        damage_state = CharacterStateDamageBonus(target, cls.game_state, actor, "blessed", 
                                                affect_amount=damage_bonus, tick_created=game_tick)
        damage_state.apply_state(game_tick or cls.game_state.current_tick, BLESS_DURATION_TICKS)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.BLESS)
        return True

    @classmethod
    async def do_cleric_consecrate(cls, actor: Actor, target: Actor, 
                                  difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast consecrate, dealing holy DoT to all enemies in the room."""
        THIS_SKILL_DATA = ClericSkills.CONSECRATE
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_cleric_consecrate_finish(actor, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, None, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_consecrate_finish(cls, actor: Actor, difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the consecrate spell, applying holy DoT to all enemies."""
        from .nondb_models.character_interface import PermanentCharacterFlags
        
        CONSECRATE_DAMAGE_BASE = 3
        CONSECRATE_DAMAGE_PER_LEVEL = 0.4
        CONSECRATE_DURATION_TICKS = ticks_from_seconds(15)
        CONSECRATE_PULSE_TICKS = ticks_from_seconds(3)
        CONSECRATE_COOLDOWN_TICKS = ticks_from_seconds(30)
        
        # Calculate damage per tick based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        damage_per_tick = int(CONSECRATE_DAMAGE_BASE + (cleric_level * CONSECRATE_DAMAGE_PER_LEVEL))
        
        cooldown = Cooldown(actor, "consecrate", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": CONSECRATE_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, CONSECRATE_COOLDOWN_TICKS)

        # Send initial message
        msg = "You consecrate the ground with holy fire!"
        vars = set_vars(actor, actor, None, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = f"{actor.art_name_cap} consecrates the ground with holy fire!"
        vars = set_vars(actor, actor, None, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        
        # Apply to all enemies in the room
        enemies_hit = 0
        for char in actor._location_room.characters:
            if char == actor:
                continue
            # Skip friendly targets (same group or friendly flag)
            if char.group_id and char.group_id == actor.group_id:
                continue
            if char.has_perm_flags(PermanentCharacterFlags.IS_FRIENDLY):
                continue
            if char.has_perm_flags(PermanentCharacterFlags.IS_PC):
                continue  # Don't hit other players
            
            # Apply the consecrate effect
            new_state = CharacterStateConsecrated(char, cls.game_state, actor, "consecrated", 
                                                 damage_amount=damage_per_tick, tick_created=game_tick)
            new_state.apply_state(game_tick or cls.game_state.current_tick, CONSECRATE_DURATION_TICKS,
                                 pulse_period_ticks=CONSECRATE_PULSE_TICKS)
            enemies_hit += 1
        
        if enemies_hit == 0:
            msg = "But there are no enemies to burn!"
            actor.echo(CommTypes.DYNAMIC, msg, {}, cls.game_state)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.CONSECRATE)
        return True

    @classmethod
    async def do_cleric_zealotry(cls, actor: Actor, target: Actor, 
                                difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast zealotry on self, gaining damage bonus but reduced healing received."""
        THIS_SKILL_DATA = ClericSkills.ZEALOTRY
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_cleric_zealotry_finish(actor, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, None, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_zealotry_finish(cls, actor: Actor, difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the zealotry spell, applying damage bonus and healing penalty."""
        ZEALOTRY_DAMAGE_BONUS_BASE = 5
        ZEALOTRY_DAMAGE_BONUS_PER_LEVEL = 0.5
        ZEALOTRY_HEALING_PENALTY = 40  # 40% less healing received
        ZEALOTRY_DURATION_TICKS = ticks_from_seconds(60)  # 1 minute
        ZEALOTRY_COOLDOWN_TICKS = ticks_from_seconds(120)  # 2 minute cooldown
        
        # Calculate damage bonus based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        damage_bonus = int(ZEALOTRY_DAMAGE_BONUS_BASE + (cleric_level * ZEALOTRY_DAMAGE_BONUS_PER_LEVEL))
        
        cooldown = Cooldown(actor, "zealotry", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": ZEALOTRY_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, ZEALOTRY_COOLDOWN_TICKS)

        # Send messages
        msg = "Divine fury fills you! Your attacks grow stronger but you become reckless!"
        vars = set_vars(actor, actor, None, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = f"{actor.art_name_cap} is filled with zealous fury!"
        vars = set_vars(actor, actor, None, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        
        # Apply the zealotry effect
        new_state = CharacterStateZealotry(actor, cls.game_state, actor, "zealous", 
                                          damage_bonus=damage_bonus, healing_penalty=ZEALOTRY_HEALING_PENALTY,
                                          tick_created=game_tick)
        new_state.apply_state(game_tick or cls.game_state.current_tick, ZEALOTRY_DURATION_TICKS)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.ZEALOTRY)
        return True

    @classmethod
    async def do_cleric_judgment(cls, actor: Actor, target: Actor, 
                                difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast judgment on target, dealing high holy damage with bonus vs undead."""
        THIS_SKILL_DATA = ClericSkills.JUDGMENT
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        if target is None:
            msg = "Who do you want to judge?"
            actor.echo(CommTypes.DYNAMIC, msg, {}, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_cleric_judgment_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_judgment_finish(cls, actor: Actor, target: Actor, 
                                       difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the judgment spell, dealing high holy damage."""
        JUDGMENT_DICE_NUM = 4
        JUDGMENT_DICE_SIZE = 10
        JUDGMENT_BASE_BONUS = 10
        JUDGMENT_PER_LEVEL = 1.5
        JUDGMENT_UNDEAD_MULTIPLIER = 2.0  # Double damage vs undead
        JUDGMENT_COOLDOWN_TICKS = ticks_from_seconds(20)
        
        # Calculate damage based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        damage_bonus = int(JUDGMENT_BASE_BONUS + (cleric_level * JUDGMENT_PER_LEVEL))
        damage = roll_dice(JUDGMENT_DICE_NUM, JUDGMENT_DICE_SIZE) + damage_bonus
        
        # Check if target is undead
        is_undead = any(word in target.name.lower() for word in ['zombie', 'skeleton', 'undead', 'ghoul', 'vampire', 'lich', 'wraith', 'ghost', 'specter'])
        if is_undead:
            damage = int(damage * JUDGMENT_UNDEAD_MULTIPLIER)
        
        cooldown = Cooldown(actor, "judgment", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": JUDGMENT_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, JUDGMENT_COOLDOWN_TICKS)

        # Send messages
        if is_undead:
            msg = f"You pass divine judgment upon {target.art_name}! The undead abomination writhes in agony!"
        else:
            msg = f"You pass divine judgment upon {target.art_name}!"
        vars = set_vars(actor, actor, target, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        
        msg = f"{actor.art_name_cap} passes divine judgment upon you!"
        vars = set_vars(actor, actor, target, msg)
        target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        
        msg = f"{actor.art_name_cap} passes divine judgment upon {target.art_name}!"
        vars = set_vars(actor, actor, target, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
        
        # Deal holy damage
        await CoreActionsInterface.get_instance().do_calculated_damage(actor, target, damage, DamageType.HOLY)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.JUDGMENT)
        return True

    @classmethod
    async def do_cleric_divine_reckoning(cls, actor: Actor, target: Actor, 
                                        difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast divine reckoning, dealing massive AoE holy damage and stunning all enemies."""
        THIS_SKILL_DATA = ClericSkills.DIVINE_RECKONING
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
            
        continue_func = lambda: cls.do_cleric_divine_reckoning_finish(actor, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, None, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_divine_reckoning_finish(cls, actor: Actor, difficulty_modifier=0, game_tick=0) -> bool:
        """Complete divine reckoning, dealing massive AoE damage and stunning enemies."""
        from .nondb_models.character_interface import PermanentCharacterFlags
        
        RECKONING_DICE_NUM = 6
        RECKONING_DICE_SIZE = 12
        RECKONING_BASE_BONUS = 20
        RECKONING_PER_LEVEL = 2.0
        RECKONING_STUN_DURATION_TICKS = ticks_from_seconds(4)
        RECKONING_COOLDOWN_TICKS = ticks_from_seconds(300)  # 5 minute cooldown
        
        # Calculate damage based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        damage_bonus = int(RECKONING_BASE_BONUS + (cleric_level * RECKONING_PER_LEVEL))
        
        cooldown = Cooldown(actor, "divine_reckoning", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": RECKONING_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, RECKONING_COOLDOWN_TICKS)

        # Send initial message
        msg = "You invoke DIVINE RECKONING! Holy light blazes forth!"
        vars = set_vars(actor, actor, None, msg)
        actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
        msg = f"{actor.art_name_cap} invokes DIVINE RECKONING! Blinding holy light blazes forth!"
        vars = set_vars(actor, actor, None, msg)
        actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        
        # Hit all enemies in the room
        enemies_hit = 0
        for char in list(actor._location_room.characters):
            if char == actor:
                continue
            # Skip friendly targets
            if char.group_id and char.group_id == actor.group_id:
                continue
            if char.has_perm_flags(PermanentCharacterFlags.IS_FRIENDLY):
                continue
            if char.has_perm_flags(PermanentCharacterFlags.IS_PC):
                continue
            
            # Roll damage for each target
            damage = roll_dice(RECKONING_DICE_NUM, RECKONING_DICE_SIZE) + damage_bonus
            
            # Deal holy damage
            await CoreActionsInterface.get_instance().do_calculated_damage(actor, char, damage, DamageType.HOLY)
            
            # Apply stun
            stun_state = CharacterStateStunned(char, cls.game_state, actor, "divine reckoning", 
                                              tick_created=game_tick)
            stun_state.apply_state(game_tick or cls.game_state.current_tick, RECKONING_STUN_DURATION_TICKS)
            enemies_hit += 1
        
        if enemies_hit == 0:
            msg = "But there are no enemies to judge!"
            actor.echo(CommTypes.DYNAMIC, msg, {}, cls.game_state)
        else:
            msg = f"Divine reckoning strikes {enemies_hit} enemies!"
            actor.echo(CommTypes.DYNAMIC, msg, {}, cls.game_state)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.DIVINE_RECKONING)
        return True

    @classmethod
    async def do_cleric_cast_armor_of_faith(cls, actor: Actor, target: Actor, 
                                           difficulty_modifier=0, game_tick=0, nowait=False) -> bool:
        """Cast armor of faith on self or target, granting physical damage reduction."""
        THIS_SKILL_DATA = ClericSkills.ARMOR_OF_FAITH
        ready, msg = Skills.check_ready(actor, THIS_SKILL_DATA.cooldown_name, THIS_SKILL_DATA)
        if not ready:
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            return False
        
        # Default to self if no target
        if target is None:
            target = actor
            
        continue_func = lambda: cls.do_cleric_cast_armor_of_faith_finish(actor, target, difficulty_modifier, game_tick)
        actor.recovers_at = (game_tick or cls.game_state.current_tick) + actor.recovery_time
        if nowait:
            await continue_func()
        else:
            vars = set_vars(actor, actor, target, THIS_SKILL_DATA.message_prepare)
            actor.echo(CommTypes.DYNAMIC, THIS_SKILL_DATA.message_prepare, vars, cls.game_state)
            actor.recovers_at += THIS_SKILL_DATA.cast_time_ticks
            await cls.start_casting(actor, THIS_SKILL_DATA.cast_time_ticks, continue_func)
        return True
    
    @classmethod
    async def do_cleric_cast_armor_of_faith_finish(cls, actor: Actor, target: Actor, 
                                                  difficulty_modifier=0, game_tick=0) -> bool:
        """Complete the armor of faith spell, applying the armor bonus."""
        ARMOR_BONUS_BASE = 2
        ARMOR_BONUS_PER_LEVEL = 0.3
        ARMOR_DURATION_TICKS = ticks_from_seconds(180)  # 3 minutes
        ARMOR_COOLDOWN_TICKS = ticks_from_seconds(60)
        
        # Calculate armor bonus based on caster's cleric level
        cleric_level = actor.levels_by_role.get(CharacterClassRole.CLERIC, 1)
        armor_bonus = int(ARMOR_BONUS_BASE + (cleric_level * ARMOR_BONUS_PER_LEVEL))
        
        cooldown = Cooldown(actor, "armor_of_faith", cls.game_state, cooldown_source=actor, 
                           cooldown_vars={"duration": ARMOR_COOLDOWN_TICKS})
        await cooldown.start(game_tick or cls.game_state.current_tick, ARMOR_COOLDOWN_TICKS)

        # Apply the armor of faith effect
        if target == actor:
            msg = "Divine armor shimmers around you, protecting you from harm!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"Divine armor shimmers around {actor.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor], game_state=cls.game_state)
        else:
            msg = f"You invoke divine protection upon {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} invokes divine protection upon you! Shimmering armor surrounds you!"
            vars = set_vars(actor, actor, target, msg)
            target.echo(CommTypes.DYNAMIC, msg, vars, cls.game_state)
            msg = f"{actor.art_name_cap} invokes divine protection upon {target.art_name}!"
            vars = set_vars(actor, actor, target, msg)
            actor._location_room.echo(CommTypes.DYNAMIC, msg, vars, exceptions=[actor, target], game_state=cls.game_state)
        
        new_state = CharacterStateArmorBonus(target, cls.game_state, actor, "armor of faith", 
                                            affect_amount=armor_bonus, tick_created=game_tick)
        new_state.apply_state(game_tick or cls.game_state.current_tick, ARMOR_DURATION_TICKS)
        
        # Consume mana
        await Skills.consume_resources(actor, ClericSkills.ARMOR_OF_FAITH)
        return True


class ClericSkills(ClassSkills):
    
    def get_level_requirement(self, skill_name: str) -> int:
        """Return the level requirement for a skill"""
        # Simple implementation for now
        tier1_skills = ["heal", "smite", "bless", "armor of faith", "regeneration"]
        tier2_skills = ["consecrate", "zealotry", "judgment", "cure poison"]
        tier3_skills = ["mass heal", "divine protection", "holy shield"]
        tier4_skills = ["divine reckoning", "resurrection", "divine intervention", "miracle"]
        
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
    
    # Basic healing spell
    HEAL = Skill(
        name="heal",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="heal",
        cooldown_ticks=ticks_from_seconds(8),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=15,
        message_prepare="You begin to channel divine energy...",
        message_success_subject="Divine light flows through your hands!",
        message_success_target="$cap(%a%) channels divine light toward you!",
        message_success_room="$cap(%a%) channels divine light toward %t%!",
        message_failure_subject="Your healing spell fizzles!",
        message_failure_target="$cap(%a%)'s healing spell fizzles!",
        message_failure_room="$cap(%a%)'s healing spell fizzles!",
        message_apply_subject="Your divine power heals %t%!",
        message_apply_target="$cap(%a%)'s divine power heals you!",
        message_apply_room="$cap(%a%)'s divine power heals %t%!",
        message_resist_subject="%t% resists your healing spell!",
        message_resist_target="You resist $cap(%a%)'s healing spell!",
        message_resist_room="%t% resists $cap(%a%)'s healing spell!",
        skill_function="do_cleric_heal",
        ai_priority=80,
        ai_condition=SkillAICondition.SELF_HP_BELOW_50,
        skill_type=SkillType.HEAL_SELF,
        requires_target=False
    )
    
    # Smite - basic offensive spell that deals holy damage with bonus vs undead
    SMITE = Skill(
        name="smite",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="smite",
        cooldown_ticks=ticks_from_seconds(8),
        cast_time_ticks=ticks_from_seconds(1.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=10,
        message_prepare="You invoke holy power...",
        message_success_subject="Holy power smites %t%!",
        message_success_target="$cap(%a%)'s holy power smites you!",
        message_success_room="$cap(%a%)'s holy power smites %t%!",
        message_failure_subject="Your smite fizzles!",
        message_failure_target="$cap(%a%)'s smite fizzles!",
        message_failure_room="$cap(%a%)'s smite fizzles!",
        message_apply_subject="Holy light burns %t%!",
        message_apply_target="$cap(%a%)'s holy light burns you!",
        message_apply_room="$cap(%a%)'s holy light burns %t%!",
        message_resist_subject="%t% resists your smite!",
        message_resist_target="You resist $cap(%a%)'s smite!",
        message_resist_room="%t% resists $cap(%a%)'s smite!",
        skill_function="do_cleric_smite",
        ai_priority=50,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=True
    )
    
    # Consecrate - AoE holy damage over time to all enemies
    CONSECRATE = Skill(
        name="consecrate",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="consecrate",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.5),
        duration_min_ticks=ticks_from_seconds(15),
        duration_max_ticks=ticks_from_seconds(15),
        mana_cost=25,
        message_prepare="You begin to sanctify the ground...",
        message_success_subject="Holy fire erupts from the consecrated ground!",
        message_success_target="The ground beneath you bursts into holy flames!",
        message_success_room="Holy fire erupts from the ground around $cap(%a%)!",
        message_failure_subject="Your consecration fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s consecration fizzles!",
        message_apply_subject="Holy flames burn your enemies!",
        message_apply_target="Holy flames burn you!",
        message_apply_room="Holy flames burn the enemies!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_cleric_consecrate",
        ai_priority=55,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=False
    )
    
    # Zealotry - self-buff that increases damage but reduces healing received
    ZEALOTRY = Skill(
        name="zealotry",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="zealotry",
        cooldown_ticks=ticks_from_seconds(120),
        cast_time_ticks=ticks_from_seconds(1.5),
        duration_min_ticks=ticks_from_seconds(60),
        duration_max_ticks=ticks_from_seconds(60),
        mana_cost=20,
        message_prepare="You channel righteous fury...",
        message_success_subject="Zealous fury fills your being!",
        message_success_target=None,
        message_success_room="$cap(%a%) is filled with zealous fury!",
        message_failure_subject="Your zealotry fades before manifesting!",
        message_failure_target=None,
        message_failure_room=None,
        message_apply_subject="Your attacks are strengthened but you become reckless!",
        message_apply_target=None,
        message_apply_room=None,
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_cleric_zealotry",
        ai_priority=70,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Judgment - powerful single-target holy damage with double damage vs undead
    JUDGMENT = Skill(
        name="judgment",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="judgment",
        cooldown_ticks=ticks_from_seconds(20),
        cast_time_ticks=ticks_from_seconds(2.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=30,
        message_prepare="You prepare to pass divine judgment...",
        message_success_subject="Divine judgment falls upon %t%!",
        message_success_target="$cap(%a%)'s divine judgment falls upon you!",
        message_success_room="$cap(%a%)'s divine judgment falls upon %t%!",
        message_failure_subject="Your judgment fails to manifest!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s judgment fails to manifest!",
        message_apply_subject="Holy wrath consumes %t%!",
        message_apply_target="Holy wrath consumes you!",
        message_apply_room="Holy wrath consumes %t%!",
        message_resist_subject="%t% partially resists your judgment!",
        message_resist_target="You partially resist $cap(%a%)'s judgment!",
        message_resist_room="%t% partially resists $cap(%a%)'s judgment!",
        skill_function="do_cleric_judgment",
        ai_priority=60,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=True
    )
    
    # Divine Reckoning - ultimate AoE holy damage + stun
    DIVINE_RECKONING = Skill(
        name="divine reckoning",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="divine_reckoning",
        cooldown_ticks=ticks_from_seconds(300),
        cast_time_ticks=ticks_from_seconds(3.5),
        duration_min_ticks=0,
        duration_max_ticks=0,
        mana_cost=60,
        message_prepare="You call upon the full might of the divine...",
        message_success_subject="DIVINE RECKONING IS UPON YOUR ENEMIES!",
        message_success_target="DIVINE RECKONING IS UPON YOU!",
        message_success_room="$cap(%a%) invokes DIVINE RECKONING!",
        message_failure_subject="The divine power escapes your grasp!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s divine reckoning fails to manifest!",
        message_apply_subject="Holy wrath devastates all enemies!",
        message_apply_target="Holy wrath devastates you!",
        message_apply_room="Holy wrath devastates all enemies!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_cleric_divine_reckoning",
        ai_priority=80,
        ai_condition=SkillAICondition.IN_COMBAT,
        skill_type=SkillType.DAMAGE,
        requires_target=False
    )
    
    # Create light
    LIGHT = Skill(
        name="light",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="light",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(1.0),
        duration_min_ticks=ticks_from_seconds(300),  # 5 minutes
        duration_max_ticks=ticks_from_seconds(300),
        message_prepare="You begin to summon divine light...",
        message_success_subject="You summon a globe of divine light!",
        message_success_target=None,
        message_success_room="$cap(%a%) summons a globe of divine light!",
        message_failure_subject="Your light spell fizzles!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s light spell fizzles!",
        message_apply_subject="A glowing orb of light follows you!",
        message_apply_target=None,
        message_apply_room="A glowing orb of light follows $cap(%a%)!",
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function=None  # Will be implemented later
    )
    
    # Cure poison
    CURE_POISON = Skill(
        name="cure poison",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="cure_poison",
        cooldown_ticks=ticks_from_seconds(30),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=0,
        duration_max_ticks=0,
        message_prepare="You channel cleansing energy...",
        message_success_subject="Cleansing energy flows through your hands!",
        message_success_target="$cap(%a%) channels cleansing energy toward you!",
        message_success_room="$cap(%a%) channels cleansing energy toward %t%!",
        message_failure_subject="Your cure poison spell fizzles!",
        message_failure_target="$cap(%a%)'s cure poison spell fizzles!",
        message_failure_room="$cap(%a%)'s cure poison spell fizzles!",
        message_apply_subject="Your cleansing power purges poison from %t%!",
        message_apply_target="$cap(%a%)'s cleansing power purges poison from you!",
        message_apply_room="$cap(%a%)'s cleansing power purges poison from %t%!",
        message_resist_subject="%t% is too heavily poisoned for your spell!",
        message_resist_target="You are too heavily poisoned for $cap(%a%)'s spell!",
        message_resist_room="%t% is too heavily poisoned for $cap(%a%)'s spell!",
        skill_function=None  # Will be implemented later
    )
    
    # Bless - buff that grants hit and damage bonus
    BLESS = Skill(
        name="bless",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="bless",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(180),  # 3 minutes
        duration_max_ticks=ticks_from_seconds(180),
        mana_cost=15,
        message_prepare="You call upon divine blessings...",
        message_success_subject="Divine favor surrounds you!",
        message_success_target="$cap(%a%) calls upon divine blessings for you!",
        message_success_room="$cap(%a%) calls upon divine blessings for %t%!",
        message_failure_subject="Your blessing fades quickly!",
        message_failure_target="$cap(%a%)'s blessing for you fades quickly!",
        message_failure_room="$cap(%a%)'s blessing for %t% fades quickly!",
        message_apply_subject="You bestow divine blessings upon %t%!",
        message_apply_target="$cap(%a%) bestows divine blessings upon you!",
        message_apply_room="$cap(%a%) bestows divine blessings upon %t%!",
        message_resist_subject="%t% resists your divine blessing!",
        message_resist_target="You resist $cap(%a%)'s divine blessing!",
        message_resist_room="%t% resists $cap(%a%)'s divine blessing!",
        skill_function="do_cleric_bless",
        ai_priority=70,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Armor of Faith - defensive spell that increases physical damage reduction
    ARMOR_OF_FAITH = Skill(
        name="armor of faith",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="armor_of_faith",
        cooldown_ticks=ticks_from_seconds(60),
        cast_time_ticks=ticks_from_seconds(2.5),
        duration_min_ticks=ticks_from_seconds(180),  # 3 minutes
        duration_max_ticks=ticks_from_seconds(180),
        mana_cost=20,
        message_prepare="You invoke divine protection...",
        message_success_subject="Divine armor shimmers around you, protecting you from harm!",
        message_success_target="$cap(%a%) invokes divine protection upon you! Shimmering armor surrounds you!",
        message_success_room="Divine armor shimmers around $cap(%a%)!",
        message_failure_subject="Your prayer for protection goes unanswered!",
        message_failure_target=None,
        message_failure_room="$cap(%a%)'s prayer for protection goes unanswered!",
        message_apply_subject="Divine armor reduces the damage you take!",
        message_apply_target="Divine armor reduces the damage you take!",
        message_apply_room=None,
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_cleric_cast_armor_of_faith",
        ai_priority=65,
        ai_condition=SkillAICondition.NOT_IN_COMBAT,
        skill_type=SkillType.BUFF_SELF,
        requires_target=False
    )
    
    # Regeneration - healing over time
    REGENERATION = Skill(
        name="regeneration",
        base_class=CharacterClassRole.CLERIC,
        cooldown_name="regeneration",
        cooldown_ticks=ticks_from_seconds(45),
        cast_time_ticks=ticks_from_seconds(2.0),
        duration_min_ticks=ticks_from_seconds(30),
        duration_max_ticks=ticks_from_seconds(30),
        mana_cost=25,
        message_prepare="You invoke healing energies to sustain your ally...",
        message_success_subject="Regenerative magic flows through you!",
        message_success_target="$cap(%a%) invokes regenerative magic upon you!",
        message_success_room="Regenerative magic surrounds %t%!",
        message_failure_subject="Your regeneration spell fizzles!",
        message_failure_target="$cap(%a%)'s regeneration spell fizzles!",
        message_failure_room="$cap(%a%)'s regeneration spell fizzles!",
        message_apply_subject="Regenerative magic heals you!",
        message_apply_target="Regenerative magic heals you!",
        message_apply_room=None,
        message_resist_subject=None,
        message_resist_target=None,
        message_resist_room=None,
        skill_function="do_cleric_regeneration",
        ai_priority=70,
        ai_condition=SkillAICondition.SELF_HP_BELOW_50,
        skill_type=SkillType.HEAL_SELF,
        requires_target=False
    ) 