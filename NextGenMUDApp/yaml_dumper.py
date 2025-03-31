import yaml

class YamlDumper:
    @staticmethod
    def to_yaml_compatible_str(obj):
        """Convert an object to a YAML-compatible string representation"""
        try:
            return yaml.dump(obj, default_flow_style=False)
        except Exception as e:
            return str(obj) 