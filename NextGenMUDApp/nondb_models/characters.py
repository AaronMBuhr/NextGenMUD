import copy
from ..structured_logger import StructuredLogger
from enum import Enum, auto
from typing import Dict, List, Callable, Optional
from .actor_interface import ActorType, ActorInterface
from .actor_states import Cooldown
from .actors import Actor
from .attacks_and_damage import AttackData, DamageResistances, DamageType, PotentialDamage
from .character_interface import CharacterInterface, EquipLocation, GamePermissionFlags, PermanentCharacterFlags, \
    TemporaryCharacterFlags, CharacterAttributes
from ..communication import CommTypes
from ..comprehensive_game_state_interface import GameStateInterface
from ..constants import Constants, CharacterClassRole
from .object_interface import ObjectInterface, ObjectFlags
from ..utility import article_plus_name, get_dice_parts, replace_vars, roll_dice, evaluate_functions_in_line
from .actor_attitudes import ActorAttitude

logger = StructuredLogger(__name__)

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
    
    def __init__(self, id: str, definition_zone_id: str, name: str = "", create_reference=True):
        super().__init__(ActorType.CHARACTER, id, name=name, create_reference=create_reference)
        self.definition_zone_id = definition_zone_id
        self.description = ""
        self.attributes = {}
        self._location_room = None
        self.contents = []
        self.levels_by_role : Dict[CharacterClassRole, int] = {}
        self.class_priority : List[CharacterClassRole] = []
        self.max_class_count = 3
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
        self.skill_levels: Dict[str, int] = {}
        self.skill_points_available: int = 0
        self.cooldowns: List[Cooldown] = []
        self.experience_points: int = 0
        self.group_id: str = None
        self.starting_eq = None
        self.starting_inv = None
        self.attitude = ActorAttitude.NEUTRAL
        self.specializations = {}  # Maps base class to chosen specialization

    def from_yaml(self, yaml_data: str, definition_zone_id: str):
        from .triggers import Trigger
        logger = StructuredLogger(__name__, prefix="Character.from_yaml()> ")
        try:
            # self.game_permission_flags_.set_flag(GamePermissionFlags.IS_ADMIN)
            # self.game_permission_flags_.set_flag(GamePermissionFlags.CAN_INSPECT)
            self.name = yaml_data['name']
            self.definition_zone_id = definition_zone_id
            self.article = yaml_data['article'] if 'article' in yaml_data else "a" if self.name[0].lower() in "aeiou" else "an" if self.name else ""
            self.description = yaml_data['description'] if 'description' in yaml_data else ''
            self.pronoun_subject = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
            self.pronoun_object = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
            self.pronoun_possessive = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
            self.group_id = yaml_data['group_id'] if 'group_id' in yaml_data else None
            
            # Set attitude from YAML if provided, defaulting to NEUTRAL
            if 'attitude' in yaml_data:
                try:
                    self.attitude = ActorAttitude[yaml_data['attitude'].upper()]
                except KeyError as e:
                    logger.error(f"Error: {yaml_data['attitude'].upper()} is not a valid ActorAttitude. Using NEUTRAL. Details: {e}")
                    self.attitude = ActorAttitude.NEUTRAL
            
            # if 'character_flags' in yaml_data:
            if 'class' in yaml_data:
                # Clear existing class data
                self.class_priority = []
                self.levels_by_role = {}
                self.skill_levels_by_role = {}
                
                # Track primary/secondary/tertiary class order if specified
                if 'class_priority' in yaml_data:
                    for role_name in yaml_data['class_priority']:
                        try:
                            role = CharacterClassRole[role_name.upper()]
                            if len(self.class_priority) < self.max_class_count:
                                self.class_priority.append(role)
                        except KeyError as e:
                            logger.error(f"Error: {role_name.upper()} is not a valid CharacterClassRole. Details: {e}")
                
                # Process class data
                for role, role_data in yaml_data['class'].items():
                    try:
                        role_enum = CharacterClassRole[role.upper()]
                        self.levels_by_role[role_enum] = role_data['level']
                        self.skill_levels_by_role[role_enum] = {}
                        
                        # Add to class_priority if not already there and if we have room
                        if role_enum not in self.class_priority and len(self.class_priority) < self.max_class_count:
                            self.class_priority.append(role_enum)
                            
                        if 'skills' in role_data:
                            for skill, skill_data in role_data['skills'].items():
                                if role_enum == CharacterClassRole.FIGHTER:
                                    skills = FighterSkills
                                elif role_enum == CharacterClassRole.ROGUE:
                                    skills = RogueSkills
                                elif role_enum == CharacterClassRole.MAGE:
                                    skills = MageSkills
                                elif role_enum == CharacterClassRole.CLERIC:
                                    skills = ClericSkills
                                else:
                                    raise Exception("Invalid character class role.")
                                self.skill_levels_by_role[role_enum][skills[skill.upper()]] = skill_data['level']
                    except KeyError as e:
                        logger.error(f"Error: {role.upper()} is not a valid CharacterClassRole. Details: {e}")
                        
            if 'permanent_flags' in yaml_data:
                for flag in yaml_data['permanent_flags']:
                    try:
                        self.permanent_character_flags = self.permanent_character_flags.add_flag_name(flag)
                    except KeyError as e:
                        logger.error(f"Error: {flag.upper()} is not a valid CharacterFlag. Details: {e}")
            if 'experience_points' in yaml_data:
                self.experience_points = yaml_data['experience_points']
            for resist_name, resist_amount in yaml_data.get('damage_resistances', {}).items():
                self.damage_resistances.profile[DamageType[resist_name.upper()]] = resist_amount
            for reduce_name, reduce_amount in yaml_data.get('damage_reductions', {}).items():
                self.damage_reduction.profile[DamageType[reduce_name.upper()]] = reduce_amount

            # print(yaml_data.get('attributes', []))
            for attr_name, attr_amount in yaml_data.get('attributes', {}).items():
                self.attributes[CharacterAttributes[attr_name.upper()]] = attr_amount
            # need classes
            hit_point_parts = get_dice_parts(yaml_data['hit_dice'])
            self.hit_dice, self.hit_dice_size, self.hit_point_bonus = hit_point_parts[0], hit_point_parts[1], hit_point_parts[2]
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
            if 'equipment' in yaml_data:
                self.starting_eq = yaml_data['equipment']
            if 'inventory' in yaml_data:
                self.starting_inv = yaml_data['inventory']
            if 'triggers' in yaml_data: 
                for trig in yaml_data['triggers']:
                    logger.debug3(f"got trigger for {self.name}: {trig}")
                    # logger.debug3(f"loading trigger_type: {trigger_type}")
                    new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                    if not new_trigger.trigger_type_ in self.triggers_by_type:
                        self.triggers_by_type[new_trigger.trigger_type_] = []
                    self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
            if 'skills' in yaml_data:
                for skill in yaml_data['skills']:
                    self.skill_levels[skill['skill']] = skill['level']
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
        except:
            logger.error("Error loading character from yaml.")
            logger.error("yaml_data: " + str(yaml_data))
            raise

    @property
    def art_name(self):
        return article_plus_name(self.article, self.name)
    
    @property
    def art_name_cap(self):
        return article_plus_name(self.article, self.name, cap=True)
    
    async def send_text(self, text_type: CommTypes, text: str) -> bool:
        logger = StructuredLogger(__name__, prefix="Character.sendText()> ")
        logger.debug3(f"sendText: {text}")
        if self.connection:
            logger.debug3(f"connection exists, sending text to {self.name}")
            await self.connection.send(text_type, text)
            logger.debug3("text sent")
            return True
        else:
            logger.debug3("no connection")
            return False

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, \
                   exceptions: List['Actor'] = None, already_substituted: bool = False,\
                   game_state: 'ComprehensiveGameState' = None, skip_triggers: bool = False) -> bool:
        logger = StructuredLogger(__name__, prefix="Character.echo()> ")
        logger.debug3(f"text before: {text}")  # Use f-string to handle potential None
        if not already_substituted and text is not None: # Ensure text is not None before processing
            processed_text = evaluate_functions_in_line(replace_vars(text, vars), vars, game_state)
        else:
            processed_text = text # Assign original text (or None) if no processing needed
        logger.debug3(f"text after: {processed_text}") # Use f-string
        if exceptions and self in exceptions:
            retval = False
        else:
            retval = True
            if processed_text is not None: # Only send if text is not None
                logger.debug3(f"sending text: {processed_text}") # Use f-string
                await self.send_text(text_type, processed_text)
        logger.debug3("running super")
        await super().echo(text_type, processed_text, vars, exceptions, already_substituted=True, game_state=game_state, skip_triggers=skip_triggers)
        return retval

    @classmethod
    def create_from_definition(cls, char_def: 'Character', game_state: GameStateInterface=None,include_items: bool = True) -> 'Character':
        logger = StructuredLogger(__name__, prefix="Character.create_from_definition()> ")
        logger.debug3(f"char_def: {char_def}")
        logger.debug3(f"char def triggers: {char_def.triggers_by_type}")
        new_char = copy.deepcopy(char_def)
        logger.debug3(f"new_char triggers: {char_def.triggers_by_type}")
        if not new_char.reference_number or new_char.reference_number == char_def.reference_number:
            new_char.create_reference()
        new_char.max_hit_points = roll_dice(new_char.hit_dice, new_char.hit_dice_size, new_char.hit_point_bonus)
        new_char.current_hit_points = new_char.max_hit_points
        new_char.contents = []
        new_char.connection = None
        new_char.fighting_whom = None
        new_char.equipped = {loc: None for loc in EquipLocation}
        if new_char.starting_eq and include_items:
            for eq_id in new_char.starting_eq:
                if "." not in eq_id:
                    eq_id = f"{new_char.definition_zone_id}.{eq_id}"
                new_obj_def = game_state.world_definition.find_object_definition(eq_id)
                if not new_obj_def:
                    logger.warning(f"Could not find object definition for {eq_id}")
                    continue
                new_obj = ObjectInterface.create_from_definition(new_obj_def, game_state)
                if not new_obj:
                    logger.warning(f"Could not create object from definition for {eq_id}")
                    continue
                if new_char.equipped[new_obj.equip_location] != None:
                    if new_obj.equip_location == EquipLocation.LEFT_FINGER \
                    and new_char.equipped[EquipLocation.RIGHT_FINGER] == None:
                        new_char.equip_item(EquipLocation.RIGHT_FINGER, new_obj)
                    elif new_obj.equip_location == EquipLocation.RIGHT_FINGER \
                    and new_char.equipped[EquipLocation.LEFT_FINGER] == None:
                        new_char.equip_item(EquipLocation.LEFT_FINGER, new_obj)
                    elif new_obj.equip_location == EquipLocation.MAIN_HAND \
                    and new_char.equipped[EquipLocation.OFF_HAND] == None:
                        new_char.equip_item(EquipLocation.OFF_HAND, new_obj)
                    else:
                        logger.error("equip_location already in self.equipped_")
                else:
                    new_char.equip_item(new_obj.equip_location, new_obj)
        if new_char.starting_inv and include_items:
            for inv_id in new_char.starting_inv:
                if "." not in inv_id:
                    inv_id = f"{new_char.definition_zone_id}.{inv_id}"
                new_obj_def = game_state.world_definition.find_object_definition(inv_id)
                if not new_obj_def:
                    logger.error(f"Could not find object definition for {inv_id}")
                    continue
                new_obj = ObjectInterface.create_from_definition(new_obj_def, game_state)
                if not new_obj:
                    logger.error(f"Could not create object from definition for {inv_id}")
                    continue
                new_char.add_object(new_obj)
        for trig_type, trig_data in new_char.triggers_by_type.items():
            for trig in trig_data:
                logger.debug3(f"enabling trigger: {trig.to_dict()}")
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
    
    def remove_states_by_flag(self, flags: TemporaryCharacterFlags) -> bool:
        for state in self.get_character_states_by_flag(flags):
            self.remove_state(state)
        return True

    def total_levels(self):
        return sum(self.levels_by_role.values())
    
    def get_class_count(self):
        """Return the number of classes this character has"""
        return len(self.class_priority)
    
    def has_class(self, role: CharacterClassRole) -> bool:
        """Check if the character has the specified class"""
        return role in self.class_priority
    
    def get_primary_class(self) -> Optional[CharacterClassRole]:
        """Get the character's primary class, if any"""
        return self.class_priority[0] if len(self.class_priority) > 0 else None
    
    def get_secondary_class(self) -> Optional[CharacterClassRole]:
        """Get the character's secondary class, if any"""
        return self.class_priority[1] if len(self.class_priority) > 1 else None
    
    def get_tertiary_class(self) -> Optional[CharacterClassRole]:
        """Get the character's tertiary class, if any"""
        return self.class_priority[2] if len(self.class_priority) > 2 else None
    
    def get_class_level(self, role: CharacterClassRole) -> int:
        """Get the character's level in the specified class, or 0 if they don't have the class"""
        return self.levels_by_role.get(role, 0)
    
    def add_class(self, role: CharacterClassRole) -> bool:
        """
        Add a new class to the character
        Returns True if successful, False if the character already has the maximum number of classes
        """
        if role in self.class_priority:
            return True  # Already has this class
        
        if len(self.class_priority) >= self.max_class_count:
            return False  # Already has maximum classes
        
        self.class_priority.append(role)
        self.levels_by_role[role] = 1  # Start at level 1
        self.skill_levels_by_role[role] = {}  # Initialize skills dict
        
        # Add skills based on level requirements
        for skill, level in Skills.SKILL_LEVEL_REQUIREMENTS[role].items():
            if 1 >= level:  # Starting at level 1
                self.skill_levels_by_role[role][skill] = 0
                
        return True
    
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
        self.permanent_character_flags.remove_flags(flags)
        return True
    
    def remove_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags.remove_flags(flags)
        return True
    
    def set_in_room(self, room: 'Room'):
        self._location_room = room

    def can_level(self):
        return self.experience_points >= Constants.XP_PROGRESSION[self.total_levels()]
    
    def level_up(self, role: CharacterClassRole) -> bool:
        """Level up the specified class. Returns True if successful, False otherwise."""
        if role not in self.class_priority:
            return False  # Can't level a class the character doesn't have
        
        if not self.can_level():
            return False  # Not enough XP to level up
        
        # Increase class level
        self.levels_by_role[role] += 1
        current_level = self.levels_by_role[role]
        
        # Increase hit points based on class
        self.max_hit_points += Constants.HP_BY_CHARACTER_CLASS[role]
        self.current_hit_points += Constants.HP_BY_CHARACTER_CLASS[role]
        
        # Initialize skill dict if needed
        if role not in self.skill_levels_by_role:
            self.skill_levels_by_role[role] = {}
            
        # If this is a base class, unlock base class skills
        if CharacterClassRole.is_base_class(role):
            # Unlock new skills if appropriate level
            for skill, level in Skills.SKILL_LEVEL_REQUIREMENTS[role].items():
                if current_level >= level and skill not in self.skill_levels_by_role[role]:
                    self.skill_levels_by_role[role][skill] = 0
            
            # If we have a specialization, also unlock specialization skills
            if role in self.specializations:
                specialization = self.specializations[role]
                for skill, level in Skills.SKILL_LEVEL_REQUIREMENTS.get(specialization, {}).items():
                    if current_level >= level and skill not in self.skill_levels_by_role[role]:
                        self.skill_levels_by_role[role][skill] = 0
        
        # Handle special class features
        self._update_class_features()
        
        return True
    
    def _update_class_features(self):
        """Update special features based on class levels and combinations"""
        # Get primary class (highest level)
        highest_level_roles = sorted(self.levels_by_role.items(), key=lambda x: x[1], reverse=True)
        
        # Handle number of attacks based on class levels
        highest_main_hand_attacks_num = 0
        highest_main_hand_attacks_role = None
        
        for role, role_level in self.levels_by_role.items():
            main_hand_attacks_num = Constants.MAIN_HAND_ATTACK_PROGRESSION[role][role_level]
            if main_hand_attacks_num > highest_main_hand_attacks_num:
                highest_main_hand_attacks_num = main_hand_attacks_num
                highest_main_hand_attacks_role = role
                
        # Set main hand attacks to the best value from any class
        self.num_main_hand_attacks = highest_main_hand_attacks_num
        
        # Handle rogue dual-wielding - check if rogue is in our classes
        if CharacterClassRole.ROGUE in self.class_priority:
            rogue_level = self.levels_by_role[CharacterClassRole.ROGUE]
            # Only enable dual-wielding if rogue is one of our primary classes
            if highest_level_roles and highest_level_roles[0][0] == CharacterClassRole.ROGUE:
                self.num_off_hand_attacks = Constants.OFF_HAND_ATTACK_PROGRESSION[CharacterClassRole.ROGUE][rogue_level]
                self.add_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD)
            else:
                # Still allow dual-wielding but with reduced effectiveness if rogue is secondary/tertiary
                reduced_level = max(1, rogue_level // 2)  # Half as effective if not primary
                self.num_off_hand_attacks = Constants.OFF_HAND_ATTACK_PROGRESSION[CharacterClassRole.ROGUE][reduced_level]
                self.add_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD)
        else:
            # No rogue class, no dual wielding
            self.num_off_hand_attacks = 0
            self.remove_perm_flags(PermanentCharacterFlags.CAN_DUAL_WIELD)
            
        # Additional class feature combinations could be implemented here
        
    def calculate_damage_resistance(self):
        """Recalculate damage resistances including any class-based bonuses"""
        # Original calculation logic
        self.current_damage_resistances = copy.deepcopy(self.damage_resistances)
        for item in self.equipped.values():
            if item:
                for dt, mult in item.damage_resistances.profile.items():
                    self.current_damage_resistances.profile[dt] = self.current_damage_resistances.profile[dt] * mult
        
        # Apply class-based resistances
        # Example: Fighters get better physical resistance, Mages get better magical resistance
        if CharacterClassRole.FIGHTER in self.class_priority:
            fighter_level = self.levels_by_role[CharacterClassRole.FIGHTER]
            # Reduce physical damage by 1% per level (multiplicative)
            physical_resist_mult = 1.0 - (fighter_level * 0.01)
            self.current_damage_resistances.profile[DamageType.PHYSICAL] *= physical_resist_mult
            
        if CharacterClassRole.MAGE in self.class_priority:
            mage_level = self.levels_by_role[CharacterClassRole.MAGE]
            # Reduce magical damage by 1% per level (multiplicative)
            magic_resist_mult = 1.0 - (mage_level * 0.01)
            self.current_damage_resistances.profile[DamageType.MAGICAL] *= magic_resist_mult
            
        # TODO:M: add status effects

    def gain_xp(self, xp_amount: int) -> bool:
        self.experience_points += xp_amount
        return self.can_level()

    @property
    def location_room(self) -> 'Room':
        return self._location_room

    @location_room.setter
    def location_room(self, room: 'Room'):
        self._location_room = room

    def get_display_class_name(self, role: CharacterClassRole) -> str:
        """
        Get the display name for a class or specialization.
        Once a character has chosen a specialization for a class, that's their displayed class.
        """
        # If this is a specialization, just return its name
        if CharacterClassRole.is_specialization(role):
            return CharacterClassRole.field_name(role)
            
        # If this is a base class, check if we have a specialization for it
        if role in self.specializations and self.levels_by_role[role] >= Constants.SPECIALIZATION_LEVEL:
            return CharacterClassRole.field_name(self.specializations[role])
            
        # Otherwise just return the base class name
        return CharacterClassRole.field_name(role)
        
    def get_class_description(self) -> str:
        """
        Returns a string description of the character's class(es)
        Example: "Level 25 Evoker/Level 10 Rogue"
        """
        descriptions = []
        for role in self.class_priority:
            level = self.levels_by_role[role]
            class_name = self.get_display_class_name(role)
            descriptions.append(f"Level {level} {class_name}")
            
        return "/".join(descriptions)
        
    def can_specialize(self, role: CharacterClassRole) -> bool:
        """Check if a character can choose a specialization for a class"""
        # Must be a base class
        if not CharacterClassRole.is_base_class(role):
            return False
            
        # Must have the class
        if role not in self.class_priority:
            return False
            
        # Must be at least level 20
        if self.levels_by_role[role] < Constants.SPECIALIZATION_LEVEL:
            return False
            
        # Must not already have a specialization for this class
        if role in self.specializations:
            return False
            
        return True
        
    def choose_specialization(self, base_class: CharacterClassRole, specialization: CharacterClassRole) -> bool:
        """
        Choose a specialization for a base class.
        Returns True if successful, False otherwise.
        """
        # Check if the character can specialize
        if not self.can_specialize(base_class):
            return False
            
        # Check if the specialization is valid for this base class
        if specialization not in CharacterClassRole.get_specializations(base_class):
            return False
            
        # Set the specialization
        self.specializations[base_class] = specialization
        
        # Unlock specialization skills
        self._unlock_specialization_skills(base_class, specialization)
        
        return True
        
    def _unlock_specialization_skills(self, base_class: CharacterClassRole, specialization: CharacterClassRole):
        """Unlock skills based on the chosen specialization and current level"""
        # Current level in this class
        level = self.levels_by_role[base_class]
        
        # Add skills for the specialization based on current level
        for skill, req_level in Skills.SKILL_LEVEL_REQUIREMENTS.get(specialization, {}).items():
            if level >= req_level and skill not in self.skill_levels_by_role[base_class]:
                self.skill_levels_by_role[base_class][skill] = 0
