from django.apps import AppConfig
import sys

class NextGenMUDAppConfig(AppConfig):
    name = 'NextGenMUDApp'

    def ready(self):
        # Only initialize game state if not running management commands
        if not any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'shell', 'dbshell']):
            # Import here to avoid premature loading
            from .main_process import MainProcess
            from .comprehensive_game_state import live_game_state
            
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
# - need to give stealth some kind of re-check cooldown
#   then use can_see for do_aggro
                        
# LOW priority
# - handle possessive pronouns
# - look room after something dies is not working
# - add parry?        
# - combine equip & carry weight
# - instead of set_vars dupes, just change '*'
# - make room say be "You hear" or something
# - process_command command stack funky
# - could optimize pc-in-zone checking