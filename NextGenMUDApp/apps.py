
from django.apps import AppConfig
from .main_process import MainProcess
from .comprehensive_game_state import live_game_state

class NextGenMUDAppConfig(AppConfig):
    name = 'NextGenMUDApp'

    def ready(self):
        # # Import and start your background task here
        # from . import background_tasks
        # background_tasks.start_my_task()
        live_game_state.Initialize()
        MainProcess.start_main_process()



# ****************************************
#             MAIN TO-DO LIST
# ****************************************

# HIGH priority
# - handle "you die"
# - get all
# - saving throws!
# - aggro not working
# - up/down not working
                
# MEDIUM priority
# - handle capitalization
# - hp regen over time
# - command abbrevs
# - need an ON_SPAWN trigger
# - not sure players are being handled right
# - make attack and kill allow you to switch targets
# - at some point going to need to handle pc vs pc interaction
                        
# LOW priority
# - handle possessive pronouns
# - look room after something dies is not working
# - add parry?        
# - combine equip & carry weight
# - instead of set_vars dupes, just change '*'
# - make room say be "You hear" or something
# - process_command command stack funky
# - could optimize pc-in-zone checking