
# this is all wrong but leaving it for future skill ideas
# DO NOT UNCOMMENT OR OTHERWISE USE THIS FILE

# from enum import Enum


# class FighterSkills(Enum):
#     # Base Fighter Skills (Tiers 1-2)
#     BATTLE_STANCE = 1
#     SHIELD_BASH = 2
#     HEROIC_STRIKE = 3
#     TAUNT = 4
#     CHARGE = 5
#     DUAL_WIELD = 6
#     DEFENSIVE_STANCE = 7
#     BATTLE_SHOUT = 8
#     SECOND_WIND = 9
#     DISARM = 10

#     # Berserker Skills (Tiers 3-7)
#     BERSERKER_STANCE = 11
#     RAGE = 12
#     CLEAVE = 13
#     BLOODTHIRST = 14
#     INTIMIDATING_SHOUT = 15
#     WHIRLWIND = 16
#     RAMPAGE = 17
#     EXECUTE = 18
#     DEATHWISH = 19
#     ENRAGE = 20
#     UNSTOPPABLE = 21
#     BLOODBATH = 22
#     RECKLESSNESS = 23
#     BRUTAL_STRIKE = 24
#     DEATH_WISH = 25
#     BERSERKER_FURY = 26
#     TITANS_GRIP = 27
#     MEAT_CLEAVER = 28
#     BLOOD_FRENZY = 29
#     MASSACRE = 30
#     AVATAR = 31

#     # Guardian Skills (Tiers 3-7)
#     SHIELD_WALL = 32
#     PROTECTION_STANCE = 33
#     INTERVENE = 34
#     REVENGE = 35
#     LAST_STAND = 36
#     SHIELD_SLAM = 37
#     SHIELD_BLOCK = 38
#     VIGILANCE = 39
#     SAFEGUARD = 40
#     SPELL_REFLECTION = 41
#     SHIELD_MASTERY = 42
#     INDOMITABLE = 43
#     BASTION = 44
#     STALWART_DEFENDER = 45
#     DEFIANCE = 46
#     UNBREAKABLE = 47
#     SHIELD_FORTRESS = 48
#     IMPENETRABLE_DEFENSE = 49
#     GUARDIANS_CALL = 50
#     INVINCIBILITY = 51

#     # Reaver Skills (Tiers 3-7)
#     SWEEPING_STRIKES = 52
#     OVERPOWER = 53
#     THUNDERCLAP = 54
#     HAMSTRING = 55
#     MORTAL_STRIKE = 56
#     BLADESTORM = 57
#     COLOSSUS_SMASH = 58
#     SLAM = 59
#     REND = 60
#     SHOCK_WAVE = 61
#     STORM_BOLT = 62
#     DEADLY_CALM = 63
#     DEMORALIZING_SHOUT = 64
#     PIERCING_HOWL = 65
#     DEATH_SENTENCE = 66
#     RAVAGER = 67
#     WAR_MACHINE = 68
#     DIE_BY_THE_SWORD = 69
#     TITANIC_MIGHT = 70
#     SIEGEBREAKER = 71
#     JUGGERNAUT = 72
    
#     def __str__(self):
#         return self.name.replace("_", " ").title()


# class MageSkills(Enum):
#     # Base Mage Skills (Tiers 1-2)
#     MAGIC_MISSILE = 1
#     ARCANE_BARRIER = 2
#     BURNING_HANDS = 3
#     MANA_SHIELD = 4
#     DISPEL_MAGIC = 5
#     DETECT_MAGIC = 6
#     IDENTIFY = 7
#     ARCANE_INTELLECT = 8
#     BLINK = 9
#     FROST_NOVA = 10

#     # Evoker Skills (Tiers 3-7)
#     FIREBALL = 11
#     LIGHTNING_BOLT = 12
#     SPELL_PENETRATION = 13
#     ICE_LANCE = 14
#     ARCANE_EXPLOSION = 15
#     CHAIN_LIGHTNING = 16
#     ACID_FOG = 17
#     FIRE_BLAST = 18
#     ARCANE_BARRAGE = 19
#     COLD_SNAP = 20
#     METEOR_SHOWER = 21
#     ARCANE_SURGE = 22
#     LIVING_BOMB = 23
#     SUPERNOVA = 24
#     BALL_LIGHTNING = 25
#     POLAR_VORTEX = 26
#     PYROCLASM = 27
#     ARCANE_DEVASTATION = 28
#     THUNDER_STRIKE = 29
#     GLACIAL_SPIKE = 30
#     CATACLYSM = 31

