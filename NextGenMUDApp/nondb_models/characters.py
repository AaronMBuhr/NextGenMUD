import copy
from ..structured_logger import StructuredLogger
from enum import Enum, auto
from typing import Dict, List, Callable, Optional
from .actor_interface import ActorType, ActorInterface
from .actor_states import Cooldown
from .actors import Actor
from .attacks_and_damage import AttackData, DamageMultipliers, DamageType, PotentialDamage
from .character_interface import CharacterInterface, EquipLocation, GamePermissionFlags, PermanentCharacterFlags, \
    TemporaryCharacterFlags, CharacterAttributes
from ..communication import CommTypes
from ..comprehensive_game_state_interface import GameStateInterface
from ..constants import Constants, CharacterClassRole
from .object_interface import ObjectInterface, ObjectFlags
from .objects import Object
from ..utility import article_plus_name, generate_article, get_dice_parts, replace_vars, roll_dice, evaluate_functions_in_line
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


class SkillsByClassProxy:
    """
    Proxy class that provides dict-like access to skills, dynamically creating
    CharacterSkill objects from the underlying skill_levels_by_role data.
    
    This allows code like: actor.skills_by_class[CharacterClassRole.FIGHTER][skill_enum]
    to return a CharacterSkill object with the correct skill_level.
    """
    
    def __init__(self, character: 'Character'):
        self._character = character
        self._class_proxies = {}
    
    def __getitem__(self, role: CharacterClassRole) -> 'ClassSkillsProxy':
        if role not in self._class_proxies:
            self._class_proxies[role] = ClassSkillsProxy(self._character, role)
        return self._class_proxies[role]
    
    def __contains__(self, role: CharacterClassRole) -> bool:
        return role in self._character.skill_levels_by_role
    
    def get(self, role: CharacterClassRole, default=None):
        if role in self._character.skill_levels_by_role:
            return self[role]
        return default


