import copy
from custom_detail_logger import CustomDetailLogger
from enum import Enum
from typing import Dict, List
from .actor_interface import ActorType, ActorInterface
from .actor_states import Cooldown
from .actors import Actor
from .attacks_and_damage import AttackData, DamageResistances, DamageType, PotentialDamage
from .character_interface import CharacterInterface, EquipLocation, GamePermissionFlags, PermanentCharacterFlags, TemporaryCharacterFlags    
from ..communication import CommTypes
from ..constants import Constants, CharacterClassRole
from .object_interface import ObjectInterface, ObjectFlags
from ..utility import article_plus_name, get_dice_parts, replace_vars, roll_dice, evaluate_functions_in_line



class CharacterSkill():
    def __init__(self, character_class: CharacterClassRole, skill_number: int, skill_level: int=0):
        self.character_class = character_class
        self.skill_number = skill_number
        self.skill_level = skill_level

    def set_skill_level(self, skill_level: int):
        self.skill_level = skill_level

    def get_skill_level(self):
        return self.skill_level
    
    def add_points(self, points: int):
        self.skill_level += points


class CharacterClass:

    def __init__(self, role: CharacterClassRole, level: int = 0):
        self.role = role
        self.level = level

    def level_up(self):
        self.level += 1



class Character(Actor, CharacterInterface):
    
    def __init__(self, id: str, definition_zone: 'Zone', name: str = "", create_reference=True):
        super().__init__(ActorType.CHARACTER, id, name=name, create_reference=create_reference)
        self.definition_zone = definition_zone
        self.description = ""
        self.attributes = {}
        self._location_room = None
        self.contents = []
        self.levels_by_role : Dict[CharacterClassRole, int] = {}
        self.contents: List[Object] = []
        self.permanent_character_flags = PermanentCharacterFlags(0)
        self.temporary_character_flags = TemporaryCharacterFlags(0)
        self.current_states = []
        self.connection: 'Connection' = None
        self.fighting_whom: Character = None
        self.equipped: Dict[EquipLocation, ObjectInterface] = {loc: None for loc in EquipLocation}
        self.damage_resistances = DamageResistances()
        self.current_damage_resistances = DamageResistances()
        self.damage_reduction: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.current_damage_reduction: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.natural_attacks: List[AttackData] = []
        self.hit_modifier: int = 80
        self.dodge_dice_number: int = 1
        self.dodge_dice_size: int = 50
        self.dodge_modifier: int = 0
        self.critical_chance: int = 0
        self.critical_multiplier: int = 100
        self.hit_dice = 1
        self.hit_dice_size = 10
        self.hit_point_bonus = 0
        self.max_hit_points = 1
        self.current_hit_points = 1
        self.game_permission_flags = GamePermissionFlags(0)
        self.max_carrying_capacity = 100
        self.current_carrying_weight = 0
        self.num_main_hand_attacks = 1
        self.num_off_hand_attacks = 0
        self.skill_levels_by_role: Dict[CharacterClassRole, Dict[Enum, int]] = {}
        self.skill_points_available: int = 0
        self.cooldowns: List[Cooldown] = []
        self.experience_points: int = 0
        self.group_id: str = ""


    def from_yaml(self, yaml_data: str):
        from .triggers import Trigger
        logger = CustomDetailLogger(__name__, prefix="Character.from_yaml()> ")
        # self.game_permission_flags_.set_flag(GamePermissionFlags.IS_ADMIN)
        # self.game_permission_flags_.set_flag(GamePermissionFlags.CAN_INSPECT)
        self.name = yaml_data['name']
        self.article = yaml_data['article'] if 'article' in yaml_data else "a" if self.name[0].lower() in "aeiou" else "an" if self.name else ""
        self.description = yaml_data['description'] if 'description' in yaml_data else ''
        self.pronoun_subject = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
        self.pronoun_object = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
        self.pronoun_possessive = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
        # if 'character_flags' in yaml_data:
        #     for flag in yaml_data['character_flags']:
        #         self.permanent_character_flags_.set_flag(CharacterFlags[flag.upper()])
        if 'character_flags' in yaml_data:
            for flag in yaml_data['character_flags']:
                try:
                    self.permanent_character_flags = self.permanent_character_flags.add_flag_name(flag)
                except KeyError as e:
                    logger.error(f"Error: {flag.upper()} is not a valid CharacterFlag. Details: {e}")
        if 'experience_points' in yaml_data:
            self.experience_points = yaml_data['experience_points']
        # need attributes
        # need classes
        hit_point_parts = get_dice_parts(yaml_data['hit_dice'])
        self.hit_dice, self.hit_dice_size, self.hit_point_bonus = hit_point_parts[0], hit_point_parts[1], hit_point_parts[2]
        # need character flags
        # need damage resistances
        # print(yaml_data['natural_attacks'])
        for atk in yaml_data['natural_attacks']:
            new_attack = AttackData()
            new_attack.attack_noun = atk['attack_noun']
            new_attack.attack_verb = atk['attack_verb']
            for dmg in atk['potential_damage']:
                dice_parts = get_dice_parts(dmg['damage_dice'])
                num_dice, dice_size, dice_bonus = dice_parts[0],dice_parts[1],dice_parts[2]
                new_attack.potential_damage_.append(PotentialDamage(DamageType[dmg['damage_type'].upper()], num_dice, dice_size, dice_bonus))
            self.natural_attacks.append(new_attack)
        # print(type(self.hit_dice_))
        # print(type(self.hit_dice_size_))
        # print(type(self.hit_point_bonus_))
        self.max_hit_points = roll_dice(self.hit_dice, self.hit_dice_size, self.hit_point_bonus)
        self.current_hit_points = self.max_hit_points
        self.hit_modifier = yaml_data['hit_modifier']
        dodge_parts = get_dice_parts(yaml_data['dodge_dice'])
        self.dodge_dice_number, self.dodge_dice_size, self.dodge_modifier = dodge_parts[0], dodge_parts[1], dodge_parts[2]
        self.critical_chance = yaml_data['critical_chance']
        self.critical_multiplier = yaml_data['critical_multiplier']
        if 'triggers' in yaml_data:
            for trig in yaml_data['triggers']:
                logger.debug(f"got trigger for {self.name}: {trig}")
                # logger.debug3(f"loading trigger_type: {trigger_type}")
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type:
                    self.triggers_by_type[new_trigger.trigger_type_] = []
                self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
        # unnecessary?
        # if 'triggers' in yaml_data:
        #     # print(f"triggers: {yaml_data['triggers']}")
        #     # raise NotImplementedError("Triggers not implemented yet.")
        #     # for trigger_type, trigger_info in yaml_data['triggers'].items():
        #     #     # logger.debug3(f"loading trigger_type: {trigger_type}")
        #     #     if not trigger_type in self.triggers_by_type_:
        #     #         self.triggers_by_type_[trigger_type] = []
        #     #     self.triggers_by_type_[trigger_type] += trigger_info
        #     logger.critical(f"def triggers first: {self.triggers_by_type_}")
        #     for trig in yaml_data['triggers']:
        #         logger.critical("in for loop for trigger")
        #         # logger.debug3(f"loading trigger_type: {trigger_type}")
        #         new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
        #         if not new_trigger.trigger_type_ in self.triggers_by_type_:
        #             self.triggers_by_type_[new_trigger.trigger_type_] = []
        #         self.triggers_by_type_[new_trigger.trigger_type_].append(new_trigger)
        #     logger.critical(f"def triggers: {self.triggers_by_type_}")

    @property
    def art_name(self):
        return article_plus_name(self.article, self.name)
    
    @property
    def art_name_cap(self):
        return article_plus_name(self.article, self.name, cap=True)
    
    async def send_text(self, text_type: CommTypes, text: str) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Character.sendText()> ")
        logger.debug3(f"sendText: {text}")
        if self.connection:
            logger.debug3(f"connection exists, sending text to {self.name}")
            await self.connection.send(text_type, text)
            logger.debug3("text sent")
            return True
        else:
            logger.debug3("no connection")
            return False

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted: bool = False,
                   game_state: 'ComprehensiveGameState' = None, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Character.echo()> ")
        logger.debug3("text before " + text)
        if not already_substituted:
            text = evaluate_functions_in_line(replace_vars(text, vars), vars, game_state)
        logger.debug3("text after " + text)
        if exceptions and self in exceptions:
            retval = False
        else:
            retval = True
            logger.debug3("sending text: " + text)
            await self.send_text(text_type, text)
        logger.debug3("running super")
        await super().echo(text_type, text, vars, exceptions, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        return retval

    @classmethod
    def create_from_definition(cls, char_def: 'Character') -> 'Character':
        logger = CustomDetailLogger(__name__, prefix="Character.create_from_definition()> ")
        print(f"char_def: {char_def}")
        logger.critical(f"char def triggers: {char_def.triggers_by_type}")
        new_char = copy.deepcopy(char_def)
        logger.critical(f"new_char triggers: {char_def.triggers_by_type}")
        if not new_char.reference_number or new_char.reference_number == char_def.reference_number:
            new_char.create_reference()
        new_char.max_hit_points = roll_dice(new_char.hit_dice, new_char.hit_dice_size, new_char.hit_point_bonus)
        new_char.current_hit_points = new_char.max_hit_points
        new_char.contents = []
        new_char.connection = None
        new_char.fighting_whom = None
        new_char.equipped = {loc: None for loc in EquipLocation}
        for trig_type, trig_data in new_char.triggers_by_type.items():
            for trig in trig_data:
                logger.debug(f"enabling trigger: {trig.to_dict()}")
                trig.actor_ = new_char
                trig.enable()
        return new_char
    
    def get_status_description(self):
        health_percent = self.current_hit_points * 100 / self.max_hit_points
        if health_percent < 10:
            msg = "nearly dead"
        elif health_percent < 25:
            msg = "badly wounded"
        elif health_percent < 50:
            msg = "wounded"
        elif health_percent < 75:
            msg = "slightly wounded"
        elif health_percent < 90:
            msg = "in good health"
        else:
            msg = "in excellent health"
        # TODO:L: added statuses for burning, poisoned, etc.
        return msg

    def add_object(self, obj: ObjectInterface, force=False):
        self.contents.append(obj)
        obj.set_in_actor(self)
        self.current_carrying_weight += obj.weight

    def remove_object(self, obj: ObjectInterface):
        self.contents.remove(obj)
        obj.set_in_actor(None)
        self.current_carrying_weight -= obj.weight

    def is_dead(self):
        return self.current_hit_points <= 0
    
    def equip_item(self, equip_location: EquipLocation, item: ObjectInterface):
        if self.equipped[equip_location] != None:
            raise Exception("equip_location already in self.equipped_")
        item.set_equip_location(equip_location)
        item.set_in_actor(self)
        self.equipped[equip_location] = item
        self.calculate_damage_resistance()

    def unequip_location(self, equip_location: EquipLocation) -> 'Object':
        if equip_location not in self.equipped:
            raise Exception("equip_location not in self.equipped_")
        item = self.equipped[equip_location]
        item.set_equip_location(None)
        item.set_in_actor(None)
        self.equipped[equip_location] = None
        self.calculate_damage_resistance()
        return item

    def calculate_damage_resistance(self):
        self.current_damage_resistances = copy.deepcopy(self.damage_resistances)
        for item in self.equipped.values():
            if item:
                for dt, mult in item.damage_resistances.profile.items():
                    self.current_damage_resistances.profile[dt] = self.current_damage_resistances.profile[dt] * mult
        # TODO:M: add status effects
                    
    # def get_character_states_flags(self, flags: TemporaryCharacterFlags) -> List[ActorState]:
    #     states = []
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_DEAD):
    #         states.append("dead")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_SITTING):
    #         states.append("sitting")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_SLEEPING):
    #         states.append("sleeping")
    #     if self.temporary_character_flags_.is_set(TemporaryCharacterFlags.IS_STUNNED):
    #         states.append("stunned")
    #     return states
    
    def get_character_states_by_flag(self, flags: TemporaryCharacterFlags) -> List['ActorState']:
        return [s for s in self.current_states if s.does_affect_flag(flags)]
    
    def get_character_states_by_type(self, cls) -> List['ActorState']:
        return [state for state in self.current_states if isinstance(state, cls)]


    def add_state(self, state: 'ActorState') -> bool:
        self.current_states.append(state)
        return True

    def remove_state(self, state: 'ActorState') -> bool:
        self.current_states.remove(state)
        return True

    def total_levels(self):
        return sum(self.levels_by_role.values())
    
    def has_cooldown(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.has_cooldown(self, cooldown_source, cooldown_name)
    
    def add_cooldown(self, cooldown: Cooldown):
        self.cooldowns.append(cooldown)

    def remove_cooldown(self, cooldown: Cooldown):
        self.cooldowns.remove(cooldown)

    def current_cooldowns(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.current_cooldowns(self, cooldown_source, cooldown_name)
    
    def last_cooldown(self, cooldown_source=None, cooldown_name: str=None):
        return Cooldown.last_cooldown(self, cooldown_source, cooldown_name)

    def get_states(self):
        return self.current_states
    
    def has_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        return self.temporary_character_flags.are_flags_set(flags)

    def has_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        return self.permanent_character_flags.are_flags_set(flags)
    
    def has_game_flags(self, flags: GamePermissionFlags) -> bool:
        return self.game_permission_flags.are_flags_set(flags)
    
    def add_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags.add_flags(flags)
        return True
    
    def add_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags.add_flags(flags)
        return True
    
    def add_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags.add_flags(flags)
        return True
    
    def remove_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags.remove_flags(flags)
        return True
    
    def remove_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags.remove_Flags(flags)
        return True
    
    def remove_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags.remove_Flags(flags)
        return True
    
    def set_in_room(self, room: 'Room'):
        self._location_room = room

    def can_level(self):
        return self.experience_points >= Constants.XP_PROGRESSION[self.total_levels()]
    
    def level_up(self, role: CharacterClassRole) -> bool:
        if self.can_level():
            self.levels_by_role[role] += 1
            self.max_hit_points += Constants.HP_BY_CHARACTER_CLASS[role]
            self.current_hit_points += Constants.HP_BY_CHARACTER_CLASS[role]
            if not role in self.skill_levels_by_role:
                self.skill_levels_by_role[role] = {}
            for skill, level in Skills.SKILL_LEVEL_REQUIREMENTS[role].items():
                if self.levels_by_role[role] >= level and not skill in self.skill_levels_by_role[role]:
                    self.skill_levels_by_role[role][skill] = 0
            # handle rogue dual-wielding requirement
            highest_role = max(self.levels_by_role, key=lambda role: self.levels_by_role[role])
            highest_main_hand_attacks_num = 0
            highest_main_hand_attacks_role = None
            for role, role_level in self.skill_levels_by_role.items():
                main_hand_attacks_num = Constants.MAIN_HAND_PROGRESSION[role][role_level]
                if main_hand_attacks_num > highest_main_hand_attacks_num:
                    highest_main_hand_attacks_num = main_hand_attacks_num
                    highest_main_hand_attacks_role = role
            if role == CharacterClassRole.ROGUE and self.levels_by_role[role] >= highest_role:
                self.num_off_hand_attacks = Constants.OFF_HAND_PROGRESSION[CharacterClassRole.ROGUE][self.levels_by_role[role]]
                self.add_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD)
            else:
                self.num_off_hand_attacks = 0
                self.remove_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD)
            return True
        else:
            return False

    def gain_xp(self, xp_amount: int) -> bool:
        self.experience_points += xp_amount
        return self.can_level()

    @property
    def location_room(self) -> 'Room':
        return self._location_room

    @location_room.setter
    def location_room(self, room: 'Room'):
        self._location_room = room