#     # Conjurer Skills (Tiers 3-7)
#     SUMMON_FAMILIAR = 32
#     CREATE_FOOD = 33
#     CONJURE_WATER = 34
#     SUMMON_MANA_GEM = 35
#     ARCANE_PORTAL = 36
#     SUMMON_LESSER_MONSTER = 37
#     CONJURE_STAFF = 38
#     DIMENSIONAL_DOOR = 39
#     SUMMON_WEAPON = 40
#     DISLOCATION = 41
#     SUMMON_ELEMENTAL = 42
#     MIRROR_IMAGE = 43
#     TELEPORT = 44
#     MASS_TELEPORT = 45
#     SUMMON_CONSTRUCT = 46
#     SUMMON_GREATER_MONSTER = 47
#     PLANAR_BINDING = 48
#     TIME_WARP = 49
#     DIMENSIONAL_ANCHOR = 50
#     CONJURE_ARMY = 51
#     GATE = 52

#     # Enchanter Skills (Tiers 3-7)
#     CHARM_PERSON = 53
#     WEAKEN = 54
#     SLEEP = 55
#     MAGICAL_APTITUDE = 56
#     SLOW = 57
#     CONFUSION = 58
#     ENCHANT_WEAPON = 59
#     CURSE = 60
#     MIND_LINK = 61
#     FORGET = 62
#     DOMINATE = 63
#     GREATER_ENCHANTMENT = 64
#     ARCANE_BRILLIANCE = 65
#     MIND_CONTROL = 66
#     PARALYZE = 67
#     MASS_CHARM = 68
#     POWER_WORD_STUN = 69
#     TEMPORAL_STASIS = 70
#     MENTAL_FORTRESS = 71
#     MIND_SHATTER = 72
#     WISH = 73

#     def __str__(self):
#         return self.name.replace("_", " ").title()


# class RogueSkills(Enum):
#     # Base Rogue Skills (Tiers 1-2)
#     STEALTH = 1
#     BACKSTAB = 2
#     PICK_LOCK = 3
#     DETECT_TRAPS = 4
#     EVADE = 5
#     DUAL_WIELD = 6
#     POISONED_WEAPON = 7
#     DISARM_TRAP = 8
#     ACROBATICS = 9
#     FEINT = 10

#     # Duelist Skills (Tiers 3-7)
#     RIPOSTE = 11
#     PRECISION_STRIKES = 12
#     PARRY = 13
#     FLOURISH = 14
#     ELEGANT_FORM = 15
#     BLADE_FLURRY = 16
#     FINISHING_MOVE = 17
#     COMBAT_POTENCY = 18
#     COMBAT_READINESS = 19
#     ADRENALINE_RUSH = 20
#     DUELMASTER_STANCE = 21
#     PERFECT_BALANCE = 22
#     LIGHTNING_REFLEXES = 23
#     COMBAT_INSIGHT = 24
#     BLADE_DANCE = 25
#     MASTERFUL_PARRY = 26
#     DEADLY_MOMENTUM = 27
#     COMBAT_TRANCE = 28
#     BURST_OF_SPEED = 29
#     KILLING_SPREE = 30
#     BLADESTORM = 31

#     # Assassin Skills (Tiers 3-7)
#     GARROTE = 32
#     DEADLY_POISON = 33
#     SHADOWSTEP = 34
#     RUPTURE = 35
#     AMBUSH = 36
#     MUTILATE = 37
#     VENDETTA = 38
#     ENVENOM = 39
#     VENOM_RUSH = 40
#     SHADOW_FOCUS = 41
#     EXSANGUINATE = 42
#     TOXIC_BLADE = 43
#     MASTER_POISONER = 44
#     INTERNAL_BLEEDING = 45
#     DEATHMARK = 46
#     DEATH_FROM_ABOVE = 47
#     MARKED_FOR_DEATH = 48
#     VEILED_KILLER = 49
#     HEMOTOXIN = 50
#     ASSASSINATE = 51
#     PERFECT_KILL = 52