class ClassSkillsProxy:
    """
    Proxy for a single class's skills, dynamically creates CharacterSkill objects.
    
    Supports access by:
    - String skill name (e.g., "mighty_kick", "mighty kick")
    - Skill enum value (for backwards compatibility)
    """
    
    def __init__(self, character: 'Character', role: CharacterClassRole):
        self._character = character
        self._role = role
        self._skill_cache = {}
    
    def _normalize_key(self, key) -> str:
        """Normalize a skill key to the standard string format."""
        if isinstance(key, str):
            return key.lower().replace(' ', '_').replace('-', '_')
        elif hasattr(key, 'name') and isinstance(key.name, str):
            # It's a Skill object or enum with a name attribute
            return key.name.lower().replace(' ', '_').replace('-', '_')
        elif hasattr(key, 'value'):
            # It's an enum without a string name
            return str(key.value).lower()
        else:
            return str(key).lower().replace(' ', '_').replace('-', '_')
    
    def __getitem__(self, skill_key) -> CharacterSkill:
        normalized = self._normalize_key(skill_key)
        
        # Check cache first
        if normalized in self._skill_cache:
            return self._skill_cache[normalized]
        
        # Get skill level from skill_levels_by_role, default to 0
        skill_levels = self._character.skill_levels_by_role.get(self._role, {})
        skill_level = skill_levels.get(normalized, 0)
        
        # Create CharacterSkill object with a hash of the skill name as the "number"
        skill_number = hash(normalized) & 0xFFFF  # Keep it as a reasonable int
        char_skill = CharacterSkill(self._role, skill_number, skill_level)
        
        # Cache it
        self._skill_cache[normalized] = char_skill
        return char_skill
    
    def __contains__(self, skill_key) -> bool:
        normalized = self._normalize_key(skill_key)
        skill_levels = self._character.skill_levels_by_role.get(self._role, {})
        return normalized in skill_levels
    
    def get(self, skill_key, default=None):
        if skill_key in self:
            return self[skill_key]
        return default
    
    def items(self):
        """Iterate over skill_name, CharacterSkill pairs"""
        skill_levels = self._character.skill_levels_by_role.get(self._role, {})
        for skill_name, level in skill_levels.items():
            yield skill_name, self[skill_name]


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
        self.max_class_count = 2  # Limit multiclassing to 2 classes
        self.contents: List[Object] = []
        self.permanent_character_flags = PermanentCharacterFlags(0)
        self.temporary_character_flags = TemporaryCharacterFlags(0)
        self.current_states = []
        self.connection: 'Connection' = None
        self.fighting_whom: Character = None
        self.charmed_by: Character = None  # Who has charmed/controls this character
        self.equipped: Dict[EquipLocation, ObjectInterface] = {loc: None for loc in EquipLocation}
        self.damage_multipliers = DamageMultipliers()
        self.current_damage_multipliers = DamageMultipliers()
        self.damage_reduction: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.current_damage_reduction: Dict[DamageType, int] = {dt: 0 for dt in DamageType}
        self.natural_attacks: List[AttackData] = []
        # Base combat stats (set by character template/NPC definition)
        self.base_hit_modifier: int = 50  # Base hit chance before level bonuses
        self.base_dodge_modifier: int = 0  # Base dodge before level bonuses
        # Current combat stats (base + level bonuses + buffs/debuffs)
        self.hit_modifier: int = 50
        self.dodge_dice_number: int = 1
        self.dodge_dice_size: int = 50
        self.dodge_modifier: int = 0
        self.critical_chance: int = 0
        self.critical_multiplier: int = 100
        # Spell power (increases spell save DC, reduces target resistance)
        self.spell_power: int = 0
        # Save skills (trainable 0-100, used in opposed saving throw checks)
        # These are stored in skill_levels dict with keys: "fortitude", "reflex", "will"
        # Attribute bonuses are calculated dynamically
        self.unspent_attribute_points: int = 0  # Gained every 10 levels
        self.hit_dice = 1
        self.hit_dice_size = 10
        self.hit_point_bonus = 0
        self.max_hit_points = 1
        self.current_hit_points = 1
        # Mana pool (magical abilities - Mage/Cleric)
        self.max_mana = 0
        self.current_mana = 0
        # Stamina pool (physical abilities - Fighter/Rogue)
        self.max_stamina = 0
        self.current_stamina = 0
        # Regen state tracking
        self.is_meditating = False
        self.game_permission_flags = GamePermissionFlags(0)
        self.max_carrying_capacity = 100
        self.current_carrying_weight = 0
        self.num_main_hand_attacks = 1
        self.num_off_hand_attacks = 0
        self.skill_levels: Dict[str, int] = {}
        self.skill_levels_by_role: Dict[CharacterClassRole, Dict[str, int]] = {}
        self.skill_cap_overrides: Dict[str, int] = {}  # YAML-defined skill cap overrides
        self.skill_points_available: int = 0
        self.cooldowns: List[Cooldown] = []
        self.experience_points: int = 0
        self.group_id: str = None
        self.starting_eq = None
        self.starting_inv = None
        self.attitude = ActorAttitude.NEUTRAL
        self.specializations = {}  # Maps base class to chosen specialization
        self.guards_rooms: List[str] = []  # List of zone.room IDs this NPC guards (blocks access to)
        self.last_entered_from: Optional[str] = None  # Direction player last entered current room from
        self._skills_by_class_proxy = None  # Lazy-initialized proxy for skills_by_class access
        # Saving throw bonuses - percentage bonuses that can exceed normal 5-95 limits
        # Keys: "fortitude", "reflex", "will" - values are percentage bonuses (100 = immune)
        self.saving_throw_bonuses: Dict[str, int] = {}

    @property
    def skills_by_class(self) -> SkillsByClassProxy:
        """
        Provides dict-like access to skills by class, returning CharacterSkill objects.
        
        Usage: actor.skills_by_class[CharacterClassRole.FIGHTER][skill_enum].skill_level
        """
        if self._skills_by_class_proxy is None:
            self._skills_by_class_proxy = SkillsByClassProxy(self)
        return self._skills_by_class_proxy

    def from_yaml(self, yaml_data: str, definition_zone_id: str):
        from .triggers import Trigger
        logger = StructuredLogger(__name__, prefix="Character.from_yaml()> ")
        try:
            # self.game_permission_flags_.set_flag(GamePermissionFlags.IS_ADMIN)
            # self.game_permission_flags_.set_flag(GamePermissionFlags.CAN_INSPECT)
            self.name = yaml_data['name']
            self.definition_zone_id = definition_zone_id
            self.article = yaml_data['article'] if 'article' in yaml_data else generate_article(self.name)
            # Support both 'long_description' (preferred) and 'description' for compatibility
            self.description = yaml_data.get('long_description', yaml_data.get('description', ''))
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
                        class_level = role_data['level']
                        self.levels_by_role[role_enum] = class_level
                        self.skill_levels_by_role[role_enum] = {}
                        
                        # Add to class_priority if not already there and if we have room
                        if role_enum not in self.class_priority and len(self.class_priority) < self.max_class_count:
                            self.class_priority.append(role_enum)
                        
                        # Auto-populate skills based on class level using registry
                        # This gives NPCs all skills appropriate for their level without 
                        # requiring explicit specification
                        try:
                            self._auto_populate_skills_for_class(role_enum, class_level)
                        except (ImportError, NameError) as e:
                            # Skill auto-population may fail during initial import due to circular imports
                            # Skills will be populated later when accessed via skills_by_class proxy
                            pass
                        
                        # Process explicit skill overrides if any
                        if 'skills' in role_data:
                            for skill_name, skill_data in role_data['skills'].items():
                                # Handle skill removal with -skill_name syntax
                                if skill_name.startswith('-'):
                                    # Remove skill (e.g., "-mighty_kick" removes mighty kick)
                                    actual_name = skill_name[1:]
                                    skill_key = self._get_skill_key(actual_name)
                                    if skill_key in self.skill_levels_by_role[role_enum]:
                                        del self.skill_levels_by_role[role_enum][skill_key]
                                    # Also remove any cap override
                                    if skill_key in self.skill_cap_overrides:
                                        del self.skill_cap_overrides[skill_key]
                                else:
                                    # Add or override skill level
                                    skill_key = self._get_skill_key(skill_name)
                                    
                                    if isinstance(skill_data, dict):
                                        level = skill_data.get('level', 0)
                                        # Support YAML cap override per skill
                                        # Example: skills:
                                        #            mighty_kick:
                                        #              level: 50
                                        #              cap: 75
                                        if 'cap' in skill_data:
                                            self.skill_cap_overrides[skill_key] = skill_data['cap']
                                    elif isinstance(skill_data, int):
                                        level = skill_data
                                    else:
                                        level = 0
                                    
                                    if level <= 0:
                                        # Level 0 or negative means remove the skill
                                        if skill_key in self.skill_levels_by_role[role_enum]:
                                            del self.skill_levels_by_role[role_enum][skill_key]
                                    else:
                                        self.skill_levels_by_role[role_enum][skill_key] = level
                    except KeyError as e:
                        logger.error(f"Error: {role.upper()} is not a valid CharacterClassRole. Details: {e}")
                        
            if 'permanent_flags' in yaml_data:
                for flag in yaml_data['permanent_flags']:
                    flag_lower = flag.lower()
                    # Convert legacy immunity flags to proper system
                    if flag_lower == 'immune_poison':
                        # Poison immunity is a damage multiplier of 0 (100% reduction)
                        self.damage_multipliers.profile[DamageType.POISON] = 0
                    elif flag_lower in ('immune_charm', 'immune_fear'):
                        # Charm/fear immunity is a 100% will save bonus
                        self.saving_throw_bonuses['will'] = 100
                    else:
                        # Handle as a regular permanent flag
                        # Try the flag name as-is first, then with IS_ prefix
                        flag_upper = flag.upper().replace(" ", "_").replace("-", "_")
                        flag_found = False
                        
                        # Try exact match first
                        if flag_upper in PermanentCharacterFlags.__members__:
                            flag_enum = PermanentCharacterFlags.__members__[flag_upper]
                            self.permanent_character_flags = self.permanent_character_flags.add_flags(flag_enum)
                            flag_found = True
                        # Try with IS_ prefix
                        elif f"IS_{flag_upper}" in PermanentCharacterFlags.__members__:
                            flag_enum = PermanentCharacterFlags.__members__[f"IS_{flag_upper}"]
                            self.permanent_character_flags = self.permanent_character_flags.add_flags(flag_enum)
                            flag_found = True
                        
                        if not flag_found:
                            logger.warning(f"Unknown permanent flag: {flag}")
            # Load top-level skill cap overrides
            # Example YAML:
            # skill_cap_overrides:
            #   mighty_kick: 75
            #   fireball: 50
            if 'skill_cap_overrides' in yaml_data:
                for skill_name, cap_value in yaml_data['skill_cap_overrides'].items():
                    skill_key = self._get_skill_key(skill_name)
                    self.skill_cap_overrides[skill_key] = cap_value
                    
            if 'experience_points' in yaml_data:
                self.experience_points = yaml_data['experience_points']
            for multiplier_name, multiplier_value in yaml_data.get('damage_multipliers', {}).items():
                self.damage_multipliers.profile[DamageType[multiplier_name.upper()]] = multiplier_value
            for reduce_name, reduce_amount in yaml_data.get('damage_reductions', {}).items():
                self.damage_reduction.profile[DamageType[reduce_name.upper()]] = reduce_amount
            
            # Load saving throw bonuses (percentage bonuses that can exceed normal limits)
            # Values: percentage bonus to save chance. 100 = immune (automatic success)
            # Valid keys: fortitude, reflex, will
            for save_type, bonus in yaml_data.get('saving_throw_bonuses', {}).items():
                normalized = save_type.lower()
                if normalized in ('fortitude', 'reflex', 'will'):
                    self.saving_throw_bonuses[normalized] = bonus
                else:
                    logger.warning(f"Unknown saving throw type: {save_type}")

            # print(yaml_data.get('attributes', []))
            for attr_name, attr_amount in yaml_data.get('attributes', {}).items():
                self.attributes[CharacterAttributes[attr_name.upper()]] = attr_amount
            # need classes
            if 'hit_dice' in yaml_data:
                hit_point_parts = get_dice_parts(yaml_data['hit_dice'])
                self.hit_dice, self.hit_dice_size, self.hit_point_bonus = hit_point_parts[0], hit_point_parts[1], hit_point_parts[2]
                self.max_hit_points = roll_dice(self.hit_dice, self.hit_dice_size, self.hit_point_bonus)
                self.current_hit_points = self.max_hit_points
            
            # Natural attacks are optional for non-combat NPCs
            # Supports both simple format (type/damage) and complex format (attack_noun/attack_verb/potential_damage)
            for atk in yaml_data.get('natural_attacks', []):
                # Check if using simple format (type and damage directly)
                if 'type' in atk and 'damage' in atk:
                    damage_type = DamageType[atk['type'].upper()]
                    dice_parts = get_dice_parts(atk['damage'])
                    num_dice, dice_size, dice_bonus = dice_parts[0], dice_parts[1], dice_parts[2]
                    new_attack = AttackData(
                        damage_type=damage_type,
                        damage_num_dice=num_dice,
                        damage_dice_size=dice_size,
                        damage_bonus=dice_bonus,
                        attack_noun=atk.get('attack_noun', damage_type.noun()),
                        attack_verb=atk.get('attack_verb', damage_type.verb())
                    )
                    self.natural_attacks.append(new_attack)
                # Complex format with attack_noun, attack_verb, and potential_damage list
                elif 'attack_noun' in atk and 'attack_verb' in atk and 'potential_damage' in atk:
                    # Use the first damage entry to initialize AttackData
                    first_dmg = atk['potential_damage'][0]
                    dice_parts = get_dice_parts(first_dmg['damage_dice'])
                    num_dice, dice_size, dice_bonus = dice_parts[0], dice_parts[1], dice_parts[2]
                    new_attack = AttackData(
                        damage_type=DamageType[first_dmg['damage_type'].upper()],
                        damage_num_dice=num_dice,
                        damage_dice_size=dice_size,
                        damage_bonus=dice_bonus,
                        attack_noun=atk['attack_noun'],
                        attack_verb=atk['attack_verb']
                    )
                    # Add any additional damage types
                    for dmg in atk['potential_damage'][1:]:
                        dice_parts = get_dice_parts(dmg['damage_dice'])
                        num_dice, dice_size, dice_bonus = dice_parts[0], dice_parts[1], dice_parts[2]
                        new_attack.potential_damage_.append(PotentialDamage(DamageType[dmg['damage_type'].upper()], num_dice, dice_size, dice_bonus))
                    self.natural_attacks.append(new_attack)
                else:
                    logger.warning(f"Invalid natural_attack format for {self.name}: {atk}")
            
            # Combat stats are optional for non-combat NPCs
            # base_hit_modifier is the template value; hit_modifier includes level bonuses
            if 'hit_modifier' in yaml_data:
                self.base_hit_modifier = yaml_data['hit_modifier']
            if 'dodge_dice' in yaml_data:
                dodge_parts = get_dice_parts(yaml_data['dodge_dice'])
                self.dodge_dice_number, self.dodge_dice_size, dodge_bonus = dodge_parts[0], dodge_parts[1], dodge_parts[2]
                self.base_dodge_modifier = dodge_bonus
            if 'critical_chance' in yaml_data:
                self.critical_chance = yaml_data['critical_chance']
            if 'critical_multiplier' in yaml_data:
                self.critical_multiplier = yaml_data['critical_multiplier']
            if 'equipment' in yaml_data:
                self.starting_eq = yaml_data['equipment']
            if 'inventory' in yaml_data:
                self.starting_inv = yaml_data['inventory']
            if 'triggers' in yaml_data: 
                for trig in yaml_data['triggers']:
                    logger.debug3(f"got trigger for {self.name}: {trig}")
                    # logger.debug3(f"loading trigger_type: {trigger_type}")
                    new_trigger = Trigger.new_trigger(trig["type"], self, disabled=True).from_dict(trig)
                    if not new_trigger.trigger_type_ in self.triggers_by_type:
                        self.triggers_by_type[new_trigger.trigger_type_] = []
                    self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
            if 'skills' in yaml_data:
                for skill in yaml_data['skills']:
                    self.skill_levels[skill['skill']] = skill['level']
            
            # Unlock universal skills (save skills) for all characters
            if self.class_priority:  # Only if character has a class
                try:
                    self._unlock_universal_skills()
                except (ImportError, NameError):
                    pass  # May fail during initial import
            
            # Load guard rooms (rooms this NPC blocks access to)
            if 'guards_rooms' in yaml_data:
                self.guards_rooms = yaml_data['guards_rooms']
            
            # Load LLM conversation configuration if present
            if 'llm_conversation' in yaml_data:
                self._load_llm_conversation_config(yaml_data['llm_conversation'], logger)
            
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

    def _load_llm_conversation_config(self, llm_config: dict, logger) -> None:
        """
        Load LLM conversation configuration from YAML data.
        
        Expected YAML format:
            llm_conversation:
              personality: "A grizzled old man..."
              speaking_style: "Speaks slowly, trails off..."
              knowledge:
                - id: secret_location
                  content: "The crypt is behind the willow"
                  reveal_threshold: 70
                  is_secret: true
              goals:
                - id: earn_trust
                  description: "Player earns NPC's trust"
                  condition: "Player shows respect"
                  disposition_required: 60
                  on_achieve_set_vars:
                    player.npc_trusts: true
                  on_achieve_message: "The NPC regards you warmly."
              will_discuss: ["the cemetery", "ghosts"]
              will_not_discuss: ["his past"]
              special_instructions: "Never reveal X unless..."
        """
        from ..llm_npc_conversation import NPCConversationHandler
        
        # Build the context dictionary that will be stored in perm_variables
        context_data = {
            "personality": llm_config.get("personality", f"You are {self.name}. {self.description}"),
            "speaking_style": llm_config.get("speaking_style", ""),
            "knowledge": [],
            "goals": [],
            "will_discuss": llm_config.get("will_discuss", []),
            "will_not_discuss": llm_config.get("will_not_discuss", []),
            "special_instructions": llm_config.get("special_instructions", ""),
            "common_knowledge_refs": llm_config.get("common_knowledge_refs", []),  # References to zone common knowledge
        }
        
        # Process knowledge entries
        for k in llm_config.get("knowledge", []):
            if isinstance(k, dict):
                context_data["knowledge"].append({
                    "id": k.get("id", "unknown"),
                    "content": k.get("content", ""),
                    "reveal_threshold": k.get("reveal_threshold", 60),
                    "is_secret": k.get("is_secret", True),
                })
            else:
                logger.warning(f"Invalid knowledge entry for {self.name}: {k}")
        
        # Process goals
        for g in llm_config.get("goals", []):
            if isinstance(g, dict):
                context_data["goals"].append({
                    "id": g.get("id", "unknown"),
                    "description": g.get("description", ""),
                    "condition": g.get("condition", ""),
                    "disposition_required": g.get("disposition_required"),
                    "on_achieve_set_vars": g.get("on_achieve_set_vars", {}),
                    "on_achieve_message": g.get("on_achieve_message"),
                })
            else:
                logger.warning(f"Invalid goal entry for {self.name}: {g}")
        
        # Store in permanent variables using the handler's key
        self.perm_variables[NPCConversationHandler.VAR_CONTEXT] = context_data
        
        logger.debug3(f"Loaded LLM conversation config for {self.name}")

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

    async def send_status_update(self) -> bool:
        """Send current HP/Mana/Stamina to the client status bar."""
        import json
        status_data = {
            'hp': self.current_hit_points,
            'max_hp': self.max_hit_points,
            'mana': self.current_mana,
            'max_mana': self.max_mana,
            'stamina': self.current_stamina,
            'max_stamina': self.max_stamina
        }
        return await self.send_text(CommTypes.STATUS, json.dumps(status_data))

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
        for trig_type, trig_data in char_def.triggers_by_type.items():
            for trig in trig_data:
                logger.debug3(f"checking trigger: {trig.to_dict()}")
                if not trig.disabled_:
                    logger.critical(f"char def trigger is enabled: {trig.to_dict()}")
                    raise Exception("char def trigger is enabled")
        
        new_char = copy.deepcopy(char_def)
        logger.debug3(f"new_char triggers: {char_def.triggers_by_type}")
        new_char.reference_number = None
        new_char.create_reference()
        new_char.max_hit_points = roll_dice(new_char.hit_dice, new_char.hit_dice_size, new_char.hit_point_bonus)
        new_char.current_hit_points = new_char.max_hit_points
        new_char.contents = []
        
        # Explicitly set connection to None to avoid issues with connection persistence
        # logger.debug3(f"Setting connection to None for new character {new_char.name} ({new_char.id})")
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
                new_obj = Object.create_from_definition(new_obj_def)
                if not new_obj:
                    logger.warning(f"Could not create object from definition for {eq_id}")
                    continue
                # Get the first equip location from the list
                if not new_obj.equip_locations:
                    logger.warning(f"Object {eq_id} has no equip_locations defined")
                    continue
                equip_loc = new_obj.equip_locations[0]
                if new_char.equipped[equip_loc] != None:
                    if equip_loc == EquipLocation.LEFT_FINGER \
                    and new_char.equipped[EquipLocation.RIGHT_FINGER] == None:
                        new_char.equip_item(EquipLocation.RIGHT_FINGER, new_obj)
                    elif equip_loc == EquipLocation.RIGHT_FINGER \
                    and new_char.equipped[EquipLocation.LEFT_FINGER] == None:
                        new_char.equip_item(EquipLocation.LEFT_FINGER, new_obj)
                    elif equip_loc == EquipLocation.MAIN_HAND \
                    and new_char.equipped[EquipLocation.OFF_HAND] == None:
                        new_char.equip_item(EquipLocation.OFF_HAND, new_obj)
                    else:
                        logger.error("equip_location already in self.equipped_")
                else:
                    new_char.equip_item(equip_loc, new_obj)
        if new_char.starting_inv and include_items:
            for inv_id in new_char.starting_inv:
                if "." not in inv_id:
                    inv_id = f"{new_char.definition_zone_id}.{inv_id}"
                new_obj_def = game_state.world_definition.find_object_definition(inv_id)
                if not new_obj_def:
                    logger.error(f"Could not find object definition for {inv_id}")
                    continue
                new_obj = Object.create_from_definition(new_obj_def)
                if not new_obj:
                    logger.error(f"Could not create object from definition for {inv_id}")
                    continue
                new_char.add_object(new_obj)
        for trig_type, trig_data in new_char.triggers_by_type.items():
            for trig in trig_data:
                logger.debug3(f"enabling trigger: {trig.to_dict()}")
                trig.actor_ = new_char
                trig.enable()
        
        # Calculate level-based bonuses (hit, dodge, spell power, attacks, mana, stamina)
        new_char._update_class_features()
        
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
    
    def is_incapacitated(self) -> bool:
        """Check if character is unable to act (stunned, frozen, sleeping)."""
        return self.has_temp_flags(
            TemporaryCharacterFlags.IS_STUNNED |
            TemporaryCharacterFlags.IS_FROZEN |
            TemporaryCharacterFlags.IS_SLEEPING
        )
    
    def can_see(self, target: 'Character') -> bool:
        """
        Check if this character can see the target.
        Returns False if target is hidden/stealthed/invisible and this character
        doesn't have the appropriate detection abilities.
        """
        # Dead characters can't see
        if self.is_dead():
            return False
        
        # Check invisibility
        if target.has_temp_flags(TemporaryCharacterFlags.IS_INVISIBLE):
            if not self.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE) and \
               not self.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE):
                return False
        
        # Check stealth/hidden
        if target.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED | TemporaryCharacterFlags.IS_HIDDEN):
            # For now, simple check - stealth defeats non-see-invisible viewers
            # TODO:M: Add perception vs stealth skill check
            if not self.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE) and \
               not self.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE):
                return False
        
        return True
    
    def get_guarded_destination(self, exit_destination: str) -> Optional['Character']:
        """
        Check if any hostile NPC in the room guards the given destination.
        Returns the blocking guard if found, None otherwise.
        
        Args:
            exit_destination: The zone.room ID of the exit destination
        """
        if not self._location_room:
            return None
        
        for char in self._location_room.get_characters():
            # Skip self
            if char == self:
                continue
            
            # Must be guarding this destination
            if not char.guards_rooms or exit_destination not in char.guards_rooms:
                continue
            
            # Must be hostile or unfriendly toward us
            if char.attitude not in [ActorAttitude.HOSTILE, ActorAttitude.UNFRIENDLY]:
                continue
            
            # Must be able to see us
            if not char.can_see(self):
                continue
            
            # Must not be incapacitated
            if char.is_incapacitated():
                continue
            
            # Check if this guard has explicitly allowed us passage
            allowed_players = char.get_perm_var("allows_passage", [])
            if self.id in allowed_players or self.name in allowed_players:
                continue
            
            # This guard blocks us
            return char
        
        return None
    
    def equip_item(self, equip_location: EquipLocation, item: ObjectInterface):
        if self.equipped[equip_location] != None:
            raise Exception("equip_location already in self.equipped_")
        item.set_equip_location(equip_location)
        item.set_in_actor(self)
        self.equipped[equip_location] = item
        self.calculate_damage_multipliers()

    def unequip_location(self, equip_location: EquipLocation) -> 'Object':
        if equip_location not in self.equipped:
            raise Exception("equip_location not in self.equipped_")
        item = self.equipped[equip_location]
        item.set_equip_location(None)
        item.set_in_actor(None)
        self.equipped[equip_location] = None
        self.calculate_damage_multipliers()
        return item

    def calculate_damage_multipliers(self):
        self.current_damage_multipliers = copy.deepcopy(self.damage_multipliers)
        for item in self.equipped.values():
            if item:
                for dt, mult in item.damage_multipliers.profile.items():
                    self.current_damage_multipliers.profile[dt] = self.current_damage_multipliers.profile[dt] * mult
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
        if state in self.current_states:
            self.current_states.remove(state)
            return True
        else:
            logger.warning(f"Attempted to remove state {state.state_type_name if hasattr(state, 'state_type_name') else type(state).__name__} from character {self.name} ({self.id}), but state was not in current_states list.")
            return False
    
    def remove_states_by_flag(self, flags: TemporaryCharacterFlags) -> bool:
        for state in self.get_character_states_by_flag(flags):
            self.remove_state(state)
        return True

    def total_levels(self):
        return sum(self.levels_by_role.values())
    
    def _unlock_universal_skills(self) -> List[str]:
        """
        Unlock universal skills (save skills) for all characters.
        These are stored in the main skill_levels dict, not by class.
        
        Returns:
            List of newly unlocked skill names
        """
        from ..skills_core import SkillsRegistry
        
        universal_skills = SkillsRegistry.get_class_skills("universal")
        newly_unlocked = []
        
        for skill_name, skill in universal_skills.items():
            normalized_name = skill_name.lower().replace(' ', '_').replace('-', '_')
            if normalized_name not in self.skill_levels:
                self.skill_levels[normalized_name] = 0
                newly_unlocked.append(skill_name.replace('_', ' ').title())
        
        return newly_unlocked
    
    def _unlock_skills_for_level(self, role: CharacterClassRole, class_level: int) -> List[str]:
        """
        Unlock skills for a class based on class level.
        
        Uses SkillsRegistry to find all skills for the class and their level requirements,
        then unlocks skills the character qualifies for (sets to level 0 = available to train).
        Skills are keyed by their normalized name (lowercase, underscores).
        
        Note: This is for the player skill point system. Skills start at 0 and must be
        trained using skill points.
        
        Returns:
            List of newly unlocked skill names (display format)
        """
        from ..skills_core import SkillsRegistry
        
        class_name = role.name.lower()
        class_skills = SkillsRegistry.get_class_skills(class_name)
        newly_unlocked = []
        
        if role not in self.skill_levels_by_role:
            self.skill_levels_by_role[role] = {}
        
        # Get the skill class for level requirements
        skill_class = self._get_skill_class_for_role(role)
        
        for skill_name, skill in class_skills.items():
            # Normalize skill name for consistent keying
            normalized_name = skill_name.lower().replace(' ', '_').replace('-', '_')
            
            # Get level requirement from the skill class
            level_req = 1  # Default to level 1
            if skill_class is not None:
                try:
                    level_req = skill_class.get_level_requirement(skill_class, skill_name)
                except Exception:
                    pass  # Use default
            
            # Unlock skill if character meets level requirement and doesn't already have it
            if class_level >= level_req and normalized_name not in self.skill_levels_by_role[role]:
                self.skill_levels_by_role[role][normalized_name] = 0  # Start at skill level 0 (unlocked but not trained)
                # Use the original skill name for display
                display_name = skill.name if hasattr(skill, 'name') else normalized_name.replace('_', ' ').title()
                newly_unlocked.append(display_name)
        
        return newly_unlocked
    
    def _auto_populate_skills_for_class(self, role: CharacterClassRole, class_level: int):
        """
        Auto-populate skills for a class based on class level.
        
        Uses SkillsRegistry to find all skills for the class and their level requirements,
        then grants all skills the character qualifies for at skill level 1.
        Skills are keyed by their normalized name (lowercase, underscores).
        
        Note: This is used for NPCs who get skills automatically.
        """
        from ..skills_core import SkillsRegistry
        
        class_name = role.name.lower()
        class_skills = SkillsRegistry.get_class_skills(class_name)
        
        if role not in self.skill_levels_by_role:
            self.skill_levels_by_role[role] = {}
        
        # Get the skill class for level requirements
        skill_class = self._get_skill_class_for_role(role)
        
        for skill_name, skill in class_skills.items():
            # Normalize skill name for consistent keying
            normalized_name = skill_name.lower().replace(' ', '_').replace('-', '_')
            
            # Get level requirement from the skill class
            level_req = 1  # Default to level 1
            if skill_class is not None:
                try:
                    level_req = skill_class.get_level_requirement(skill_class, skill_name)
                except Exception:
                    pass  # Use default
            
            # Grant skill if character meets level requirement and doesn't already have it
            if class_level >= level_req and normalized_name not in self.skill_levels_by_role[role]:
                self.skill_levels_by_role[role][normalized_name] = 1  # Start at skill level 1
    
    def _get_skill_class_for_role(self, role: CharacterClassRole):
        """Get the skill class (e.g., Skills_Fighter) for a given role."""
        try:
            from ..skills_fighter import Skills_Fighter
            from ..skills_rogue import Skills_Rogue
            from ..skills_mage import Skills_Mage
            from ..skills_cleric import Skills_Cleric
            
            skill_classes = {
                CharacterClassRole.FIGHTER: Skills_Fighter,
                CharacterClassRole.ROGUE: Skills_Rogue,
                CharacterClassRole.MAGE: Skills_Mage,
                CharacterClassRole.CLERIC: Skills_Cleric
            }
            return skill_classes.get(role)
        except (ImportError, NameError):
            # May fail during initial import due to circular imports
            return None
    
    def _get_skill_key(self, skill_name: str) -> str:
        """
        Normalize a skill name for use as a dictionary key.
        
        Args:
            skill_name: The skill name in any format
            
        Returns:
            Normalized key (lowercase, underscores)
        """
        return skill_name.lower().replace(' ', '_').replace('-', '_')
    
    def _get_skill_requirement_level(self, role: CharacterClassRole, skill_name: str) -> int:
        """
        Get the level requirement for a skill.
        
        This is used to calculate the dynamic skill cap based on when the skill
        becomes available vs the character's current level.
        
        Args:
            role: The character class role that provides this skill
            skill_name: The normalized skill name
            
        Returns:
            The level at which this skill becomes available (1, 10, 20, 30, etc.)
        """
        skill_class = self._get_skill_class_for_role(role)
        if skill_class is not None:
            try:
                # Convert normalized name back to display format for lookup
                display_name = skill_name.replace('_', ' ')
                return skill_class.get_level_requirement(skill_class, display_name)
            except Exception:
                pass
        # Default to tier 1 (level 1)
        return 1
    
    def get_skill_cap(self, skill_name: str, role: CharacterClassRole = None) -> int:
        """
        Get the current maximum trainable level for a skill.
        
        Args:
            skill_name: The name of the skill
            role: Optional specific class to check (if None, searches all classes)
            
        Returns:
            The maximum skill level the character can currently train to
        """
        from ..skills_core import Skills
        
        normalized = skill_name.lower().replace(' ', '_').replace('-', '_')
        
        # Find which role owns the skill if not specified
        if role is None:
            for r in self.class_priority:
                if r in self.skill_levels_by_role:
                    if normalized in self.skill_levels_by_role[r]:
                        role = r
                        break
        
        if role is None:
            return 0
        
        skill_requirement = self._get_skill_requirement_level(role, normalized)
        
        # Check for YAML override
        override_cap = None
        if hasattr(self, 'skill_cap_overrides') and self.skill_cap_overrides:
            override_cap = self.skill_cap_overrides.get(normalized)
        
        return Skills.calculate_skill_cap(self.total_levels(), skill_requirement, override_cap)
    
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
        Add a new class to the character (multiclassing).
        Grants level 1 in the new class with all appropriate stat bonuses.
        Returns True if successful, False if the character already has the maximum number of classes.
        """
        if role in self.class_priority:
            return True  # Already has this class
        
        if len(self.class_priority) >= self.max_class_count:
            return False  # Already has maximum classes
        
        self.class_priority.append(role)
        self.levels_by_role[role] = 1  # Start at level 1
        self.skill_levels_by_role[role] = {}  # Initialize skills dict
        
        # Grant HP for the new class
        hp_gain = Constants.HP_BY_CHARACTER_CLASS.get(role, 0)
        if hp_gain > 0:
            self.max_hit_points += hp_gain
            self.current_hit_points += hp_gain
        
        # Grant mana for the new class
        mana_gain = Constants.MANA_BY_CHARACTER_CLASS.get(role, 0)
        if mana_gain > 0:
            self.max_mana += mana_gain
            self.current_mana += mana_gain
        
        # Grant stamina for the new class
        stamina_gain = Constants.STAMINA_BY_CHARACTER_CLASS.get(role, 0)
        if stamina_gain > 0:
            self.max_stamina += stamina_gain
            self.current_stamina += stamina_gain
        
        # Unlock skills for level 1 of the new class (at level 0 - available to train)
        self._unlock_skills_for_level(role, 1)
        
        # Unlock universal skills (save skills) if this is the first class
        if len(self.class_priority) == 1:
            self._unlock_universal_skills()
                
        return True
    
    def has_cooldown(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.has_cooldown(self.cooldowns, cooldown_source, cooldown_name)
    
    def add_cooldown(self, cooldown: Cooldown):
        self.cooldowns.append(cooldown)

    def remove_cooldown(self, cooldown: Cooldown):
        self.cooldowns.remove(cooldown)

    def current_cooldowns(self, cooldown_source=None, cooldown_name: str = None):
        return Cooldown.current_cooldowns(self.cooldowns, cooldown_source, cooldown_name)
    
    def last_cooldown(self, cooldown_source=None, cooldown_name: str=None):
        return Cooldown.last_cooldown(self.cooldowns, cooldown_source, cooldown_name)

    def get_states(self):
        return self.current_states
    
    def has_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        return self.temporary_character_flags.are_flags_set(flags)

    def has_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        return self.permanent_character_flags.are_flags_set(flags)
    
    def has_game_flags(self, flags: GamePermissionFlags) -> bool:
        return self.game_permission_flags.are_flags_set(flags)
    
    def add_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags = self.temporary_character_flags.add_flags(flags)
        return True
    
    def add_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags = self.permanent_character_flags.add_flags(flags)
        return True
    
    def add_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags = self.game_permission_flags.add_flags(flags)
        return True
    
    def remove_temp_flags(self, flags: TemporaryCharacterFlags) -> bool:
        self.temporary_character_flags = self.temporary_character_flags.remove_flags(flags)
        return True
    
    def remove_perm_flags(self, flags: PermanentCharacterFlags) -> bool:
        self.permanent_character_flags = self.permanent_character_flags.remove_flags(flags)
        return True
    
    def remove_game_flags(self, flags: GamePermissionFlags) -> bool:
        self.game_permission_flags = self.game_permission_flags.remove_flags(flags)
        return True
    
    def set_in_room(self, room: 'Room'):
        self._location_room = room

    def can_level(self):
        """Check if character has enough XP to level up."""
        total = self.total_levels()
        # Check max level
        if total >= Constants.MAX_LEVEL:
            return False
        return self.experience_points >= Constants.XP_PROGRESSION[total]
    
    def has_unspent_skill_points(self) -> bool:
        """Check if character has unspent skill points that must be spent before leveling."""
        return self.skill_points_available > 0
    
    def can_perform_levelup(self, role: CharacterClassRole) -> tuple[bool, str]:
        """
        Check if a character can perform a level up in the specified class.
        Returns (can_level, reason_message).
        """
        # Check if has class
        if role not in self.class_priority:
            return False, f"You are not a {CharacterClassRole.field_name(role).title()}."
        
        # Check max level for the class
        current_class_level = self.levels_by_role.get(role, 0)
        if current_class_level >= Constants.MAX_LEVEL:
            return False, f"You have reached the maximum level for {CharacterClassRole.field_name(role).title()}."
        
        # Check total level cap
        if self.total_levels() >= Constants.MAX_LEVEL:
            return False, f"You have reached the maximum total level of {Constants.MAX_LEVEL}."
        
        # Check XP requirement
        if not self.can_level():
            next_xp = Constants.XP_PROGRESSION[self.total_levels()]
            return False, f"You need {next_xp:,} XP to level up. You have {self.experience_points:,} XP."
        
        # Check for unspent skill points
        if self.has_unspent_skill_points():
            return False, f"You must spend your {self.skill_points_available} skill points before leveling up. Use 'skillup <skill> <points>'."
        
        return True, ""
    
    def level_up(self, role: CharacterClassRole) -> tuple[bool, dict]:
        """
        Level up the specified class. 
        Returns (success, stats_gained) where stats_gained contains the increases.
        """
        if role not in self.class_priority:
            return False, {}  # Can't level a class the character doesn't have
        
        if not self.can_level():
            return False, {}  # Not enough XP to level up
        
        stats_gained = {}
        
        # Increase class level
        self.levels_by_role[role] += 1
        current_level = self.levels_by_role[role]
        stats_gained['level'] = current_level
        
        # Increase hit points based on class
        hp_gain = Constants.HP_BY_CHARACTER_CLASS.get(role, 0)
        self.max_hit_points += hp_gain
        self.current_hit_points += hp_gain
        stats_gained['hp'] = hp_gain
        
        # Increase mana based on class
        mana_gain = Constants.MANA_BY_CHARACTER_CLASS.get(role, 0)
        if mana_gain > 0:
            self.max_mana += mana_gain
            self.current_mana += mana_gain
            stats_gained['mana'] = mana_gain
        
        # Increase stamina based on class
        stamina_gain = Constants.STAMINA_BY_CHARACTER_CLASS.get(role, 0)
        if stamina_gain > 0:
            self.max_stamina += stamina_gain
            self.current_stamina += stamina_gain
            stats_gained['stamina'] = stamina_gain
        
        # Grant skill points based on class
        skill_points_gain = Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(role, 0)
        self.skill_points_available += skill_points_gain
        stats_gained['skill_points'] = skill_points_gain
        
        # Initialize skill dict if needed
        if role not in self.skill_levels_by_role:
            self.skill_levels_by_role[role] = {}
            
        # Unlock new skills appropriate for the new level (at level 0, meaning they can be trained)
        # This uses the skills registry to find skills and their level requirements
        newly_unlocked = self._unlock_skills_for_level(role, current_level)
        if newly_unlocked:
            stats_gained['new_skills'] = newly_unlocked
        
        # Grant attribute point at level milestones (10, 20, 30, 40, 50)
        total_level = self.total_levels()
        if total_level > 0 and total_level % Constants.ATTRIBUTE_GAIN_LEVEL_INTERVAL == 0:
            self.unspent_attribute_points += 1
            stats_gained['attribute_point'] = True
        
        # Handle special class features
        self._update_class_features()
        
        return True, stats_gained
    
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
        
        # Update mana and stamina pools
        self.calculate_max_mana()
        self.calculate_max_stamina()
        
        # Update combat bonuses based on class levels
        self.calculate_combat_bonuses()
        
    def calculate_max_mana(self):
        """
        Calculate max mana based on class levels and attributes.
        Mage uses INT, Cleric uses WIS.
        """
        base_mana = 0
        
        # Add mana from each class that grants it
        for role, level in self.levels_by_role.items():
            if role in Constants.MANA_BY_CHARACTER_CLASS:
                base_mana += Constants.MANA_BY_CHARACTER_CLASS[role] * level
        
        # Attribute bonus: Mage scales with INT, Cleric with WIS
        attribute_bonus = 0
        if CharacterClassRole.MAGE in self.levels_by_role:
            mage_level = self.levels_by_role[CharacterClassRole.MAGE]
            intelligence = self.attributes.get(CharacterAttributes.INTELLIGENCE, 10)
            attribute_bonus += max(0, intelligence - 10) * Constants.MANA_ATTRIBUTE_SCALING * mage_level
        
        if CharacterClassRole.CLERIC in self.levels_by_role:
            cleric_level = self.levels_by_role[CharacterClassRole.CLERIC]
            wisdom = self.attributes.get(CharacterAttributes.WISDOM, 10)
            attribute_bonus += max(0, wisdom - 10) * Constants.MANA_ATTRIBUTE_SCALING * cleric_level
        
        old_max = self.max_mana
        self.max_mana = base_mana + attribute_bonus
        
        # If max increased, add the difference to current (don't overfill)
        if self.max_mana > old_max:
            self.current_mana += (self.max_mana - old_max)
        # Cap current at max
        self.current_mana = min(self.current_mana, self.max_mana)
    
    def calculate_max_stamina(self):
        """
        Calculate max stamina based on class levels and CON.
        """
        base_stamina = 0
        
        # Add stamina from each class that grants it
        for role, level in self.levels_by_role.items():
            if role in Constants.STAMINA_BY_CHARACTER_CLASS:
                base_stamina += Constants.STAMINA_BY_CHARACTER_CLASS[role] * level
        
        # Attribute bonus: scales with CON
        constitution = self.attributes.get(CharacterAttributes.CONSTITUTION, 10)
        total_physical_levels = (
            self.levels_by_role.get(CharacterClassRole.FIGHTER, 0) +
            self.levels_by_role.get(CharacterClassRole.ROGUE, 0)
        )
        attribute_bonus = max(0, constitution - 10) * Constants.STAMINA_ATTRIBUTE_SCALING * total_physical_levels
        
        old_max = self.max_stamina
        self.max_stamina = base_stamina + attribute_bonus
        
        # If max increased, add the difference to current (don't overfill)
        if self.max_stamina > old_max:
            self.current_stamina += (self.max_stamina - old_max)
        # Cap current at max
        self.current_stamina = min(self.current_stamina, self.max_stamina)
    
    def calculate_combat_bonuses(self):
        """
        Calculate hit bonus, dodge bonus, and spell power based on class levels.
        
        Physical classes (Fighter/Rogue) gain hit bonus as they level.
        Caster classes (Mage/Cleric) gain spell power to overcome enemy resistances.
        All classes gain some dodge improvement.
        
        Note: Saving throws are now skill-based (see get_save_value and resolve_saving_throw).
        
        This creates level parity: a level 30 fighter will hit much more often
        than a level 10 fighter, and a level 30 mage's spells will be harder
        for enemies to resist.
        """
        # Calculate total hit bonus from all classes (take best from each)
        best_hit_bonus = 0
        for role, level in self.levels_by_role.items():
            if role in Constants.HIT_BONUS_PROGRESSION and level > 0:
                # Use level-1 as index (levels are 1-MAX_LEVEL, arrays are 0-(MAX_LEVEL-1))
                level_index = min(level - 1, Constants.MAX_LEVEL - 1)
                class_hit_bonus = Constants.HIT_BONUS_PROGRESSION[role][level_index]
                if class_hit_bonus > best_hit_bonus:
                    best_hit_bonus = class_hit_bonus
        
        # Calculate total dodge bonus (sum from all classes - agility stacks)
        total_dodge_bonus = 0
        for role, level in self.levels_by_role.items():
            if role in Constants.DODGE_BONUS_PROGRESSION and level > 0:
                level_index = min(level - 1, Constants.MAX_LEVEL - 1)
                total_dodge_bonus += Constants.DODGE_BONUS_PROGRESSION[role][level_index]
        
        # Calculate spell power (take best caster class)
        best_spell_power = 0
        for role, level in self.levels_by_role.items():
            if role in Constants.SPELL_POWER_PROGRESSION and level > 0:
                level_index = min(level - 1, Constants.MAX_LEVEL - 1)
                class_spell_power = Constants.SPELL_POWER_PROGRESSION[role][level_index]
                if class_spell_power > best_spell_power:
                    best_spell_power = class_spell_power
        
        # Apply bonuses to base values
        # hit_modifier = base + level bonus (buffs/debuffs are added separately by states)
        self.hit_modifier = self.base_hit_modifier + best_hit_bonus
        self.dodge_modifier = self.base_dodge_modifier + total_dodge_bonus
        self.spell_power = best_spell_power
    
    # ========== Skill-Based Saving Throw System ==========
    # See documentation/saving-throws-design.md for full details
    
    def get_save_skill(self, save_type: str) -> int:
        """
        Get the skill level for a save type (fortitude, reflex, will).
        Save skills are stored in skill_levels dict.
        """
        normalized = save_type.lower()
        return self.skill_levels.get(normalized, 0)
    
    def set_save_skill(self, save_type: str, value: int):
        """Set the skill level for a save type."""
        normalized = save_type.lower()
        self.skill_levels[normalized] = max(0, min(Constants.MAX_SKILL_LEVEL, value))
    
    def get_save_attribute(self, save_type: str) -> int:
        """
        Get the relevant attribute for a save type.
        Fortitude -> Constitution
        Reflex -> Dexterity
        Will -> Wisdom
        """
        normalized = save_type.lower()
        attr_map = {
            "fortitude": CharacterAttributes.CONSTITUTION,
            "reflex": CharacterAttributes.DEXTERITY,
            "will": CharacterAttributes.WISDOM,
            "reason": CharacterAttributes.INTELLIGENCE,  # Future use
        }
        attr = attr_map.get(normalized, CharacterAttributes.CONSTITUTION)
        return self.attributes.get(attr, 10)
    
    def get_save_value(self, save_type: str, gear_bonus: int = 0, buff_bonus: int = 0) -> int:
        """
        Calculate the defender's total save value for opposed checks.
        
        Defender_Save = Save_Skill + (Attribute × ATTRIBUTE_SAVE_MODIFIER) + gear + buffs
        """
        skill = self.get_save_skill(save_type)
        attribute = self.get_save_attribute(save_type)
        attr_bonus = attribute * Constants.ATTRIBUTE_SAVE_MODIFIER
        return skill + attr_bonus + gear_bonus + buff_bonus
    
    def get_penetration_value(self, skill_name: str, relevant_attribute: CharacterAttributes = None,
                               mastery_bonus: int = 0, penetration_bonus: int = 0) -> int:
        """
        Calculate the attacker's penetration value for opposed checks.
        
        Attacker_Penetration = Skill + (Attribute × ATTRIBUTE_SAVE_MODIFIER) + mastery + bonuses
        """
        # Get skill level from any class
        skill_level = self.get_skill_level(skill_name)
        
        # Get attribute bonus
        attr_value = 10
        if relevant_attribute is not None:
            attr_value = self.attributes.get(relevant_attribute, 10)
        attr_bonus = attr_value * Constants.ATTRIBUTE_SAVE_MODIFIER
        
        return skill_level + attr_bonus + mastery_bonus + penetration_bonus
    
    @staticmethod
    def resolve_saving_throw(defender_save: int, attacker_penetration: int, 
                              situational_mod: int = 0, save_bonus_percent: int = 0) -> tuple[int, bool]:
        """
        Resolve an opposed saving throw check.
        
        SaveChance = clamp(50 + (Defender_Save - Attacker_Penetration) + situational_mods, 5, 95) + save_bonus_percent
        
        The save_bonus_percent is applied AFTER clamping, allowing bonuses to exceed the normal
        5-95 limits. A bonus of 100 makes the save automatic (immune).
        
        Returns:
            (save_chance, saved) - The percentage chance and whether the save succeeded
        """
        import random
        
        # Calculate base save chance
        save_chance = 50 + (defender_save - attacker_penetration) + situational_mod
        
        # Clamp to min/max bounds (normal limits)
        save_chance = max(Constants.SAVE_CHANCE_MIN, min(Constants.SAVE_CHANCE_MAX, save_chance))
        
        # Apply save bonus AFTER clamping - this allows exceeding normal limits
        # A 100% bonus means automatic success (immune)
        save_chance = save_chance + save_bonus_percent
        
        # Final cap at 100 (can't exceed 100% success)
        save_chance = min(100, save_chance)
        
        # Roll
        roll = random.randint(1, 100)
        saved = roll <= save_chance
        
        return save_chance, saved
    
    def get_saving_throw_bonus(self, save_type: str) -> int:
        """
        Get the percentage bonus to a saving throw type.
        A bonus of 100 means immune (automatic success).
        """
        normalized = save_type.lower()
        return self.saving_throw_bonuses.get(normalized, 0)
    
    def attempt_save(self, save_type: str, attacker: 'Character', attack_skill: str,
                     attacker_attribute: CharacterAttributes = None,
                     situational_mod: int = 0, gear_bonus: int = 0, buff_bonus: int = 0) -> tuple[int, bool]:
        """
        Attempt a saving throw against an attacker's ability.
        
        Args:
            save_type: "fortitude", "reflex", or "will"
            attacker: The attacking character
            attack_skill: Name of the attacker's skill
            attacker_attribute: Relevant attribute for the attack
            situational_mod: Bonus/penalty to save chance
            gear_bonus: Defender's gear bonus
            buff_bonus: Defender's buff bonus
            
        Returns:
            (save_chance, saved) tuple
        """
        defender_save = self.get_save_value(save_type, gear_bonus, buff_bonus)
        attacker_pen = attacker.get_penetration_value(attack_skill, attacker_attribute)
        save_bonus = self.get_saving_throw_bonus(save_type)
        
        return self.resolve_saving_throw(defender_save, attacker_pen, situational_mod, save_bonus)
    
    def get_mana_regen_rate(self) -> float:
        """Get current mana regen rate based on state."""
        if self.is_meditating:
            return Constants.MANA_REGEN_MEDITATING
        elif self.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            return Constants.MANA_REGEN_RESTING
        elif self.fighting_whom is not None:
            return Constants.MANA_REGEN_COMBAT
        else:
            return Constants.MANA_REGEN_WALKING
    
    def get_stamina_regen_rate(self) -> float:
        """Get current stamina regen rate based on state."""
        if self.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            return Constants.STAMINA_REGEN_RESTING
        elif self.fighting_whom is not None:
            return Constants.STAMINA_REGEN_COMBAT
        else:
            return Constants.STAMINA_REGEN_WALKING
    
    def get_hp_regen_rate(self) -> float:
        """Get current HP regen rate based on state. No HP regen in combat."""
        if self.fighting_whom is not None:
            return Constants.HP_REGEN_COMBAT  # 0 - no regen in combat
        elif self.has_temp_flags(TemporaryCharacterFlags.IS_SLEEPING):
            return Constants.HP_REGEN_SLEEPING
        elif self.has_temp_flags(TemporaryCharacterFlags.IS_SITTING):
            return Constants.HP_REGEN_RESTING
        else:
            return Constants.HP_REGEN_WALKING
    
    def regenerate_resources(self) -> bool:
        """
        Regenerate HP, mana and stamina based on current state. Called each tick.
        Returns True if any resource changed (for status update purposes).
        """
        changed = False
        
        # HP regen (off in combat)
        if self.current_hit_points < self.max_hit_points:
            old_hp = self.current_hit_points
            hp_regen = self.get_hp_regen_rate()
            if hp_regen > 0:
                self.current_hit_points = min(self.max_hit_points, self.current_hit_points + hp_regen)
                if int(self.current_hit_points) != int(old_hp):
                    changed = True
        
        # Mana regen
        if self.current_mana < self.max_mana:
            old_mana = self.current_mana
            self.current_mana = min(self.max_mana, self.current_mana + self.get_mana_regen_rate())
            if int(self.current_mana) != int(old_mana):
                changed = True
        
        # Stamina regen
        if self.current_stamina < self.max_stamina:
            old_stamina = self.current_stamina
            self.current_stamina = min(self.max_stamina, self.current_stamina + self.get_stamina_regen_rate())
            if int(self.current_stamina) != int(old_stamina):
                changed = True
        
        return changed
    
    def use_mana(self, amount: int) -> bool:
        """Attempt to use mana. Returns True if successful, False if not enough."""
        if self.current_mana >= amount:
            self.current_mana -= amount
            return True
        return False
    
    def use_stamina(self, amount: int) -> bool:
        """Attempt to use stamina. Returns True if successful, False if not enough."""
        if self.current_stamina >= amount:
            self.current_stamina -= amount
            return True
        return False
        
    def calculate_damage_multipliers(self):
        """Recalculate damage multipliers including any class-based bonuses"""
        # Original calculation logic
        self.current_damage_multipliers = copy.deepcopy(self.damage_multipliers)
        for item in self.equipped.values():
            if item:
                for dt, mult in item.damage_multipliers.profile.items():
                    self.current_damage_multipliers.profile[dt] = self.current_damage_multipliers.profile[dt] * mult
        
        # Apply class-based multipliers
        # Example: Fighters get better physical multipliers, Mages get better magical multipliers
        if CharacterClassRole.FIGHTER in self.class_priority:
            fighter_level = self.levels_by_role[CharacterClassRole.FIGHTER]
            # Reduce physical damage by 1% per level (multiplicative)
            physical_resist_mult = 1.0 - (fighter_level * 0.01)
            for dt in [DamageType.SLASHING, DamageType.PIERCING, DamageType.BLUDGEONING]:
                self.current_damage_multipliers.profile[dt] *= physical_resist_mult
            
        if CharacterClassRole.MAGE in self.class_priority:
            mage_level = self.levels_by_role[CharacterClassRole.MAGE]
            # Reduce magical damage by 1% per level (multiplicative)
            magic_resist_mult = 1.0 - (mage_level * 0.01)
            for dt in [DamageType.FIRE, DamageType.COLD, DamageType.LIGHTNING, DamageType.ARCANE, DamageType.PSYCHIC]:
                self.current_damage_multipliers.profile[dt] *= magic_resist_mult
            
        # TODO:M: add status effects

    def spend_skill_points(self, skill_name: str, points: int) -> tuple[bool, str]:
        """
        Spend skill points to improve a skill.
        
        The maximum skill level depends on character level and when the skill was unlocked:
        - Level 1 skills (treated as level 0): cap starts at ~32 at level 1, reaches 100 at level 10
        - Level 10 skills: cap starts at 25 at level 10, reaches 100 at level 20
        - Level 20 skills: cap starts at 25 at level 20, reaches 100 at level 30
        - etc. (75 points over 10 levels = 7.5 per level)
        
        YAML overrides can set custom caps per skill.
        
        Args:
            skill_name: The name of the skill (can be partial match)
            points: Number of points to spend
            
        Returns:
            (success, message)
        """
        from ..skills_core import SkillsRegistry, Skills
        
        if points <= 0:
            return False, "You must spend at least 1 skill point."
        
        if points > self.skill_points_available:
            return False, f"You don't have enough skill points. You have {self.skill_points_available}, need {points}."
        
        # Find the skill across all classes
        normalized_input = skill_name.lower().replace(' ', '_').replace('-', '_')
        
        found_skill = None
        found_role = None
        found_skill_name = None
        
        # Check all classes the character has
        for role in self.class_priority:
            if role not in self.skill_levels_by_role:
                continue
            
            # First try exact match
            if normalized_input in self.skill_levels_by_role[role]:
                found_skill_name = normalized_input
                found_role = role
                found_skill = True
                break
            
            # Try partial match
            for sk_name in self.skill_levels_by_role[role].keys():
                if sk_name.startswith(normalized_input) or normalized_input in sk_name:
                    if found_skill is not None:
                        return False, f"Ambiguous skill name '{skill_name}'. Be more specific."
                    found_skill_name = sk_name
                    found_role = role
                    found_skill = True
        
        if not found_skill:
            return False, f"You don't have access to the skill '{skill_name}'."
        
        current_level = self.skill_levels_by_role[found_role][found_skill_name]
        new_level = current_level + points
        
        # Get the skill's level requirement for cap calculation
        skill_requirement_level = self._get_skill_requirement_level(found_role, found_skill_name)
        
        # Check for YAML override cap (stored in skill_cap_overrides dict)
        override_cap = None
        if hasattr(self, 'skill_cap_overrides') and self.skill_cap_overrides:
            override_cap = self.skill_cap_overrides.get(found_skill_name)
        
        # Calculate the dynamic skill cap based on character level and skill tier
        character_level = self.total_levels()
        skill_cap = Skills.calculate_skill_cap(character_level, skill_requirement_level, override_cap)
        
        # Check against dynamic skill cap
        if new_level > skill_cap:
            max_can_spend = skill_cap - current_level
            display_name = found_skill_name.replace('_', ' ').title()
            if max_can_spend <= 0:
                return False, f"'{display_name}' is already at your current cap ({skill_cap}). Level up to increase the cap."
            return False, f"That would exceed your current cap for this skill ({skill_cap}). You can spend at most {max_can_spend} more points on this skill."
        
        # Spend the points
        self.skill_levels_by_role[found_role][found_skill_name] = new_level
        self.skill_points_available -= points
        
        display_name = found_skill_name.replace('_', ' ').title()
        cap_info = f" (cap: {skill_cap})" if skill_cap < 100 else ""
        return True, f"You improved '{display_name}' to level {new_level}{cap_info}. ({self.skill_points_available} skill points remaining)"
    
    def get_available_skills(self) -> dict:
        """
        Get all available skills for the character, organized by class.
        
        Returns:
            Dict[CharacterClassRole, Dict[str, int]] mapping class to skill names and levels
        """
        return self.skill_levels_by_role
    
    def get_skill_level(self, skill_name: str, role: CharacterClassRole = None) -> int:
        """
        Get the level of a specific skill.
        
        Args:
            skill_name: The name of the skill
            role: Optional specific class to check (if None, checks all classes)
            
        Returns:
            The skill level, or 0 if not found
        """
        normalized = skill_name.lower().replace(' ', '_').replace('-', '_')
        
        if role is not None:
            if role in self.skill_levels_by_role:
                return self.skill_levels_by_role[role].get(normalized, 0)
            return 0
        
        # Check all classes
        for r in self.class_priority:
            if r in self.skill_levels_by_role:
                if normalized in self.skill_levels_by_role[r]:
                    return self.skill_levels_by_role[r][normalized]
        return 0

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
        # Use the same auto-populate mechanism but for the specialization class
        self._auto_populate_skills_for_class(specialization, level)
