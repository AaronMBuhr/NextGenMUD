import copy
from custom_detail_logger import CustomDetailLogger
from typing import List
from .actor_interface import ActorType
from .actors import Actor
from .character_interface import CharacterInterface, EquipLocation
from ..communication import CommTypes
from .attacks_and_damage import DamageType, DamageResistances, DamageReduction
from .object_interface import ObjectInterface, ObjectFlags
from .room_interface import RoomInterface
from .triggers import TriggerType, Trigger
from ..utility import get_dice_parts, replace_vars, firstcap



class Object(Actor, ObjectInterface):
    def __init__(self, id: str, zone: 'Zone', name: str = "", create_reference=False):
        super().__init__(ActorType.OBJECT, id, name=name, create_reference=create_reference)
        self.definition_zone_: 'Zone' = zone
        self.name_: str = name
        self.article_ = "" if name == "" else "a" if name[0].lower() in "aeiou" else "an" if name else ""
        self.zone_: 'Zone' = None
        self.in_actor: Actor = None
        self.object_flags_ = ObjectFlags(0)
        self.equipped_location_: EquipLocation = None
        self.equip_locations_: List[EquipLocation] = []
        # for armor
        self.damage_resistances_ = DamageResistances()
        self.damage_reduction_ = DamageReduction()
        # for weapons
        self.attack_bonus_: int = 0
        self.damage_type_: DamageType = None
        self.damage_num_dice_:int = 0
        self.damage_dice_size_:int = 0
        self.damage_bonus_:int = 0
        self.dodge_penalty_:int = 0
        self.weight_:int = 0
        self.value_:int = 0
        self.contents_: List[Object] = []


    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name_,
            'equip_locations': [ loc.name.lower() for loc in self.equip_locations_ ],
            'damage_resistances': self.damage_resistances_.to_dict(),
            'damage_reduction': self.damage_reduction_,
            'damage_type': self.damage_type_.name.lower() if self.damage_type_ else None,
            'damage_dice_number': self.damage_num_dice_,
            'damage_dice_size': self.damage_dice_size_,
            'damage_bonus': self.damage_bonus_,
            'weight': self.weight_
        }
    
    def from_yaml(self, yaml_data: str):
        self.name_ = yaml_data['name']
        self.description_ = yaml_data['description']
        self.article_ = yaml_data['article'] if 'article' in yaml_data else "a" if self.name_[0].lower() in "aeiou" else "an" if self.name_ else ""
        self.pronoun_subject_ = yaml_data['pronoun_subject'] if 'pronoun_subject' in yaml_data else "it"
        self.pronoun_object_ = yaml_data['pronoun_object'] if 'pronoun_object' in yaml_data else "it"
        self.pronoun_possessive_ = yaml_data['pronoun_possessive'] if 'pronoun_possessive' in yaml_data else "its"
        self.weight_ = yaml_data['weight']
        self.value_ = yaml_data['value']
        if 'equip_locations' in yaml_data:
            for el in yaml_data['equip_locations']:
                self.equip_locations_.append(EquipLocation.string_to_enum(el))
        if 'attack_bonus' in yaml_data:
            self.attack_bonus_ = yaml_data['attack_bonus']
        if 'damage_type' in yaml_data:
            self.damage_type_ = DamageType[yaml_data['damage_type'].upper()] if 'damage_type' in yaml_data else None
            dmg_parts = get_dice_parts(yaml_data['damage'])
            self.damage_num_dice_ = dmg_parts[0]
            self.damage_dice_size_ = dmg_parts[1]
            self.damage_bonus_ = dmg_parts[2]
        self.dodge_penalty_ = yaml_data['dodge_penalty'] if 'dodge_penalty' in yaml_data else 0
        if 'damage_resistances' in yaml_data:
            for dt, mult in yaml_data['damage_resistances'].items():
                self.damage_resistances_.set(DamageType[dt.upper()], mult)
        if 'damage_reduction' in yaml_data:
            for dt, amount in yaml_data['damage_reduction'].items():
                self.damage_reduction_.set(DamageType[dt.upper()], amount)

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
                new_trigger = Trigger.new_trigger(trig["type"], self).from_dict(trig)
                if not new_trigger.trigger_type_ in self.triggers_by_type:
                    self.triggers_by_type[new_trigger.trigger_type_] = []
                self.triggers_by_type[new_trigger.trigger_type_].append(new_trigger)
    
    def add_object(self, obj: 'Object', force=False):
        self.contents_.append(obj)
        obj.in_actor = self

    def remove_object(self, obj: 'Object'):
        self.contents_.remove(obj)
        obj.in_actor = None

    async def echo(self, text_type: CommTypes, text: str, vars: dict = None, 
                   exceptions: List['Actor'] = None, already_substituted:bool = False,
                   game_state=None, skip_triggers: bool = False) -> bool:
        logger = CustomDetailLogger(__name__, prefix="Object.echo()> ")
        logger.critical("text before " + text)
        if not already_substituted:
            text = replace_vars(text, vars)
        logger.critical("text after " + text)
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
            return f"{objects[0].article_} {objects[0].name_}"

        multiples = {}
        for obj in objects:
            if obj.name_ in multiples:
                multiples[obj.name_]["count"] += 1 
            else:
                multiples[obj.name_] = {"count": 1, "article": obj.article_}
        
        msg_parts = []
        for name, info in multiples.items():
            if info["count"] >= minimum_qty:
                if info["count"] == 1:
                    msg_parts.append(f"{info['article']} {name}")
                else:
                    msg_parts.append(f"{info['count']} {name}s")
        return separator.join(msg_parts)

    def has_flags(self, flags: ObjectFlags) -> bool:
        return self.object_flags_.are_flags_set(flags)

    def set_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags_.add_flags(flags)
        return True
    
    def remove_flags(self, flags: ObjectFlags) -> bool:
        self.object_flags_.remove_Flags(flags)
        return True
   
    def set_in_room(self, room: RoomInterface):
        self.location_room = room
        
    def set_in_actor(self, actor: Actor):
        self.in_actor = actor
    
    def set_equip_location(self, loc: EquipLocation):
        self.equipped_location_ = loc

    @property
    def art_name(self) -> str:
        return self.character.name
    
    @property
    def art_name_cap(self) -> str:
        return firstcap(self.name)


class Corpse(Object):

    def __init__(self, character: CharacterInterface, room: RoomInterface):
        id = character.id_ + "_corpse"
        super().__init__(id, character.definition_zone_, name=f"{character.art_name_cap}'s corpse", create_reference=True)
        self.article_ = ""
        self.description_ = f"The corpse of {character.art_name} lies here. It makes you feel sad..."
        self.character_ = character
        self.object_flags_.add_flags(ObjectFlags.IS_CONTAINER)
        self.definition_zone_ = None
        self.location_room = room
        self.zone_ = room.zone_
        self.weight_ = 10
        self.original_id = character.zone.id + "." + character.id

    def to_dict(self):
        return {
            'actor_type': self.actor_type.name,
            'rid': self.rid,
            'name': self.name_,
            'character': self.character_.to_dict(),
            'contents': [obj.to_dict() for obj in self.contents_]
        }
    
    def transfer_inventory(self):
        for obj in self.character_.contents_[:]:
            self.character_.remove_object(obj)
            self.add_object(obj)
            obj.location_room = self.character.location_room


