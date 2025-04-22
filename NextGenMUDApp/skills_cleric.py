from .skills_core import Skills
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterAttributes
from .nondb_models.characters import CharacterSkill
from .constants import CharacterClassRole
from .communication import CommTypes

class Skills_Cleric(Skills):
    @classmethod
    async def do_cleric_cure_light_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                        difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure light wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_serious_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                          difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure serious wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_cure_critical_wounds(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                                           difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Cure critical wounds is not yet implemented!", cls.game_state)
        return False

    @classmethod
    async def do_cleric_heal(cls, actor: Actor, target: Actor, skill: CharacterSkill, 
                            difficulty_modifier=0, game_tick=0) -> bool:
        actor.send_text(CommTypes.DYNAMIC, "Heal is not yet implemented!", cls.game_state)
        return False 