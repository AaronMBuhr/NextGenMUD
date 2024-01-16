from abc import ABCMeta, abstractmethod

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

