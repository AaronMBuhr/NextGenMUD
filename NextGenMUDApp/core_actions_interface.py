from abc import ABCMeta, abstractmethod
from .nondb_models.actors import Actor
from .nondb_models.attacks_and_damage import DamageType

class CoreActionsInterface(metaclass=ABCMeta):

    _instance: 'CoreActionsInterface' = None

    @abstractmethod
    async def do_aggro(cls, actor: 'Actor') -> None:
        raise NotImplementedError
    
    # @classmethod
    # def set_instance(cls, instance: 'CoreActionsInterface') -> None:
    #     # cls._instance = instance
    #     cls._instance = CoreActions()

    @classmethod
    def get_instance(cls) -> 'CoreActionsInterface':
        if not cls._instance:
            from .core_actions import CoreActions
            cls._instance = CoreActions()
        return cls._instance    

    async def do_calculated_damage(self, actor: Actor, target: Actor, damage: int, damage_type: DamageType, do_msg=True) -> int:
        pass

    async def trigger_group_aggro(self, attacker: Actor, target: Actor) -> None:
        """Trigger group members of target to join combat against attacker."""
        pass
    