#     # Infiltrator Skills (Tiers 3-7)
#     CLOAK_OF_SHADOWS = 53
#     DISTRACT = 54
#     SAP = 55
#     DETECT_WEAKNESS = 56
#     PICK_POCKET = 57
#     CHEAT_DEATH = 58
#     TRAP_MASTERY = 59
#     SMOKE_BOMB = 60
#     EVASION = 61
#     SHADOW_DANCE = 62
#     VANISH = 63
#     PREPARATION = 64
#     SECRET_TECHNIQUE = 65
#     SHADOW_BLADES = 66
#     SILENT_STEPS = 67
#     MASTER_OF_SUBTLETY = 68
#     PHANTOM_STRIKE = 69
#     GHOST_IN_THE_SHADOWS = 70
#     DEFT_FINGERS = 71
#     SUBVERSION = 72
#     SHADOW_MASTER = 73

#     def __str__(self):
#         return self.name.replace("_", " ").title()


# class ClericSkills(Enum):
#     # Base Cleric Skills (Tiers 1-2)
#     CURE_LIGHT_WOUNDS = 1
#     BLESS = 2
#     DIVINE_FAVOR = 3
#     RADIANT_LIGHT = 4
#     SANCTUARY = 5
#     CURE_MODERATE_WOUNDS = 6
#     REMOVE_CURSE = 7
#     DIVINE_PROTECTION = 8
#     SMITE = 9
#     DIVINE_GUIDANCE = 10

#     # Warpriest Skills (Tiers 3-7)
#     DIVINE_STRIKE = 11
#     HOLY_FIRE = 12
#     RIGHTEOUS_FURY = 13
#     FLAMESTRIKE = 14
#     DIVINE_ARMOR = 15
#     CONSECRATION = 16
#     HOLY_NOVA = 17
#     DIVINE_PUNISHMENT = 18
#     BATTLE_PRAYER = 19
#     SHIELD_OF_FAITH = 20
#     HOLY_WRATH = 21
#     DIVINE_AEGIS = 22
#     HAMMER_OF_JUSTICE = 23
#     RIGHTEOUS_DEFENSE = 24
#     DIVINE_STORM = 25
#     AVENGING_WRATH = 26
#     GUARDIAN_OF_FAITH = 27
#     DIVINE_INTERVENTION = 28
#     HOLY_RADIANCE = 29
#     ABSOLUTION = 30
#     DIVINE_RECKONING = 31

#     # Restorer Skills (Tiers 3-7)
#     CURE_SERIOUS_WOUNDS = 32
#     REGENERATION = 33
#     DIVINE_HEALING = 34
#     PURIFY = 35
#     RESTORATION = 36
#     MASS_CURE_WOUNDS = 37
#     VITALITY = 38
#     HOLY_BEACON = 39
#     LIFE_LINK = 40
#     PURIFICATION = 41
#     MASS_REGENERATION = 42
#     CIRCLE_OF_HEALING = 43
#     DIVINE_TRANSFUSION = 44
#     RENEW = 45
#     FAITH_HEALING = 46
#     DIVINE_HYMN = 47
#     GENESIS = 48
#     MIRACLE_OF_LIFE = 49
#     SALVATION = 50
#     GUARDIAN_SPIRIT = 51
#     RESURRECTION = 52

#     # Ritualist Skills (Tiers 3-7)
#     DIVINE_BLESSING = 53
#     DIVINE_WARD = 54
#     SPIRITUAL_WEAPON = 55
#     HOLY_SYMBOL = 56
#     DIVINE_REVELATION = 57
#     DIVINE_EMPOWERMENT = 58
#     CONSECRATED_GROUND = 59
#     DIVINE_CLARITY = 60
#     SACRED_RITUAL = 61
#     SPIRIT_GUARDIANS = 62
#     DIVINE_COMMUNION = 63
#     HALLOWED_GROUND = 64
#     SPIRITUAL_BINDING = 65
#     SACRED_FLAME = 66
#     DIVINE_CONDUIT = 67
#     HOLY_WORD = 68
#     DIVINE_PRESENCE = 69
#     SPIRITUAL_PROJECTION = 70
#     RITUAL_OF_JUDGMENT = 71
#     ASTRAL_MANIFESTATION = 72
#     TRANSCENDENCE = 73

#     def __str__(self):
#         return self.name.replace("_", " ").title()


# class SkillsInterface:
#     _instance: 'SkillsInterface' = None

#     @classmethod
#     def get_instance(cls) -> 'SkillsInterface':
#         if not cls._instance:
#             from .skills import Skills
#             cls._instance = Skills()
#         return cls._instance
    
