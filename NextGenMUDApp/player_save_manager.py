"""
Player Save Manager - Handles saving and loading player characters to/from YAML files.

Each player character is stored in a separate YAML file in the player_saves directory.
Files are named {character_name}.yaml with spaces converted to dashes.
"""

import os
import hashlib
import secrets
from typing import Optional, Dict, Any, List
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .structured_logger import StructuredLogger
from .constants import Constants, CharacterClassRole


class PasswordManager:
    """Handles password hashing and verification using PBKDF2-SHA256."""
    
    ITERATIONS = 260000  # OWASP recommended minimum for PBKDF2-SHA256
    SALT_LENGTH = 32
    KEY_LENGTH = 32
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Hash a password using PBKDF2-SHA256 with a random salt.
        Returns a string in format: salt$hash (both hex-encoded)
        """
        salt = secrets.token_bytes(cls.SALT_LENGTH)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            cls.ITERATIONS,
            dklen=cls.KEY_LENGTH
        )
        return f"{salt.hex()}${key.hex()}"
    
    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        """
        Verify a password against a stored hash.
        Returns True if password matches, False otherwise.
        """
        try:
            salt_hex, key_hex = stored_hash.split('$')
            salt = bytes.fromhex(salt_hex)
            stored_key = bytes.fromhex(key_hex)
            
            computed_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                cls.ITERATIONS,
                dklen=cls.KEY_LENGTH
            )
            return secrets.compare_digest(computed_key, stored_key)
        except (ValueError, AttributeError):
            return False


class PlayerSaveManager:
    """Manages saving and loading player characters to/from YAML files."""
    
    def __init__(self, saves_dir: str = None):
        self.saves_dir = saves_dir or Constants.PLAYER_SAVES_DIR
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = True
        self._ensure_saves_directory()
        
    def _ensure_saves_directory(self):
        """Create the saves directory if it doesn't exist."""
        if not os.path.exists(self.saves_dir):
            os.makedirs(self.saves_dir)
            
    def _character_name_to_filename(self, character_name: str) -> str:
        """Convert a character name to a safe filename."""
        # Replace spaces with dashes, convert to lowercase for consistency
        safe_name = character_name.replace(' ', '-').lower()
        # Remove any other potentially problematic characters
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '-')
        return f"{safe_name}.yaml"
    
    def _get_save_path(self, character_name: str) -> str:
        """Get the full path to a character's save file."""
        filename = self._character_name_to_filename(character_name)
        return os.path.join(self.saves_dir, filename)
    
    def character_exists(self, character_name: str) -> bool:
        """Check if a save file exists for a character."""
        return os.path.exists(self._get_save_path(character_name))
    
    def verify_password(self, character_name: str, password: str) -> bool:
        """Verify a password for an existing character."""
        logger = StructuredLogger(__name__, prefix="verify_password()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return False
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            if not data or 'password_hash' not in data:
                logger.warning(f"No password hash found for character {character_name}")
                return False
                
            return PasswordManager.verify_password(password, data['password_hash'])
        except Exception as e:
            logger.error(f"Error verifying password for {character_name}: {e}")
            return False
    
    def save_character(self, character: 'Character', 
                       save_states: bool = None,
                       save_cooldowns: bool = None,
                       password: str = None) -> bool:
        """
        Save a character to a YAML file.
        
        Args:
            character: The Character object to save
            save_states: Whether to save temporary states (default from config)
            save_cooldowns: Whether to save cooldowns (default from config)
            password: Password to set (only for new characters or password change)
            
        Returns:
            True if save successful, False otherwise
        """
        logger = StructuredLogger(__name__, prefix="save_character()> ")
        
        if save_states is None:
            save_states = Constants.SAVE_CHARACTER_STATES
        if save_cooldowns is None:
            save_cooldowns = Constants.SAVE_CHARACTER_COOLDOWNS
            
        try:
            save_path = self._get_save_path(character.name)
            
            # Load existing data to preserve password hash if not changing it
            existing_data = {}
            if os.path.exists(save_path):
                with open(save_path, 'r', encoding='utf-8') as f:
                    existing_data = self.yaml.load(f) or {}
            
            # Build save data
            save_data = self._character_to_dict(character, save_states, save_cooldowns)
            
            # Handle password
            if password:
                save_data['password_hash'] = PasswordManager.hash_password(password)
            elif 'password_hash' in existing_data:
                save_data['password_hash'] = existing_data['password_hash']
            
            # Write to file
            with open(save_path, 'w', encoding='utf-8') as f:
                self.yaml.dump(save_data, f)
                
            logger.info(f"Character {character.name} saved to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving character {character.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_character(self, character_name: str, target_character: 'Character' = None,
                       restore_location: bool = False) -> Optional[Dict[str, Any]]:
        """
        Load character data from a YAML file.
        
        Args:
            character_name: Name of the character to load
            target_character: Optional Character object to populate with loaded data
            restore_location: Whether to restore the saved location (for combat reconnection)
            
        Returns:
            Dictionary of character data, or None if load failed
        """
        logger = StructuredLogger(__name__, prefix="load_character()> ")
        
        try:
            save_path = self._get_save_path(character_name)
            
            if not os.path.exists(save_path):
                logger.warning(f"Save file not found: {save_path}")
                return None
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            if not data:
                logger.warning(f"Empty or invalid save file: {save_path}")
                return None
            
            if target_character:
                self._apply_data_to_character(data, target_character, restore_location)
                
            logger.info(f"Character {character_name} loaded from {save_path}")
            return data
            
        except YAMLError as e:
            logger.error(f"YAML error loading {character_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading character {character_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_new_character(self, character_name: str, password: str, selected_class: str = None,
                              allocated_stats: dict = None) -> bool:
        """
        Create a new character save file with name, password, selected class, and allocated stats.
        The actual character will be created from template when they log in.
        
        Args:
            character_name: Name for the new character
            password: Password for the new character
            selected_class: The class chosen by the player (fighter, rogue, mage, cleric)
            allocated_stats: Dict of stat allocations (e.g., {'STRENGTH': 12, 'DEXTERITY': 14, ...})
            
        Returns:
            True if creation successful, False otherwise
        """
        logger = StructuredLogger(__name__, prefix="create_new_character()> ")
        
        try:
            if self.character_exists(character_name):
                logger.warning(f"Character {character_name} already exists")
                return False
                
            save_data = {
                'name': character_name,
                'password_hash': PasswordManager.hash_password(password),
                'selected_class': selected_class or 'fighter'  # Default to fighter if not specified
            }
            
            # Store allocated stats if provided
            if allocated_stats:
                save_data['allocated_stats'] = allocated_stats
            
            save_path = self._get_save_path(character_name)
            with open(save_path, 'w', encoding='utf-8') as f:
                self.yaml.dump(save_data, f)
                
            logger.info(f"New character {character_name} ({selected_class}) created with stats: {allocated_stats}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating new character {character_name}: {e}")
            return False
    
    def get_selected_class(self, character_name: str) -> Optional[str]:
        """Get the selected class for a new character."""
        logger = StructuredLogger(__name__, prefix="get_selected_class()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return None
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            return data.get('selected_class', 'fighter')
        except Exception as e:
            logger.error(f"Error getting selected class for {character_name}: {e}")
            return 'fighter'  # Default
    
    def get_allocated_stats(self, character_name: str) -> Optional[dict]:
        """Get the allocated stats for a new character."""
        logger = StructuredLogger(__name__, prefix="get_allocated_stats()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return None
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            return data.get('allocated_stats', None)
        except Exception as e:
            logger.error(f"Error getting allocated stats for {character_name}: {e}")
            return None
    
    def _character_to_dict(self, character: 'Character', 
                           save_states: bool, save_cooldowns: bool) -> Dict[str, Any]:
        """Convert a Character object to a saveable dictionary."""
        from .nondb_models.character_interface import EquipLocation, CharacterAttributes
        from .nondb_models.attacks_and_damage import DamageType
        
        data = {
            'name': character.name,
            'description': character.description,
            'article': character.article,
            'pronoun_subject': character.pronoun_subject,
            'pronoun_object': character.pronoun_object,
            'pronoun_possessive': character.pronoun_possessive,
            
            # Location (for potential combat reconnection)
            'location': {
                'zone': character.location_room.zone.id if character.location_room else None,
                'room': character.location_room.id if character.location_room else None
            },
            'was_in_combat': character.fighting_whom is not None,
            
            # Class information
            'class_priority': [role.name for role in character.class_priority],
            'levels_by_role': {role.name: level for role, level in character.levels_by_role.items()},
            'specializations': {base.name: spec.name for base, spec in character.specializations.items()},
            
            # Skills (legacy format)
            'skill_levels': character.skill_levels.copy() if hasattr(character, 'skill_levels') else {},
            'skill_points_available': character.skill_points_available,
            
            # Skills by class (new format)
            'skill_levels_by_role': {
                role.name: skills.copy() 
                for role, skills in character.skill_levels_by_role.items()
            } if hasattr(character, 'skill_levels_by_role') else {},
            
            # Attributes
            'attributes': {attr.name: val for attr, val in character.attributes.items()},
            
            # Flags (permanent only - temporary flags are states)
            'permanent_flags': character.permanent_character_flags.value,
            'game_permission_flags': character.game_permission_flags.value,
            
            # Stats
            'experience_points': character.experience_points,
            'hit_dice': character.hit_dice,
            'hit_dice_size': character.hit_dice_size,
            'hit_point_bonus': character.hit_point_bonus,
            'max_hit_points': character.max_hit_points,
            'current_hit_points': character.current_hit_points,
            'max_mana': character.max_mana,
            'current_mana': int(character.current_mana),
            'max_stamina': character.max_stamina,
            'current_stamina': int(character.current_stamina),
            'max_carrying_capacity': character.max_carrying_capacity,
            
            # Combat stats (base values - level bonuses are recalculated on load)
            'base_hit_modifier': character.base_hit_modifier,
            'base_dodge_modifier': character.base_dodge_modifier,
            'dodge_dice_number': character.dodge_dice_number,
            'dodge_dice_size': character.dodge_dice_size,
            'critical_chance': character.critical_chance,
            'critical_multiplier': character.critical_multiplier,
            'num_main_hand_attacks': character.num_main_hand_attacks,
            'num_off_hand_attacks': character.num_off_hand_attacks,
            
            # Damage multipliers and reductions
            'damage_multipliers': {dt.name: val for dt, val in character.damage_multipliers.profile.items()},
            'damage_reduction': {dt.name: val for dt, val in character.damage_reduction.items()},
            
            # Inventory
            'inventory': [self._object_to_dict(obj) for obj in character.contents],
            
            # Equipment
            'equipment': {
                loc.name: self._object_to_dict(obj) if obj else None 
                for loc, obj in character.equipped.items()
            },
        }
        
        # Save temporary states if configured
        if save_states:
            data['temporary_flags'] = character.temporary_character_flags.value
            data['states'] = [self._state_to_dict(state) for state in character.current_states]
        
        # Save cooldowns if configured  
        if save_cooldowns:
            data['cooldowns'] = [self._cooldown_to_dict(cd) for cd in character.cooldowns]
            
        return data
    
    def _object_to_dict(self, obj: 'Object') -> Dict[str, Any]:
        """Convert an Object to a saveable dictionary."""
        from .nondb_models.objects import ObjectFlags
        
        return {
            'id': obj.id,
            'definition_zone_id': obj.definition_zone_id,
            'name': obj.name,
            'article': obj.article,
            'description': getattr(obj, 'description_', ''),
            'weight': obj.weight,
            'value': obj.value,
            'object_flags': obj.object_flags.value,
            'equip_locations': [loc.name for loc in obj.equip_locations],
            'equipped_location': obj.equipped_location.name if obj.equipped_location else None,
            'damage_multipliers': {dt.name: val for dt, val in obj.damage_multipliers.profile.items()},
            'damage_reduction': {dt.name: val for dt, val in obj.damage_reduction.profile.items()},
            'damage_type': obj.damage_type.name if obj.damage_type else None,
            'damage_num_dice': obj.damage_num_dice,
            'damage_dice_size': obj.damage_dice_size,
            'damage_bonus': obj.damage_bonus,
            'attack_bonus': obj.attack_bonus,
            'dodge_penalty': obj.dodge_penalty,
            'contents': [self._object_to_dict(c) for c in obj.contents] if hasattr(obj, 'contents') else []
        }
    
    def _state_to_dict(self, state: 'ActorState') -> Dict[str, Any]:
        """Convert an ActorState to a saveable dictionary."""
        return {
            'type': type(state).__name__,
            'start_tick': state.start_tick if hasattr(state, 'start_tick') else 0,
            'duration_ticks': state.duration_ticks if hasattr(state, 'duration_ticks') else 0,
            # Additional state-specific data could be added here
        }
    
    def _cooldown_to_dict(self, cooldown: 'Cooldown') -> Dict[str, Any]:
        """Convert a Cooldown to a saveable dictionary."""
        return {
            'name': cooldown.name if hasattr(cooldown, 'name') else '',
            'source_type': type(cooldown.source).__name__ if hasattr(cooldown, 'source') and cooldown.source else None,
            'start_tick': cooldown.start_tick if hasattr(cooldown, 'start_tick') else 0,
            'duration_ticks': cooldown.duration_ticks if hasattr(cooldown, 'duration_ticks') else 0,
        }
    
    def _apply_data_to_character(self, data: Dict[str, Any], character: 'Character',
                                  restore_location: bool = False):
        """Apply loaded data to a Character object."""
        from .nondb_models.character_interface import (
            PermanentCharacterFlags, TemporaryCharacterFlags, 
            GamePermissionFlags, EquipLocation, CharacterAttributes
        )
        from .nondb_models.attacks_and_damage import DamageType, DamageMultipliers
        from .nondb_models.objects import Object, ObjectFlags
        
        logger = StructuredLogger(__name__, prefix="_apply_data_to_character()> ")
        
        try:
            # Basic info
            character.name = data.get('name', character.name)
            character.description = data.get('description', character.description)
            character.article = data.get('article', character.article)
            character.pronoun_subject = data.get('pronoun_subject', 'it')
            character.pronoun_object = data.get('pronoun_object', 'it')
            character.pronoun_possessive = data.get('pronoun_possessive', 'its')
            
            # Class information
            if 'class_priority' in data:
                character.class_priority = []
                for role_name in data['class_priority']:
                    try:
                        character.class_priority.append(CharacterClassRole[role_name])
                    except KeyError:
                        logger.warning(f"Unknown class role: {role_name}")
                        
            if 'levels_by_role' in data:
                character.levels_by_role = {}
                for role_name, level in data['levels_by_role'].items():
                    try:
                        character.levels_by_role[CharacterClassRole[role_name]] = level
                    except KeyError:
                        logger.warning(f"Unknown class role: {role_name}")
                        
            if 'specializations' in data:
                character.specializations = {}
                for base_name, spec_name in data['specializations'].items():
                    try:
                        character.specializations[CharacterClassRole[base_name]] = CharacterClassRole[spec_name]
                    except KeyError:
                        logger.warning(f"Unknown specialization: {base_name} -> {spec_name}")
            
            # Skills (legacy format)
            if 'skill_levels' in data:
                character.skill_levels = data['skill_levels'].copy()
            character.skill_points_available = data.get('skill_points_available', 0)
            
            # Skills by class (new format)
            if 'skill_levels_by_role' in data:
                character.skill_levels_by_role = {}
                for role_name, skills in data['skill_levels_by_role'].items():
                    try:
                        role = CharacterClassRole[role_name]
                        character.skill_levels_by_role[role] = skills.copy()
                    except KeyError:
                        logger.warning(f"Unknown class role in skills: {role_name}")
            
            # Attributes
            if 'attributes' in data:
                for attr_name, val in data['attributes'].items():
                    try:
                        character.attributes[CharacterAttributes[attr_name]] = val
                    except KeyError:
                        logger.warning(f"Unknown attribute: {attr_name}")
            
            # Flags
            if 'permanent_flags' in data:
                character.permanent_character_flags = PermanentCharacterFlags(data['permanent_flags'])
            if 'game_permission_flags' in data:
                character.game_permission_flags = GamePermissionFlags(data['game_permission_flags'])
            if 'temporary_flags' in data:
                character.temporary_character_flags = TemporaryCharacterFlags(data['temporary_flags'])
            
            # Stats
            character.experience_points = data.get('experience_points', 0)
            character.hit_dice = data.get('hit_dice', 1)
            character.hit_dice_size = data.get('hit_dice_size', 10)
            character.hit_point_bonus = data.get('hit_point_bonus', 0)
            character.max_hit_points = data.get('max_hit_points', 10)
            character.current_hit_points = data.get('current_hit_points', character.max_hit_points)
            character.max_mana = data.get('max_mana', 0)
            character.current_mana = data.get('current_mana', character.max_mana)
            character.max_stamina = data.get('max_stamina', 0)
            character.current_stamina = data.get('current_stamina', character.max_stamina)
            character.max_carrying_capacity = data.get('max_carrying_capacity', 100)
            
            # Combat stats (base values - level bonuses calculated after)
            # Support loading old saves that had hit_modifier instead of base_hit_modifier
            character.base_hit_modifier = data.get('base_hit_modifier', data.get('hit_modifier', 50))
            character.base_dodge_modifier = data.get('base_dodge_modifier', data.get('dodge_modifier', 0))
            character.dodge_dice_number = data.get('dodge_dice_number', 1)
            character.dodge_dice_size = data.get('dodge_dice_size', 50)
            character.critical_chance = data.get('critical_chance', 5)
            character.critical_multiplier = data.get('critical_multiplier', 200)
            character.num_main_hand_attacks = data.get('num_main_hand_attacks', 1)
            character.num_off_hand_attacks = data.get('num_off_hand_attacks', 0)
            
            # Recalculate level-based combat bonuses (hit_modifier, dodge_modifier, spell_power)
            character.calculate_combat_bonuses()
            
            # Damage multipliers
            if 'damage_multipliers' in data:
                for dt_name, val in data['damage_multipliers'].items():
                    try:
                        character.damage_multipliers.profile[DamageType[dt_name]] = val
                    except KeyError:
                        logger.warning(f"Unknown damage type: {dt_name}")
                        
            if 'damage_reduction' in data:
                for dt_name, val in data['damage_reduction'].items():
                    try:
                        character.damage_reduction[DamageType[dt_name]] = val
                    except KeyError:
                        logger.warning(f"Unknown damage type: {dt_name}")
            
            # Clear and restore inventory
            character.contents = []
            if 'inventory' in data:
                for obj_data in data['inventory']:
                    obj = self._dict_to_object(obj_data)
                    if obj:
                        character.add_object(obj)
            
            # Clear and restore equipment
            character.equipped = {loc: None for loc in EquipLocation}
            if 'equipment' in data:
                for loc_name, obj_data in data['equipment'].items():
                    if obj_data:
                        try:
                            loc = EquipLocation[loc_name]
                            obj = self._dict_to_object(obj_data)
                            if obj:
                                character.equip_item(loc, obj)
                        except KeyError:
                            logger.warning(f"Unknown equip location: {loc_name}")
            
            # States and cooldowns would need more complex restoration
            # For now we'll skip restoring actual state objects
            
            logger.info(f"Applied save data to character {character.name}")
            
        except Exception as e:
            logger.error(f"Error applying data to character: {e}")
            import traceback
            traceback.print_exc()
    
    def _dict_to_object(self, data: Dict[str, Any]) -> Optional['Object']:
        """Convert a dictionary back to an Object."""
        from .nondb_models.character_interface import EquipLocation
        from .nondb_models.attacks_and_damage import DamageType, DamageMultipliers, DamageReduction
        from .nondb_models.objects import Object, ObjectFlags
        
        logger = StructuredLogger(__name__, prefix="_dict_to_object()> ")
        
        try:
            obj = Object(
                id=data.get('id', 'unknown'),
                definition_zone_id=data.get('definition_zone_id', 'unknown'),
                name=data.get('name', 'Unknown Object'),
                create_reference=True
            )
            
            obj.article = data.get('article', '')
            obj.description_ = data.get('description', '')
            obj.weight = data.get('weight', 0)
            obj.value = data.get('value', 0)
            obj.object_flags = ObjectFlags(data.get('object_flags', 0))
            
            # Equip locations
            obj.equip_locations = []
            for loc_name in data.get('equip_locations', []):
                try:
                    obj.equip_locations.append(EquipLocation[loc_name])
                except KeyError:
                    pass
                    
            if data.get('equipped_location'):
                try:
                    obj.equipped_location = EquipLocation[data['equipped_location']]
                except KeyError:
                    pass
            
            # Damage multipliers
            if 'damage_multipliers' in data:
                for dt_name, val in data['damage_multipliers'].items():
                    try:
                        obj.damage_multipliers.set(DamageType[dt_name], val)
                    except KeyError:
                        pass
                        
            if 'damage_reduction' in data:
                for dt_name, val in data['damage_reduction'].items():
                    try:
                        obj.damage_reduction.set(DamageType[dt_name], val)
                    except KeyError:
                        pass
            
            # Weapon stats
            if data.get('damage_type'):
                try:
                    obj.damage_type = DamageType[data['damage_type']]
                except KeyError:
                    pass
            obj.damage_num_dice = data.get('damage_num_dice', 0)
            obj.damage_dice_size = data.get('damage_dice_size', 0)
            obj.damage_bonus = data.get('damage_bonus', 0)
            obj.attack_bonus = data.get('attack_bonus', 0)
            obj.dodge_penalty = data.get('dodge_penalty', 0)
            
            # Contents (for containers)
            for content_data in data.get('contents', []):
                content_obj = self._dict_to_object(content_data)
                if content_obj:
                    obj.add_object(content_obj)
            
            return obj
            
        except Exception as e:
            logger.error(f"Error creating object from dict: {e}")
            return None
    
    def get_character_was_in_combat(self, character_name: str) -> bool:
        """Check if a character was in combat when they last saved."""
        logger = StructuredLogger(__name__, prefix="get_character_was_in_combat()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return False
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            return data.get('was_in_combat', False)
        except Exception as e:
            logger.error(f"Error checking combat status for {character_name}: {e}")
            return False
    
    def get_character_location(self, character_name: str) -> Optional[Dict[str, str]]:
        """Get the saved location for a character."""
        logger = StructuredLogger(__name__, prefix="get_character_location()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return None
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
                
            return data.get('location')
        except Exception as e:
            logger.error(f"Error getting location for {character_name}: {e}")
            return None
    
    def is_stub_save(self, character_name: str) -> bool:
        """
        Check if a character save file is a stub (just credentials + creation choices)
        vs a full character save. A stub file hasn't been fully instantiated yet.
        """
        logger = StructuredLogger(__name__, prefix="is_stub_save()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return True  # No save file means definitely needs creation
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
            
            # A stub file won't have character data like 'level' or 'class_priority'
            # These are only present after the character has been fully created and saved
            return 'level' not in data and 'class_priority' not in data
        except Exception as e:
            logger.error(f"Error checking stub status for {character_name}: {e}")
            return True
    
    def is_fresh_character(self, character_name: str, starting_skill_points: int = 60) -> bool:
        """
        Check if a character is "fresh" (new player experience).
        A fresh character is level 1 with all starting skill points unspent.
        Also returns True for stub saves (character hasn't logged in yet).
        """
        logger = StructuredLogger(__name__, prefix="is_fresh_character()> ")
        try:
            save_path = self._get_save_path(character_name)
            if not os.path.exists(save_path):
                return True
                
            with open(save_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
            
            # Stub file = fresh (no class_priority means not fully created yet)
            if 'class_priority' not in data:
                return True
            
            # Check if level 1 with starting skill points
            # Use levels_by_role to calculate total level (not the old 'level' field)
            levels_by_role = data.get('levels_by_role', {})
            total_level = sum(levels_by_role.values()) if levels_by_role else 1
            skill_points = data.get('skill_points_available', 0)
            
            return total_level == 1 and skill_points >= starting_skill_points
        except Exception as e:
            logger.error(f"Error checking fresh character status for {character_name}: {e}")
            return True


# Global instance
player_save_manager = PlayerSaveManager()
