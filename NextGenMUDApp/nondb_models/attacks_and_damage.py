from enum import Enum
import random
from typing import List
from custom_detail_logger import CustomDetailLogger
from ..utility import get_dice_parts


class DamageType(Enum):
    SLASHING = 1
    PIERCING = 2
    BLUDGEONING = 3
    FIRE = 4
    COLD = 5
    LIGHTNING = 6
    ACID = 7
    POISON = 8
    DISEASE = 9
    HOLY = 10
    UNHOLY = 11
    ARCANE = 12
    PSYCHIC = 13
    FORCE = 14
    NECROTIC = 15
    RADIANT = 16

    def word(self):
        return self.name.lower()
    
    def verb(self):
        return ['slashes','pierces','bludgeons','burns','freezes','shocks',
                'corrodes','poisons','diseases','burns','corrupts','zaps',
                'mentally crushes','crushes','corrupts','burns'][self.value - 1]
    def noun(self):
        return ['slash','pierce','bludgeon','burn','freeze','shock',
                'corrode','poison','disease','burn','corrupt','zap',
                'mental crush','crush','corrupt','burn'][self.value - 1]
    


class DamageResistances:
    def __init__(self, profile=None):
        if profile:
            self.profile_ = profile
        else:
            self.profile_ = {loc: 1 for loc in DamageType}

    def to_dict(self):
        # return {EquipLocation[loc].name.lower(): dt.name.lower() for loc, dt in self.profile_.items()}
        return repr(self.profile_)

    def set(self, damage_type: DamageType, amount: float):
        self.profile_[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile_[damage_type]

class DamageReduction:
    def __init__(self, profile=None):
        if profile:
            self.profile_ = profile
        else:
            self.profile_ = {loc: 0 for loc in DamageType}

    def set(self, damage_type: DamageType, amount: float):
        self.profile_[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile_[damage_type]

    def to_dict(self):
        return repr(self.profile_)

class PotentialDamage:
    def __init__(self, damage_type: DamageType, damage_dice_number: int, damage_dice_type: int, damage_dice_bonus: int):
        self.damage_type_ = damage_type
        self.damage_dice_number_ = damage_dice_number
        self.damage_dice_type_ = damage_dice_type
        self.damage_dice_bonus_ = damage_dice_bonus
        self.min_damage_ = damage_dice_number + damage_dice_bonus
        self.max_damage_ = damage_dice_number * damage_dice_type + damage_dice_bonus
        self.glancing_damage_ = (self.max_damage_ - self.min_damage_) * 0.20 + self.min_damage_
        self.powerful_damage_ = (self.max_damage_ - self.min_damage_) * 0.80 + self.min_damage_

    def to_dict(self):
        return {
            "damage": f"{self.damage_dice_number_}d{self.damage_dice_type_}+{self.damage_dice_bonus_}",
            "damage_type": self.damage_type_.name.lower()
        }
    
    def roll_damage(self, critical_chance: int = 0, critical_multiplier: int = 2):
        total_damage = 0
        for i in range(self.damage_dice_number_):
            total_damage += random.randint(1, self.damage_dice_type_)
        total_damage += self.damage_dice_bonus_
        if random.randint(1, 100) <= critical_chance:
            total_damage *= critical_multiplier
        return total_damage
    
    def calc_susceptibility(self, damage_type: DamageType, damage_profile: List[DamageResistances]) -> float:
        logger = CustomDetailLogger(__name__, prefix="PotentialDamage.calc_susceptibility()> ")
        logger.debug(f"damage_type: {damage_type}, damage_profile: {[ x.to_dict() for x in damage_profile ]}")
        mult = 1
        for profile in damage_profile:
            mult *= profile.profile_[damage_type]
        return mult
    
    def damage_adjective(self, damage: int):
        if damage == 0:
            return "insignificant"
        if damage < self.glancing_damage_:
            return "minor"
        elif damage >= self.powerful_damage_:
            return "major"
        else:
            return "moderate"
        
    def damage_verb(self, damage: int):
        if damage == 0:
            return "whiffs"
        if damage < self.glancing_damage_:
            return "scratches"
        elif damage >= self.powerful_damage_:
            return "hits"
        else:
            return "whacks"




class AttackData():
    def __init__(self, 
                 damage_type: DamageType = None, 
                 damage_amount: str = None, 
                 damage_num_dice=None, 
                 damage_dice_size=None, 
                 damage_bonus=None, 
                 attack_bonus=0, 
                 attack_noun=None, 
                 attack_verb=None
                 ):
        logger = CustomDetailLogger(__name__, prefix="AttackData.__init__()> ")
        self.potential_damage_: List[PotentialDamage()] = []
        if damage_type and damage_amount:
            damage_parts = get_dice_parts(damage_amount)
            self.potential_damage_.append(PotentialDamage(damage_type, damage_parts[0], damage_parts[1], damage_parts[2]))
        elif damage_type and ((damage_num_dice and damage_dice_size) or damage_bonus):
            self.potential_damage_.append(PotentialDamage(damage_type, damage_num_dice or 0, damage_dice_size or 0, damage_bonus or 0))
        else:
            logger.error("AttackData() called without damage_type and damage_amount or damage_type and damage_num_dice and damage_dice_size or damage_bonus")
        self.attack_noun_ = attack_noun or "something"
        self.attack_verb_ = attack_verb or "hits"
        self.attack_bonus = attack_bonus

    def to_dict(self):
        return {
            "attack_bonus": self.attack_bonus,
            "potential_damage": [pd.to_dict() for pd in self.potential_damage_],
            # "attack_noun": self.attack_noun_,
            # "attack_verb": self.attack_verb_
        }

