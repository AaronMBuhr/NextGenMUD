from enum import Enum


class FighterSkills(Enum):
    MIGHTY_KICK = 1
    DEMORALIZING_SHOUT = 2
    INTIMIDATE = 3
    DISARM = 4
    SLAM = 5
    RALLY = 6
    REND = 7

    def __str__(self):
        return self.name.replace("_", " ").title()

class MageSkills(Enum):
    CAST_FIREBALL = 1
    CAST_MAGIC_MISSILE = 2
    CAST_LIGHT = 3
    CAST_SHIELD = 4
    CAST_SLEEP = 5
    CAST_CHARM = 6
    CAST_RESIST_MAGIC = 7

    def __str__(self):
        return self.name[5:].replace("_", " ").title()

class RogueSkills(Enum):
    BACKSTAB = 1
    STEALTH = 2
    EVADE = 3
    PICKPOCKET = 4
    SAP = 5

    def __str__(self):
        return self.name.replace("_", " ").title()

class ClericSkills(Enum):
    CURE_LIGHT_WOUNDS = 1
    CURE_SERIOUS_WOUNDS = 2
    CURE_CRITICAL_WOUNDS = 3
    HEAL = 4
    ANIMATE_DEAD = 5
    SMITE = 6
    BLESS = 7
    AEGIS = 8
    SANCTUARY = 9

    def __str__(self):
        return self.name.replace("_", " ").title()


class SkillsInterface:
    _instance: 'SkillsInterface' = None

    # @classmethod
    # def set_instance(cls, instance: 'SkillsInterface'):
    #     cls._instance = instance

    @classmethod
    def get_instance(cls) -> 'SkillsInterface':
        if not cls._instance:
            from .skills import Skills
            cls._instance = Skills()
        return cls._instance
    
