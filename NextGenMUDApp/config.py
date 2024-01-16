from django.conf import settings
import yaml

class Config:
    WORLD_DATA_DIR: str = "world_data"

    def load_from_yaml(self, file_path=None):
        from .constants import Constants
        if file_path is None:
            file_path = f"{settings.NEXTGENMUDAPP_CONFIG_FILE}"

        with open(file_path, 'r') as file:
            # Load the YAML file
            config_values = yaml.safe_load(file)
            # Iterate over the keys and set them on the class if they exist
            for key, value in config_values.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            Constants.load_from_dict(config_values)

    def validate(self):
        if self.WORLD_DATA_DIR is None or self.WORLD_DATA_DIR.strip() == '':
            raise ValueError("WORLD_DATA_DIR is empty")


# Default global configuration instance
default_app_config = Config()
default_app_config.load_from_yaml()
default_app_config.validate()
