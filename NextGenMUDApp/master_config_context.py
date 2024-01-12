class MasterConfigContext:
    def __init__(self, **configs):
        self.original_configs = {}
        self.new_configs = configs

    def __enter__(self):
        # Store the original configurations and apply new ones
        for class_name, new_config in self.new_configs.items():
            self.original_configs[class_name] = class_name.config
            class_name.config = new_config

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the original configurations
        for class_name, original_config in self.original_configs.items():
            class_name.config = original_config

# class UtilityClassA:
#     config = default_config_a

#     @staticmethod
#     def some_method():
#         # Use UtilityClassA.config

# class UtilityClassB:
#     config = default_config_b

#     @staticmethod
#     def some_method():
#         # Use UtilityClassB.config

# with MasterConfigContext(UtilityClassA=new_config_a, UtilityClassB=new_config_b):
#     # Within this block, UtilityClassA and UtilityClassB will use the new configurations
#     UtilityClassA.some_method()
#     UtilityClassB.some_method()

# # Outside the block, they revert to their default configurations
