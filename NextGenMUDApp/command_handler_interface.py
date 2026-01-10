from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CommandResult:
    """Result of executing a single command."""
    command: str
    succeeded: bool = True
    message: Optional[str] = None


@dataclass 
class TriggerResult:
    """Results from a single trigger's script execution."""
    trigger_type: str  # e.g., "CATCH_SAY", "ON_ENTER"
    trigger_id: str
    trigger_criteria: str  # Human readable criteria like "word 'gold'" or "object 'key'"
    command_results: List[CommandResult] = field(default_factory=list)


@dataclass
class TriggerContext:
    """
    Context for tracking trigger script execution and results.
    Stored on the actor during trigger processing.
    """
    # Who/what initiated the trigger (player reference)
    initiator_ref: Optional[str] = None
    # Accumulated results from all triggers (supports nesting)
    trigger_results: List[TriggerResult] = field(default_factory=list)
    # Current trigger being processed (for adding command results)
    current_trigger: Optional[TriggerResult] = None
    # Nesting level - only send to LLM when this returns to 0
    nesting_level: int = 0


class CommandHandlerInterface:

    _instance: 'CommandHandlerInterface' = None

    @classmethod
    def get_instance(cls) -> 'CommandHandlerInterface':
        if not cls._instance:
            from .command_handler import CommandHandler
            cls._instance = CommandHandler()
        return cls._instance

    async def process_command(cls, actor: 'Actor', input: str, vars: dict = None, from_script: bool = False) -> bool:
        """
        Process a command for an actor.
        
        Returns:
            bool: True if command succeeded (or made progress), False if it failed completely
        """
        return await CommandHandlerInterface._instance.process_command(actor, input, vars, from_script)

