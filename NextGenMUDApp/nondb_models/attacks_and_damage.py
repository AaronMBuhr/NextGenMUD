from enum import Enum
import random
from typing import Dict, List
from ..structured_logger import StructuredLogger
from ..utility import get_dice_parts


class DamageType(Enum):
    RAW = 1
    SLASHING = 2
    PIERCING = 3
    BLUDGEONING = 4
    FIRE = 5
    COLD = 6
    LIGHTNING = 7
    ACID = 8
    POISON = 9
    DISEASE = 10
    HOLY = 11
    UNHOLY = 12
    ARCANE = 13
    PSYCHIC = 14
    FORCE = 15
    NECROTIC = 16
    RADIANT = 17

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
    def __init__(self, profile=None, resistances_by_type: Dict[DamageType, int]=None):
        if profile:
            self.profile = profile
        else:
            self.profile = {loc: 1 for loc in DamageType}
        if resistances_by_type:
            for damage_type, amount in resistances_by_type.items():
                self.profile[damage_type] = amount

    def to_dict(self):
        # return {EquipLocation[loc].name.lower(): dt.name.lower() for loc, dt in self.profile.items()}
        return repr(self.profile)

    def set(self, damage_type: DamageType, amount: float):
        self.profile[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile[damage_type]
    
    def add_resistances(self, more_resistances: 'DamageResistances'):
        for damage_type, amount in more_resistances.profile.items():
            self.profile[damage_type] += amount

    def minus_resistances(self, more_resistances: 'DamageResistances'):
        for damage_type, amount in more_resistances.profile.items():
            self.profile[damage_type] -= amount
    

class DamageReduction:
    def __init__(self, profile=None, reductions_by_type: Dict[DamageType, int]=None):
        if profile:
            self.profile = profile
        else:
            self.profile = {loc: 0 for loc in DamageType}
        if reductions_by_type:
            for damage_type, amount in reductions_by_type.items():
                self.profile[damage_type] = amount

    def set(self, damage_type: DamageType, amount: float):
        self.profile[damage_type] = amount
   
    def get(self, damage_type: DamageType):
        return self.profile[damage_type]

    def to_dict(self):
        return repr(self.profile)
    
    def add_reduction(self, more_reduction: 'DamageReduction'):
        for damage_type, amount in more_reduction.profile.items():
            self.profile[damage_type] += amount

    def minus_reduction(self, more_reduction: 'DamageReduction'):
        for damage_type, amount in more_reduction.profile.items():
            self.profile[damage_type] -= amount

class PotentialDamage:
    def __init__(self, damage_type: DamageType, damage_dice_number: int, damage_dice_type: int, damage_dice_bonus: int):
        self.damage_type = damage_type
        self.damage_dice_number = damage_dice_number
        self.damage_dice_type = damage_dice_type
        self.damage_dice_bonus = damage_dice_bonus
        self.min_damage = damage_dice_number + damage_dice_bonus
        self.max_damage = damage_dice_number * damage_dice_type + damage_dice_bonus
        self.glancing_damage = (self.max_damage - self.min_damage) * 0.20 + self.min_damage
        self.powerful_damage = (self.max_damage - self.min_damage) * 0.80 + self.min_damage

    def to_dict(self):
        return {
            "damage": f"{self.damage_dice_number}d{self.damage_dice_type}+{self.damage_dice_bonus}",
            "damage_type": self.damage_type.name.lower()
        }
    
    def roll_damage(self, critical_chance: int = 0, critical_multiplier: int = 2):
        total_damage = 0
        for i in range(self.damage_dice_number):
            total_damage += random.randint(1, self.damage_dice_type)
        total_damage += self.damage_dice_bonus
        if random.randint(1, 100) <= critical_chance:
            total_damage *= critical_multiplier
        return total_damage
    
    def calc_susceptibility(self, damage_type: DamageType, damage_profile: List[DamageResistances]) -> float:
        logger = StructuredLogger(__name__, prefix="PotentialDamage.calc_susceptibility()> ")
        logger.debug(f"damage_type: {damage_type}, damage_profile: {[ x.to_dict() for x in damage_profile ]}")
        mult = 1
        for profile in damage_profile:
            mult *= profile.profile[damage_type]
        return mult
    
    def damage_adjective(self, damage: int):
        if damage == 0:
            return "insignificant"
        if damage < self.glancing_damage:
            return "minor"
        elif damage >= self.powerful_damage:
            return "major"
        else:
            return "moderate"
        
    def damage_verb(self, damage: int):
        if damage == 0:
            return "whiffs"
        if damage < self.glancing_damage:
            return "scratches"
        elif damage >= self.powerful_damage:
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
        logger = StructuredLogger(__name__, prefix="AttackData.__init__()> ")
        self.potential_damage_: List[PotentialDamage()] = []
        if damage_type and damage_amount:
            damage_parts = get_dice_parts(damage_amount)
            self.potential_damage_.append(PotentialDamage(damage_type, damage_parts[0], damage_parts[1], damage_parts[2]))
        elif damage_type and ((damage_num_dice and damage_dice_size) or damage_bonus):
            self.potential_damage_.append(PotentialDamage(damage_type, damage_num_dice or 0, damage_dice_size or 0, damage_bonus or 0))
        else:
            logger.error("AttackData() called without damage_type and damage_amount or damage_type and damage_num_dice and damage_dice_size or damage_bonus")
        self.attack_noun = attack_noun or "something"
        self.attack_verb = attack_verb or "hits"
        self.attack_bonus = attack_bonus

    def to_dict(self):
        return {
            "attack_bonus": self.attack_bonus,
            "potential_damage": [pd.to_dict() for pd in self.potential_damage_],
            # "attack_noun": self.attack_noun_,
            # "attack_verb": self.attack_verb_
        }

