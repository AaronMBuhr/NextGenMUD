import copy
from ..structured_logger import StructuredLogger
from typing import List
from .actor_interface import ActorType
from .actors import Actor
from .character_interface import CharacterInterface, EquipLocation
from ..communication import CommTypes
from ..comprehensive_game_state_interface import GameStateInterface
from .attacks_and_damage import DamageType, DamageMultipliers, DamageReduction
from .object_interface import ObjectInterface, ObjectFlags
from .room_interface import RoomInterface
from .triggers import TriggerType, Trigger
from ..utility import get_dice_parts, generate_article, replace_vars, firstcap, evaluate_functions_in_line



class Object(Actor, ObjectInterface):
    def __init__(self, id: str, definition_zone_id: str, name: str = "", create_reference=False):
        super().__init__(ActorType.OBJECT, id, name=name, create_reference=create_reference)
        self.definition_zone_id: str = definition_zone_id
        # Note: self.name and self.article are set by Actor.__init__
        self.zone: 'Zone' = None
        self.in_actor: Actor = None
        self.object_flags = ObjectFlags(0)
        self.equipped_location: EquipLocation = None
        self.equip_locations: List[EquipLocation] = []
        # for armor
        self.damage_multipliers = DamageMultipliers()
        self.damage_reduction = DamageReduction()
        # for weapons
        self.attack_bonus: int = 0
        self.damage_type: DamageType = None
        self.damage_num_dice:int = 0
        self.damage_dice_size:int = 0
        self.damage_bonus:int = 0
        self.dodge_penalty:int = 0
        self.weight:int = 0
        self.value:int = 0
        self.contents: List[Object] = []
        # Consumable properties
        self.heal_amount: int = 0           # Fixed HP heal
        self.heal_dice: str = ""            # Dice-based heal (e.g., "2d6+4")
        self.mana_restore: int = 0          # Mana restored
        self.stamina_restore: int = 0       # Stamina restored
        self.use_message: str = ""          # Custom message when used
        self.charges: int = -1              # -1 = single use destroyed, 0+ = remaining charges


    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'article': self.article,
            'definition zone id': self.definition_zone_id,
            'equip_locations': [ loc.name.lower() for loc in self.equip_locations ],
            'damage_multipliers': self.damage_multipliers.to_dict(),
            'damage_reduction': self.damage_reduction,
            'damage_type': self.damage_type.name.lower() if self.damage_type else None,
            'damage_dice_number': self.damage_num_dice,
            'damage_dice_size': self.damage_dice_size,
            'damage_bonus': self.damage_bonus,
            'weight': self.weight,
            'value': self.value
        }
    
    def from_yaml(self, yaml_data: str, definition_zone_id: str,game_state: GameStateInterface = None):
        logger = StructuredLogger(__name__, prefix="Object.from_yaml()> ")
        try:
            self.id = yaml_data['id']
            self.name = yaml_data['name']
            self.definition_zone_id = definition_zone_id
            self.description_ = yaml_data['description']
            self.article = yaml_data['article'] if 'article' in yaml_data else generate_article(self.name)
            self.pronoun_subject_ = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
            self.pronoun_object_ = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
            self.pronoun_possessive_ = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
            self.weight = yaml_data.get('weight', 0)
            self.value = yaml_data.get('value', 0)
            if 'equip_locations' in yaml_data:
                logger.debug3(f"object.from_yaml()> equip_locations: {yaml_data['equip_locations']}")
                for el in yaml_data['equip_locations']:
                    self.equip_locations.append(EquipLocation.string_to_enum(el))
            logger.debug3(f"object.from_yaml()> attack bonus")
            if 'attack_bonus' in yaml_data:
                self.attack_bonus = yaml_data['attack_bonus']
            logger.debug3(f"object.from_yaml()> damage_type")
            if 'damage_type' in yaml_data:
                self.damage_type = DamageType[yaml_data['damage_type'].upper()] if 'damage_type' in yaml_data else None
                dmg_parts = get_dice_parts(yaml_data['damage'])
                self.damage_num_dice = dmg_parts[0]
                self.damage_dice_size = dmg_parts[1]
                self.damage_bonus = dmg_parts[2]
            self.dodge_penalty = yaml_data['dodge_penalty'] if 'dodge_penalty' in yaml_data else 0
            logger.debug3(f"object.from_yaml()> damage_multipliers")
            if 'damage_multipliers' in yaml_data:
                for dt, mult in yaml_data['damage_multipliers'].items():
                    self.damage_multipliers.set(DamageType[dt.upper()], mult)
            logger.debug3(f"object.from_yaml()> damage_reduction")
            if 'damage_reduction' in yaml_data:
                for dt, amount in yaml_data['damage_reduction'].items():
                    self.damage_reduction.set(DamageType[dt.upper()], amount)

            logger.debug3(f"object.from_yaml()> triggers")
            if 'triggers' in yaml_data:
                # print(f"triggers: {yaml_data['triggers']}")
                # raise NotImplementedError("Triggers not implemented yet.")
                # for trigger_type, trigger_info in yaml_data['triggers'].items():
                #     # logger.debug3(f"loading trigger_type: {trigger_type}")
                #     if not trigger_type in self.triggers_by_type_:
                #         self.triggers_by_type_[trigger_type] = []
                #     self.triggers_by_type_[trigger_type] += trigger_info
                for trig in yaml_data['triggers']:
                    # logger.debug3(f"loading trigger_type: {trigger_type}")
                    # Triggers on definitions should be disabled; they get enabled when instances are created
                    new_trigger = Trigger.new_trigger(trig["type"], self, disabled=True).from_dict(trig)
                    self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
            
            # Consumable properties
            logger.debug3(f"object.from_yaml()> consumable properties")
            if 'heal_amount' in yaml_data:
                self.heal_amount = yaml_data['heal_amount']
            if 'heal_dice' in yaml_data:
                self.heal_dice = yaml_data['heal_dice']
            if 'mana_restore' in yaml_data:
                self.mana_restore = yaml_data['mana_restore']
            if 'stamina_restore' in yaml_data:
                self.stamina_restore = yaml_data['stamina_restore']
            if 'use_message' in yaml_data:
                self.use_message = yaml_data['use_message']
            if 'charges' in yaml_data:
                self.charges = yaml_data['charges']
            
            # Object permanent flags
            logger.debug3(f"object.from_yaml()> permanent_flags")
            flags_data = yaml_data.get('permanent_flags', [])
            for flag_name in flags_data:
                flag_name_upper = flag_name.upper().replace("-", "_")
                if hasattr(ObjectFlags, flag_name_upper):
                    self.object_flags = self.object_flags.add_flags(getattr(ObjectFlags, flag_name_upper))
                elif hasattr(ObjectFlags, f"IS_{flag_name_upper}"):
                    self.object_flags = self.object_flags.add_flags(getattr(ObjectFlags, f"IS_{flag_name_upper}"))
                        
        except Exception as e:
            logger.error("Error loading object from yaml")
            logger.error("yaml_data: " + str(yaml_data))
            logger.error(f"Error: {e}")
            raise e

    def add_object(self, obj: 'Object', force=False):
        self.contents.append(obj)
        obj.in_actor = self

    def remove_object(self, obj: 'Object'):
        self.contents.remove(obj)
        obj.in_actor = None

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted:bool = False,
                   game_state=None, skip_triggers: bool = False) -> bool:
        logger = StructuredLogger(__name__, prefix="Object.echo()> ")
        logger.debug3("text before " + text)
        if not already_substituted:
            text = evaluate_functions_in_line(replace_vars(text, vars), vars, game_state)
        logger.debug3("text after " + text)
        return await super().echo(text_type, text, vars, exceptions, game_state=game_state, skip_triggers=skip_triggers)
    
    @classmethod
    def create_from_definition(cls, obj_def: 'Object') -> 'Object':
        new_obj = copy.deepcopy(obj_def)
        if not new_obj.reference_number or new_obj.reference_number == obj_def.reference_number:
            new_obj.create_reference()
        for trig_type, trig_data in new_obj.triggers_by_type.items():
            for trig in trig_data:
                trig.actor_ = new_obj
                trig.enable()
        return new_obj
    
    @classmethod
    def collapse_name_multiples(cls, objects: List['Object'], separator: str, minimum_qty=1):
        if len(objects) == 0:
            return ""
        elif len(objects) == 1:
            return f"{objects[0].article} {objects[0].name}"

        multiples = {}
        for obj in objects:
            if obj.name in multiples:
                multiples[obj.name]["count"] += 1 
            else:
                multiples[obj.name] = {"count": 1, "article": obj.article}
        
        msg_parts = []
        for name, info in multiples.items():
            if info["count"] >= minimum_qty:
                if info["count"] == 1:
                    msg_parts.append(f"{info['article']} {name}")
                else:
                    msg_parts.append(f"{info['count']} {name}s")
        return separator.join(msg_parts)

    def has_flags(self, flags: ObjectFlags) -> bool:
        return self.object_flags.are_flags_set(flags)

    def set_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags = self.object_flags.add_flags(flags)
        return True
    
    def remove_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags.remove_Flags(flags)
        return True
   
    @property
    def location_room(self) -> 'Room':
        return self.in_actor if isinstance(self.in_actor, RoomInterface) else None

    @location_room.setter
    def location_room(self, room: 'Room'):
        self.in_actor = room
        
    def set_in_actor(self, actor: Actor):
        self.in_actor = actor
    
    def set_equip_location(self, loc: EquipLocation):
        self.equipped_location = loc

    @property
    def art_name(self) -> str:
        return ((self.article + " ") if self.article else "") + self.name
    
    @property
    def art_name_cap(self) -> str:
        return firstcap(self.art_name)


