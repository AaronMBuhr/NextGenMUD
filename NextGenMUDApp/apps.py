
from django.apps import AppConfig
from .main_process import startMainProcess
from .operating_state import operating_state

class NextGenMUDAppConfig(AppConfig):
    name = 'NextGenMUDApp'

    def ready(self):
        # # Import and start your background task here
        # from . import background_tasks
        # background_tasks.start_my_task()
        operating_state.Initialize()
        startMainProcess()


