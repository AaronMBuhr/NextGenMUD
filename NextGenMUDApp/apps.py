
from django.apps import AppConfig
from .main_process import start_main_process
from .operating_state import operating_state

class NextGenMUDAppConfig(AppConfig):
    name = 'NextGenMUDApp'

    def ready(self):
        # # Import and start your background task here
        # from . import background_tasks
        # background_tasks.start_my_task()
        operating_state.Initialize()
        start_main_process()



# ****************************************
#             MAIN TO-DO LIST
# ****************************************

# HIGH priority
# - handle "you die"
# - get all
                
# MEDIUM priority
# - handle capitalization
# - hp regen over time
# - command abbrevs
# - need an ON_SPAWN trigger
                        
# LOW priority
# - handle possessive pronouns
# - look room after something dies is not working
# - add parry?        
