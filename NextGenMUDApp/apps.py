from django.apps import AppConfig
from .structured_logger import get_logger, set_global_log_width, set_detail_level
import logging
import sys
import os
import atexit
import threading

# Add custom debug levels
logging.DEBUG2 = 9  # Between DEBUG(10) and NOTSET(0)
logging.DEBUG3 = 8  # Even more detailed than DEBUG2

class NextGenMUDAppConfig(AppConfig):
    name = 'NextGenMUDApp'

    def ready(self):
        # Create a logger instance
        logger = get_logger(__name__)

        # Set global log width from environment variable if present and valid
        log_width = os.environ.get('NEXTGENMUD_LOG_WIDTH')
        if log_width and log_width.isdigit():
            set_global_log_width(int(log_width))

        # Set log detail level from environment variable if present and valid
        log_level = os.environ.get('NEXTGENMUD_LOG_LEVEL')
        if log_level:
            if log_level.lower() == 'debug':
                logger.setLevel(logging.DEBUG)
                set_detail_level(1)
            elif log_level.lower() == 'debug2':
                logger.setLevel(logging.DEBUG)
                set_detail_level(2)
            elif log_level.lower() == 'debug3':
                logger.setLevel(logging.DEBUG)
                set_detail_level(3)
            elif log_level.lower() == 'info':
                logger.setLevel(logging.INFO)
                set_detail_level(1)
            elif log_level.lower() == 'warning':
                logger.setLevel(logging.WARNING)
                set_detail_level(1)
            elif log_level.lower() == 'error':
                logger.setLevel(logging.ERROR)
            elif log_level.lower() == 'critical':
                logger.setLevel(logging.CRITICAL)
            else:
                logger.setLevel(logging.INFO)

        # Only initialize game state if not running management commands
        if not any(cmd in sys.argv for cmd in ['makemigrations', 'migrate', 'shell', 'dbshell']):
            loader_logger = get_logger(__name__)

            # Shutdown cleanup: lazy imports so we don't trigger world load on exit if it never started
            def shutdown_cleanup():
                try:
                    from .comprehensive_game_state import live_game_state
                    from .main_process import MainProcess
                    cleanup_logger = get_logger(__name__)
                    cleanup_logger.debug("Atexit handler running...")
                    live_game_state.shutting_down = True
                    for ld_char in list(live_game_state.linkdead_characters.values()):
                        cleanup_logger.info(f"Saving linkdead character: {ld_char.character.name}")
                        live_game_state._save_character(ld_char.character)
                    MainProcess.shutdown()
                except ImportError:
                    pass

            atexit.register(shutdown_cleanup)

            # Signal handler must be registered in the main thread. MainProcess is imported here
            # but does not pull in comprehensive_game_state (lazy _get_game_state()).
            from .main_process import MainProcess
            MainProcess.register_signal_handler()

            def loader_worker():
                loader_logger.info("--- WORLD LOADING STARTED ---")
                try:
                    from .comprehensive_game_state import live_game_state
                    from .main_process import MainProcess
                    live_game_state.Initialize()
                    MainProcess.start_main_process()
                    loader_logger.info("--- WORLD LOADING COMPLETE: GAME READY ---")
                except Exception as e:
                    loader_logger.exception(f"World loading failed: {e}")
                    raise

            loader_thread = threading.Thread(target=loader_worker, daemon=True)
            loader_thread.start()
            loader_logger.info("Server boot continuing; world is loading in background.")



# ****************************************
#             MAIN TO-DO LIST
# ****************************************

# HIGH priority
# (none at the moment)

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