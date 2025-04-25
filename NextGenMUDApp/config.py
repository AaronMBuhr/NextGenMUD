from django.conf import settings
# import yaml
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
import sys

class Config:
    WORLD_DATA_DIR: str = "world_data"

    def load_from_yaml(self, file_path=None):
        from .constants import Constants
        if file_path is None:
            file_path = f"{settings.NEXTGENMUDAPP_CONFIG_FILE}"

        yaml_loader = YAML(typ='safe') # Use safe loader

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Load the YAML file
                # config_values = yaml.safe_load(file)
                config_values = yaml_loader.load(file)
                
                if not isinstance(config_values, dict):
                    print(f"Error: Config file {file_path} does not contain a valid dictionary.", file=sys.stderr)
                    sys.exit(1)
                    
                # Iterate over the keys and set them on the class if they exist
                for key, value in config_values.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
                Constants.load_from_dict(config_values)
        except FileNotFoundError:
            print(f"Error: Config file not found at {file_path}", file=sys.stderr)
            sys.exit(1)
        except YAMLError as e:
            print(f"Error parsing config YAML file: {file_path}", file=sys.stderr)
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                print(f"  Error occurred at line {mark.line + 1}, column {mark.column + 1}", file=sys.stderr)
                if hasattr(e, 'problem'):
                    print(f"  Problem: {e.problem}", file=sys.stderr)
                if hasattr(e, 'context') and e.context:
                     print(f"  Context: {e.context}", file=sys.stderr)
            else:
                print(f"  Error details: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred loading config {file_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def validate(self):
        if self.WORLD_DATA_DIR is None or self.WORLD_DATA_DIR.strip() == '':
            raise ValueError("WORLD_DATA_DIR is empty")


# Default global configuration instance
default_app_config = Config()
default_app_config.load_from_yaml()
default_app_config.validate()
