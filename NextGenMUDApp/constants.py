from typing import Dict
import yaml
from custom_detail_logger import CustomDetailLogger
from .config import Config, default_app_config


class Constants:
    REFERENCE_SYMBOL = '|'
    REFERENCE_SYMBOL_ESCAPE = '||'
    GAME_TICK_SEC = 0.5
    TICKS_PER_ROUND = 2
    XP_PROGRESSION = []
    HP_BY_CHARACTER_CLASS = {}


    @classmethod
    def load_from_dict(constants_dict: Dict):
        from .nondb_models.actors import CharacterClassRole

        # Load XP progression
        Constants.XP_PROGRESSION = constants_dict["XP_PROGRESSION"]

        # Load HP by character class
        for class_name, hp in constants_dict["HIT_POINT_GAIN_BY_CLASS"].items():
            class_enum = CharacterClassRole.from_field_name(class_name)
            Constants.HP_BY_CHARACTER_CLASS[class_enum] = hp
