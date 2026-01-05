

class CommandHandlerInterface:

    _instance: 'CommandHandlerInterface' = None

    @classmethod
    def get_instance(cls) -> 'CommandHandlerInterface':
        if not cls._instance:
            from .command_handler import CommandHandler
            cls._instance = CommandHandler()
        return cls._instance

    async def process_command(cls, actor: 'Actor', input: str, vars: dict = None, from_script: bool = False):
        await CommandHandlerInterface._instance.process_command(actor, input, vars, from_script)