class Corpse(Object):

    def __init__(self, character: CharacterInterface, room: RoomInterface):
        id = character.id + "_corpse"
        super().__init__(id, character.definition_zone_id, name=f"{character.art_name_cap}'s corpse", create_reference=True)
        self.article = ""
        self.description = f"The corpse of {character.art_name} lies here. It makes you feel sad..."
        self.character = character
        self.object_flags = self.object_flags.add_flags(ObjectFlags.IS_CONTAINER)
        self.definition_zone_id = None
        self._location_room = room
        self.zone = room.zone
        self.weight = 10
        self.original_id = character.definition_zone_id + "." + character.id
        self.owner_id = None  # For player corpses, only owner can loot
    
    def can_be_looted_by(self, actor) -> bool:
        """Check if the given actor can loot this corpse."""
        # NPC corpses (no owner) can be looted by anyone
        if self.owner_id is None:
            return True
        # Player corpses can only be looted by their owner
        return actor.id == self.owner_id

    def to_dict(self):
        return {
            'actor_type': self.actor_type.name,
            'rid': self.rid,
            'name': self.name,
            'character': self.character.to_dict(),
            'contents': [obj.to_dict() for obj in self.contents]
        }
    
    def transfer_inventory(self):
        """Transfer ALL items from character to corpse (for NPCs)."""
        for obj in self.character.contents[:]:
            self.character.remove_object(obj)
            self.add_object(obj)
            obj.location_room = self.character.location_room

    def transfer_inventory_only(self):
        """
        Transfer only non-equipped inventory items to corpse (for players).
        Equipped items stay on the player.
        """
        for obj in self.character.contents[:]:
            # Skip items that are equipped
            if obj.equip_location is not None:
                continue
            self.character.remove_object(obj)
            self.add_object(obj)
            obj.location_room = self._location_room


