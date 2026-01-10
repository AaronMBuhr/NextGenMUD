"""
LLM-Driven NPC Conversation Handler

Handles real-time NPC conversations powered by LLM, with structured
state tracking via permanent/temporary variables.

Instead of brittle CATCH_SAY triggers with keyword matching, NPCs are given
personality, knowledge, and disposition - the LLM handles natural conversation
and signals state changes back to the game.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum

from .structured_logger import StructuredLogger
from .communication import CommTypes

if TYPE_CHECKING:
    from .nondb_models.characters import Character
    from .comprehensive_game_state_interface import GameStateInterface

# Lazy import to avoid circular dependencies
def get_llm_client():
    from .llm_client import LLMClient, LLMConfig, create_client
    return LLMClient, LLMConfig, create_client


def get_llm_config():
    """Get LLM configuration from app config."""
    from .config import default_app_config
    return default_app_config.LLM or {}


def create_llm_client_from_config():
    """
    Create an LLM client based on app config.
    
    Config format (in app_config.yaml):
        LLM:
          provider: gemini
          model: gemini-2.0-flash
          api_key: optional-override
          temperature: 0.8
          max_output_tokens: 500
    """
    config = get_llm_config()
    
    if not config:
        # Fallback to Gemini with defaults
        from .llm_client_gemini import GeminiClient
        return GeminiClient()
    
    provider = config.get("provider", "gemini").lower()
    
    # Extract common parameters
    model = config.get("model")
    api_key = config.get("api_key")
    
    # Build kwargs for the client
    kwargs = {}
    if model:
        kwargs["model"] = model
    if api_key:
        kwargs["api_key"] = api_key
    
    # Create client based on provider
    if provider == "gemini":
        from .llm_client_gemini import GeminiClient
        return GeminiClient(**kwargs)
    # Future providers would be added here:
    # elif provider == "openai":
    #     from .llm_client_openai import OpenAIClient
    #     return OpenAIClient(**kwargs)
    # elif provider == "claude":
    #     from .llm_client_claude import ClaudeClient
    #     return ClaudeClient(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: gemini")


class ConversationMode(Enum):
    """How the NPC handles conversation."""
    SCRIPTED = "scripted"      # Traditional CATCH_SAY triggers only
    LLM_DRIVEN = "llm_driven"  # Full LLM conversation
    HYBRID = "hybrid"          # LLM with scripted fallbacks for key moments


@dataclass
class NPCKnowledge:
    """A piece of knowledge an NPC possesses that may be revealed."""
    id: str
    content: str
    reveal_threshold: int = 60  # Disposition needed to reveal
    is_secret: bool = True      # If false, NPC shares freely
    
    def to_prompt_text(self) -> str:
        if self.is_secret:
            return f"[SECRET - reveal only if disposition >= {self.reveal_threshold}] {self.content}"
        return self.content


@dataclass
class ConversationGoal:
    """A goal/trigger that can be achieved through conversation."""
    id: str
    description: str
    condition: str  # Natural language condition for LLM to evaluate
    disposition_required: Optional[int] = None
    on_achieve_set_vars: Dict[str, Any] = field(default_factory=dict)
    on_achieve_message: Optional[str] = None  # Message to show when achieved
    achieved: bool = False


@dataclass
class NPCConversationContext:
    """
    Context that defines how an NPC behaves in conversation.
    This is typically loaded from YAML zone data or set programmatically.
    """
    # Core identity
    personality: str = "neutral and reserved"
    speaking_style: str = ""  # e.g., "speaks in riddles", "gruff and terse"
    
    # Knowledge the NPC has
    knowledge: List[NPCKnowledge] = field(default_factory=list)
    
    # Goals that can be achieved through conversation
    goals: List[ConversationGoal] = field(default_factory=list)
    
    # Behavioral constraints
    will_discuss: List[str] = field(default_factory=list)  # Topics NPC engages with
    will_not_discuss: List[str] = field(default_factory=list)  # Topics NPC avoids
    
    # Special instructions
    special_instructions: str = ""
    
    # References to zone-level common knowledge (populated at conversation start)
    common_knowledge_refs: List[str] = field(default_factory=list)
    
    def to_prompt_section(self) -> str:
        """Convert context to prompt text."""
        sections = []
        
        sections.append(f"Personality: {self.personality}")
        
        if self.speaking_style:
            sections.append(f"Speaking style: {self.speaking_style}")
        
        if self.knowledge:
            knowledge_text = "\n".join(f"- {k.to_prompt_text()}" for k in self.knowledge)
            sections.append(f"What you know:\n{knowledge_text}")
        
        if self.will_discuss:
            sections.append(f"Topics you'll discuss: {', '.join(self.will_discuss)}")
        
        if self.will_not_discuss:
            sections.append(f"Topics you avoid: {', '.join(self.will_not_discuss)}")
        
        if self.goals:
            goals_text = "\n".join(
                f"- {g.description} (condition: {g.condition})"
                for g in self.goals if not g.achieved
            )
            if goals_text:
                sections.append(f"Potential conversation outcomes:\n{goals_text}")
        
        if self.special_instructions:
            sections.append(f"Special instructions: {self.special_instructions}")
        
        return "\n\n".join(sections)


@dataclass
class StateChange:
    """Represents a state change signaled by the LLM."""
    disposition_delta: int = 0
    revealed_knowledge: List[str] = field(default_factory=list)
    achieved_goals: List[str] = field(default_factory=list)
    set_variables: Dict[str, Any] = field(default_factory=dict)
    npc_action: Optional[str] = None  # e.g., "gives item", "attacks", "leaves"
    commands: List[str] = field(default_factory=list)  # Commands for NPC to execute post-conversation


# Universal system instructions prepended to every NPC conversation
UNIVERSAL_SYSTEM_INSTRUCTIONS = """[SYSTEM: MUD_NPC_PROTOCOL_V1]
You are a character in a text-based Multiplayer Dungeon (MUD). Your goal is to provide immersive roleplay while guiding the player toward gameplay content.

1. FORMATTING PROTOCOLS (Default):
   - Output must be RAW TEXT only. 
   - Do NOT use Markdown (no **bold**, *italics*, or bulleted lists).
   - Keep responses conversational and natural. Avoid robotic lists.
   - **EXCEPTION:** If your specific Character Profile instructs you to use a specific format (like poetry, lists, or ancient runes), you may override these formatting rules.

2. CONVERSATIONAL LOGIC:
   - Do not offer a "menu" of options (e.g., "I can tell you about A, B, or C"). Instead, weave keywords into observation.
   - **The "Flavor-to-Location" Rule:** If you mention a flavor element (e.g., wind, smell, sound), you must immediately link it to a specific Location or Game Mechanic (e.g., "The wind smells of rot... coming from the Barracks.").
   - Be verbose and effusive when you mention or talk about keywords, unless specified otherwise, rather than just short phrases indicating the keywords.
   - Add context to any conversation based on your specified knowledge.
   

3. ACTION HANDOFF:
   - You cannot physically move the player or execute code yourself.
   - If the player agrees to an action (like traveling), you must explicitly tell them the **Command Phrase** to use.
   - Example: "If you are ready to die, tell me to 'open the gate'."

4. HIERARCHY OF INSTRUCTION:
   - The specific [CHARACTER PROFILE] provided below is your primary truth. 
   - If the Character Profile contradicts these System Instructions (e.g., a character who speaks in verse or uses Markdown for emphasis), **follow the Character Profile.**

[CHARACTER PROFILE STARTS HERE]
"""

# Available NPC commands that the LLM can use (with brief descriptions)
NPC_COMMAND_REFERENCE = """
## Available NPC Commands (you can include these in your response)
Commands are executed after your dialogue. Include them in the "commands" array.

Movement:
- north, south, east, west, up, down - Move in a direction

Interaction:
- give <item> <target> - Give an item to someone (e.g., "give rusty_key player")
- emote <action> - Perform an emote (e.g., "emote nods slowly")
- say <text> - Say something to the room

Combat:
- attack <target> - Attack a target

Special:
- pause <seconds> - Wait before next action (max 5 seconds)

Examples:
"commands": ["give old_key player", "emote smiles warmly"]
"commands": ["emote backs away nervously", "south"]
"commands": ["attack player"]
"""


@dataclass
class ConversationResult:
    """Result of processing a conversation turn."""
    dialogue: str
    state_change: StateChange
    raw_response: str
    emotes: List[str] = field(default_factory=list)  # Extracted *emotes* from dialogue
    error: Optional[str] = None


class NPCConversationHandler:
    """
    Handles LLM-driven NPC conversations.
    
    Usage:
        handler = NPCConversationHandler()
        
        # When player says something to an NPC
        result = await handler.process_speech(player, npc, "Hello there!", game_state)
        
        # Result contains the NPC's response and any state changes
        await npc.location_room.echo(CommTypes.DYNAMIC, 
            f'{npc.art_name_cap} says, "{result.dialogue}"')
    """
    
    # Conversation history limits
    MAX_HISTORY_TURNS = 20
    MAX_HISTORY_CHARS = 4000
    
    # Variable keys used for conversation state
    VAR_DISPOSITION = "llm_disposition"  # disposition toward specific player
    VAR_CONVERSATION_HISTORY = "llm_convo"  # conversation history with player
    VAR_REVEALED = "llm_revealed"  # what's been revealed to player
    VAR_ACHIEVED = "llm_achieved"  # goals achieved with player
    VAR_CONTEXT = "llm_context"  # NPCConversationContext data
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the conversation handler.
        
        Args:
            api_key: Optional API key override (normally uses config/env var)
            model: Optional model name override (normally uses config)
        """
        self._api_key_override = api_key
        self._model_override = model
        self._client = None  # Lazy initialization
        self._logger = StructuredLogger(__name__, prefix="NPCConversationHandler> ")
    
    @property
    def client(self):
        """Lazy-load the LLM client from app config."""
        if self._client is None:
            # Check for overrides first
            if self._api_key_override or self._model_override:
                # Create with explicit overrides
                config = get_llm_config()
                provider = config.get("provider", "gemini").lower() if config else "gemini"
                
                kwargs = {}
                if self._model_override:
                    kwargs["model"] = self._model_override
                elif config and config.get("model"):
                    kwargs["model"] = config["model"]
                    
                if self._api_key_override:
                    kwargs["api_key"] = self._api_key_override
                elif config and config.get("api_key"):
                    kwargs["api_key"] = config["api_key"]
                
                if provider == "gemini":
                    from .llm_client_gemini import GeminiClient
                    self._client = GeminiClient(**kwargs)
                else:
                    self._client = create_llm_client_from_config()
            else:
                # Use config-based creation
                self._client = create_llm_client_from_config()
        return self._client
    
    def get_npc_context(self, npc: 'Character') -> NPCConversationContext:
        """
        Get or create the conversation context for an NPC.
        Context is stored in perm_variables for persistence.
        """
        context_data = npc.get_perm_var(self.VAR_CONTEXT, None)
        
        if context_data is None:
            # Create default context from NPC's description
            context = NPCConversationContext(
                personality=f"You are {npc.name}. {npc.description}" if npc.description else f"You are {npc.name}.",
            )
            return context
        
        # Reconstruct from stored data
        if isinstance(context_data, NPCConversationContext):
            return context_data
        
        # Handle dict format (from YAML loading)
        return self._context_from_dict(context_data)
    
    def set_npc_context(self, npc: 'Character', context: NPCConversationContext) -> None:
        """Store conversation context on an NPC."""
        npc.perm_variables[self.VAR_CONTEXT] = self._context_to_dict(context)
    
    def get_disposition(self, npc: 'Character', player: 'Character') -> int:
        """Get NPC's disposition toward a specific player (0-100)."""
        key = f"{self.VAR_DISPOSITION}_{player.id}"
        return npc.get_perm_var(key, 50)  # Default neutral
    
    def set_disposition(self, npc: 'Character', player: 'Character', value: int) -> None:
        """Set NPC's disposition toward a specific player."""
        key = f"{self.VAR_DISPOSITION}_{player.id}"
        npc.perm_variables[key] = max(0, min(100, value))
    
    def get_conversation_history(self, npc: 'Character', player: 'Character') -> List[Dict[str, str]]:
        """Get conversation history between NPC and player."""
        key = f"{self.VAR_CONVERSATION_HISTORY}_{player.id}"
        return npc.get_temp_var(key, [])
    
    def add_to_history(self, npc: 'Character', player: 'Character', role: str, content: str) -> None:
        """Add a message to conversation history."""
        key = f"{self.VAR_CONVERSATION_HISTORY}_{player.id}"
        history = self.get_conversation_history(npc, player)
        history.append({"role": role, "content": content})
        
        # Trim history if too long
        while len(history) > self.MAX_HISTORY_TURNS:
            history.pop(0)
        
        # Also trim by character count
        total_chars = sum(len(h["content"]) for h in history)
        while total_chars > self.MAX_HISTORY_CHARS and len(history) > 2:
            removed = history.pop(0)
            total_chars -= len(removed["content"])
        
        npc.temp_variables[key] = history
    
    def clear_history(self, npc: 'Character', player: 'Character') -> None:
        """Clear conversation history (e.g., when conversation ends)."""
        key = f"{self.VAR_CONVERSATION_HISTORY}_{player.id}"
        npc.temp_variables[key] = []
    
    def get_revealed_knowledge(self, npc: 'Character', player: 'Character') -> List[str]:
        """Get list of knowledge IDs revealed to this player."""
        key = f"{self.VAR_REVEALED}_{player.id}"
        return npc.get_perm_var(key, [])
    
    def get_achieved_goals(self, npc: 'Character', player: 'Character') -> List[str]:
        """Get list of goal IDs achieved with this player."""
        key = f"{self.VAR_ACHIEVED}_{player.id}"
        return npc.get_perm_var(key, [])
    
    # Variable key for player's world state knowledge (stored on player, not NPC)
    VAR_WORLD_KNOWLEDGE = "llm_world_knowledge"
    
    def get_common_knowledge(
        self, 
        npc: 'Character', 
        player: 'Character',
        context: NPCConversationContext, 
        game_state: 'GameStateInterface'
    ) -> List[str]:
        """
        Get common knowledge entries that this NPC has access to.
        Only fetched at conversation start (when history is empty).
        
        Supports:
        - Local zone references: "village_rumors" 
        - Cross-zone references: "central_city.town_burned"
        - Player-specific world state (stored in player's perm_variables)
        
        The player's world knowledge overrides zone defaults, allowing quests
        and events to change what NPCs "know" based on player actions.
        
        Args:
            npc: The NPC character
            player: The player character (for world state lookups)
            context: The NPC's conversation context
            game_state: Current game state for zone lookup
            
        Returns:
            List of common knowledge content strings
        """
        if not context.common_knowledge_refs:
            return []
        
        common_knowledge = []
        
        # Get the NPC's home zone (for local refs)
        home_zone = None
        if npc.location_room and hasattr(npc.location_room, 'zone'):
            home_zone = npc.location_room.zone
        
        if home_zone is None:
            # Try to find zone from definition
            if hasattr(npc, 'definition_zone_id') and npc.definition_zone_id:
                zone_id = npc.definition_zone_id
                if hasattr(game_state, 'world_definition') and zone_id in game_state.world_definition.zones:
                    home_zone = game_state.world_definition.zones[zone_id]
        
        # Get player's world knowledge (overrides zone defaults based on their actions)
        player_world_knowledge = player.get_perm_var(self.VAR_WORLD_KNOWLEDGE, {})
        
        # Look up each referenced common knowledge entry
        for ref in context.common_knowledge_refs:
            # First check player's world knowledge overrides
            if ref in player_world_knowledge:
                common_knowledge.append(player_world_knowledge[ref])
                continue
            
            # Check for cross-zone reference (zone_id.knowledge_id format)
            if '.' in ref:
                zone_id, knowledge_id = ref.split('.', 1)
                
                # Check player's world knowledge with full path
                if ref in player_world_knowledge:
                    common_knowledge.append(player_world_knowledge[ref])
                    continue
                
                # Look up in the specified zone
                if hasattr(game_state, 'world_definition') and zone_id in game_state.world_definition.zones:
                    target_zone = game_state.world_definition.zones[zone_id]
                    if knowledge_id in target_zone.common_knowledge:
                        common_knowledge.append(target_zone.common_knowledge[knowledge_id])
                    else:
                        self._logger.warning(f"Common knowledge '{knowledge_id}' not found in zone {zone_id}")
                else:
                    self._logger.warning(f"Zone '{zone_id}' not found for common knowledge ref '{ref}'")
            else:
                # Local zone reference
                if home_zone is None:
                    self._logger.warning(f"No home zone for NPC {npc.name}, cannot resolve local ref '{ref}'")
                    continue
                    
                if ref in home_zone.common_knowledge:
                    common_knowledge.append(home_zone.common_knowledge[ref])
                else:
                    self._logger.warning(f"Common knowledge '{ref}' not found in zone {home_zone.id}")
        
        return common_knowledge
    
    @staticmethod
    def set_world_knowledge(player: 'Character', knowledge_id: str, content: str) -> None:
        """
        Set or update world knowledge for a player.
        
        This overrides zone-level common knowledge from the player's perspective.
        When this player talks to NPCs, they'll reference this updated knowledge.
        
        Args:
            player: The player character
            knowledge_id: The knowledge ID (can be local or cross-zone format)
            content: The knowledge content
            
        Example:
            # After the player finds a body
            NPCConversationHandler.set_world_knowledge(player, "murder_case", 
                "A body was discovered in the old mill")
            
            # After the player witnesses an event in another zone
            NPCConversationHandler.set_world_knowledge(player, "central_city.fire",
                "The market district burned down - you saw it happen")
        """
        world_knowledge = player.get_perm_var(NPCConversationHandler.VAR_WORLD_KNOWLEDGE, {})
        world_knowledge[knowledge_id] = content
        player.perm_variables[NPCConversationHandler.VAR_WORLD_KNOWLEDGE] = world_knowledge
    
    @staticmethod
    def clear_world_knowledge(player: 'Character', knowledge_id: str) -> None:
        """
        Clear world knowledge for a player, reverting to zone-level defaults.
        
        Args:
            player: The player character
            knowledge_id: The knowledge ID to clear
        """
        world_knowledge = player.get_perm_var(NPCConversationHandler.VAR_WORLD_KNOWLEDGE, {})
        if knowledge_id in world_knowledge:
            del world_knowledge[knowledge_id]
            player.perm_variables[NPCConversationHandler.VAR_WORLD_KNOWLEDGE] = world_knowledge
    
    @staticmethod
    def get_player_world_knowledge(player: 'Character') -> Dict[str, str]:
        """
        Get all world knowledge overrides for a player.
        
        Args:
            player: The player character
            
        Returns:
            Dictionary of knowledge_id -> content
        """
        return player.get_perm_var(NPCConversationHandler.VAR_WORLD_KNOWLEDGE, {})

    async def process_speech(
        self,
        player: 'Character',
        npc: 'Character',
        speech: str,
        game_state: 'GameStateInterface',
        trigger_actions: list = None
    ) -> ConversationResult:
        """
        Process player speech directed at an NPC.
        
        Args:
            player: The player character speaking
            npc: The NPC being spoken to
            speech: What the player said
            game_state: Current game state
            trigger_actions: Optional list of trigger scripts that just executed
                            (provides context for LLM about what the NPC just did)
            
        Returns:
            ConversationResult with NPC's response and any state changes
        """
        self._logger.debug(f"Processing speech from {player.name} to {npc.name}: {speech}")
        if trigger_actions:
            self._logger.debug(f"Trigger actions executed: {trigger_actions}")
        
        try:
            # Get context and state
            context = self.get_npc_context(npc)
            disposition = self.get_disposition(npc, player)
            history = self.get_conversation_history(npc, player)
            revealed = self.get_revealed_knowledge(npc, player)
            achieved = self.get_achieved_goals(npc, player)
            
            # Get common knowledge only at conversation start
            common_knowledge = []
            if not history:
                common_knowledge = self.get_common_knowledge(npc, player, context, game_state)
            
            # Build the prompt
            prompt = self._build_prompt(
                npc=npc,
                player=player,
                context=context,
                disposition=disposition,
                history=history,
                revealed=revealed,
                achieved=achieved,
                speech=speech,
                common_knowledge=common_knowledge,
                trigger_actions=trigger_actions
            )
            
            # Get LLM response with config from app settings
            _, LLMConfig, _ = get_llm_client()
            llm_settings = get_llm_config()
            config = LLMConfig(
                temperature=llm_settings.get("temperature", 0.8) if llm_settings else 0.8,
                max_output_tokens=llm_settings.get("max_output_tokens", 500) if llm_settings else 500,
            )
            
            response = await self.client.generate_async(prompt, config=config)
            raw_response = response.content
            
            self._logger.debug(f"LLM response: {raw_response}")
            
            # Parse response
            dialogue, state_change, emotes = self._parse_response(raw_response, context)
            
            # Update conversation history (store full dialogue including emotes for context)
            self.add_to_history(npc, player, "user", speech)
            self.add_to_history(npc, player, "assistant", raw_response.split('```')[0].strip())
            
            # Apply state changes
            await self._apply_state_changes(npc, player, state_change, game_state)
            
            return ConversationResult(
                dialogue=dialogue,
                state_change=state_change,
                raw_response=raw_response,
                emotes=emotes
            )
            
        except Exception as e:
            self._logger.error(f"Error processing speech: {e}")
            return ConversationResult(
                dialogue="*looks at you blankly*",
                state_change=StateChange(),
                raw_response="",
                error=str(e)
            )
    
    def _build_prompt(
        self,
        npc: 'Character',
        player: 'Character',
        context: NPCConversationContext,
        disposition: int,
        history: List[Dict[str, str]],
        revealed: List[str],
        achieved: List[str],
        speech: str,
        common_knowledge: Optional[List[str]] = None,
        trigger_actions: Optional[List[str]] = None
    ) -> str:
        """Build the conversation prompt for the LLM."""
        
        # Format history
        if history:
            history_text = "\n".join(
                f"{'Player' if h['role'] == 'user' else npc.name}: {h['content']}"
                for h in history[-10:]  # Last 10 exchanges
            )
        else:
            history_text = "(This is the start of the conversation)"
        
        # Format revealed knowledge
        revealed_text = ", ".join(revealed) if revealed else "nothing yet"
        
        # Format common knowledge (only included at conversation start)
        common_knowledge_section = ""
        if common_knowledge:
            ck_items = "\n".join(f"- {ck}" for ck in common_knowledge)
            common_knowledge_section = f"""
## Common Knowledge (what everyone around here knows)
{ck_items}
"""
        
        # Format trigger actions context (scripted actions that just happened)
        trigger_context_section = ""
        if trigger_actions:
            # Join multiple trigger scripts and format them
            actions_text = "\n".join(f"- {action.strip()}" for action in trigger_actions)
            trigger_context_section = f"""
## You Just Performed These Scripted Actions
(Your scripted triggers just executed the following - acknowledge or respond to what you just did)
{actions_text}
"""
        
        # Build prompt with universal system instructions prepended
        prompt = f"""{UNIVERSAL_SYSTEM_INSTRUCTIONS}
You are roleplaying as {npc.name} in a text-based fantasy MUD game.

## Your Character
{context.to_prompt_section()}
{common_knowledge_section}{trigger_context_section}
## Current State
- Your disposition toward this player ({player.name}): {disposition}/100
  (0=hostile, 25=distrustful, 50=neutral, 75=friendly, 100=devoted)
- Already revealed to them: {revealed_text}

## Conversation Rules
1. Stay completely in character - never break the fourth wall
2. Keep responses concise (1-3 sentences typically, can be longer for important moments)
3. Your disposition can change based on how the player treats you
4. Only reveal secrets if your disposition is high enough AND they ask/it's relevant
5. For physical actions/emotes, put them on their own line with *asterisks* (e.g. "*tilts head thoughtfully*"). Do NOT use asterisks for emphasis in speech.
6. Don't explain game mechanics or your own decision-making
7. NEVER prefix your dialogue with your name (e.g. don't say "The Archivist: Hello" - just say "Hello")
8. If scripted actions are listed above, you already performed them - acknowledge or followup naturally, don't repeat the action

## CRITICAL: No Hallucination
- ONLY state facts that are explicitly in your knowledge above or common knowledge
- NEVER invent directions, locations, distances, or navigation ("go east then south")
- NEVER invent specific details about people, places, or events not in your knowledge
- If asked about something not in your knowledge, say you don't know or deflect vaguely
- You can make up small talk, opinions, and atmosphere, but NOT factual game-world information

## Response Format
First, write your in-character dialogue response.
Then, on a new line, output a JSON block with state changes and optional commands:

```json
{{"disposition_delta": <-20 to +20 or 0>, "revealed": ["knowledge_id", ...], "achieved": ["goal_id", ...], "action": null, "commands": []}}
```

The JSON block is REQUIRED even if nothing changes (use zeros/empty arrays).
- action: null, "ends_conversation", or leave empty (use commands for give/attack/flee instead)
- commands: Array of game commands for you (the NPC) to execute after speaking

{NPC_COMMAND_REFERENCE}

## Conversation History
{history_text}

---
Player says: "{speech}"

Respond as {npc.name}:"""
        
        return prompt
    
    def _parse_response(self, response: str, context: NPCConversationContext) -> tuple[str, StateChange, List[str]]:
        """Parse LLM response into dialogue, state changes, and extracted emotes."""
        
        # Try to extract JSON block
        json_match = re.search(r'```json\s*(\{[^`]+\})\s*```', response, re.DOTALL)
        
        if json_match:
            dialogue = response[:json_match.start()].strip()
            try:
                state_data = json.loads(json_match.group(1))
                state_change = StateChange(
                    disposition_delta=state_data.get("disposition_delta", 0),
                    revealed_knowledge=state_data.get("revealed", []),
                    achieved_goals=state_data.get("achieved", []),
                    set_variables=state_data.get("set_vars", {}),
                    npc_action=state_data.get("action"),
                    commands=state_data.get("commands", [])
                )
            except json.JSONDecodeError:
                self._logger.warning(f"Failed to parse state JSON: {json_match.group(1)}")
                state_change = StateChange()
        else:
            # No JSON found, try inline format
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                dialogue = response[:json_match.start()].strip()
                try:
                    state_data = json.loads(json_match.group(0))
                    state_change = StateChange(
                        disposition_delta=state_data.get("disposition_delta", 0),
                        revealed_knowledge=state_data.get("revealed", []),
                        achieved_goals=state_data.get("achieved", []),
                        npc_action=state_data.get("action"),
                        commands=state_data.get("commands", [])
                    )
                except json.JSONDecodeError:
                    dialogue = response.strip()
                    state_change = StateChange()
            else:
                dialogue = response.strip()
                state_change = StateChange()
        
        # Clean up dialogue
        dialogue = dialogue.strip()
        if dialogue.endswith("```"):
            dialogue = dialogue[:-3].strip()
        
        # Extract emotes - only asterisk-wrapped text that looks like an action, not emphasis
        # Emotes are typically: at the start of dialogue, on their own line, or multi-word actions
        # Single words like *how* or *past* are emphasis, not emotes
        emotes = []
        
        # Pattern for emotes: must be multi-word (contains a space) to distinguish from emphasis
        # Also check if at start of line/dialogue
        lines = dialogue.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Check if entire line is an emote (starts and ends with asterisks, multi-word)
            emote_line_match = re.match(r'^\*([^*]+)\*$', line)
            if emote_line_match:
                emote_text = emote_line_match.group(1).strip()
                # Only treat as emote if it's multi-word (likely an action)
                if ' ' in emote_text:
                    emotes.append(emote_text)
                    continue  # Don't add this line to dialogue
            
            # Check for emote at start of line followed by speech
            start_emote_match = re.match(r'^\*([^*]+)\*\s*(.*)$', line)
            if start_emote_match:
                emote_text = start_emote_match.group(1).strip()
                rest_of_line = start_emote_match.group(2).strip()
                # Only treat as emote if it's multi-word (likely an action)
                if ' ' in emote_text:
                    emotes.append(emote_text)
                    if rest_of_line:
                        cleaned_lines.append(rest_of_line)
                    continue
            
            # Keep the line as-is (including any *emphasis* words)
            cleaned_lines.append(line)
        
        dialogue = ' '.join(cleaned_lines)
        # Clean up any double spaces
        dialogue = ' '.join(dialogue.split())
        
        return dialogue, state_change, emotes
    
    async def _apply_state_changes(
        self,
        npc: 'Character',
        player: 'Character',
        state_change: StateChange,
        game_state: 'GameStateInterface'
    ) -> None:
        """Apply state changes from conversation to game state."""
        
        # Update disposition
        if state_change.disposition_delta != 0:
            current = self.get_disposition(npc, player)
            new_disposition = current + state_change.disposition_delta
            self.set_disposition(npc, player, new_disposition)
            self._logger.debug(
                f"Disposition {npc.name} -> {player.name}: {current} -> {new_disposition}"
            )
        
        # Record revealed knowledge
        if state_change.revealed_knowledge:
            key = f"{self.VAR_REVEALED}_{player.id}"
            revealed = npc.get_perm_var(key, [])
            for knowledge_id in state_change.revealed_knowledge:
                if knowledge_id not in revealed:
                    revealed.append(knowledge_id)
                    self._logger.debug(f"NPC {npc.name} revealed '{knowledge_id}' to {player.name}")
            npc.perm_variables[key] = revealed
        
        # Record achieved goals and apply their effects
        if state_change.achieved_goals:
            key = f"{self.VAR_ACHIEVED}_{player.id}"
            achieved = npc.get_perm_var(key, [])
            context = self.get_npc_context(npc)
            
            for goal_id in state_change.achieved_goals:
                if goal_id not in achieved:
                    achieved.append(goal_id)
                    self._logger.debug(f"Goal '{goal_id}' achieved with {npc.name}")
                    
                    # Find the goal and apply its effects
                    for goal in context.goals:
                        if goal.id == goal_id:
                            # Set any variables defined by the goal
                            for var_name, var_value in goal.on_achieve_set_vars.items():
                                if var_name.startswith("player."):
                                    player.perm_variables[var_name[7:]] = var_value
                                elif var_name.startswith("npc."):
                                    npc.perm_variables[var_name[4:]] = var_value
                                else:
                                    player.perm_variables[var_name] = var_value
                            
                            # Show achievement message if defined
                            if goal.on_achieve_message and player.connection:
                                await player.send_text(CommTypes.DYNAMIC, goal.on_achieve_message)
                            break
            
            npc.perm_variables[key] = achieved
        
        # Apply any direct variable sets
        for var_name, var_value in state_change.set_variables.items():
            if var_name.startswith("player."):
                player.perm_variables[var_name[7:]] = var_value
            elif var_name.startswith("npc."):
                npc.perm_variables[var_name[4:]] = var_value
        
        # Handle special actions
        if state_change.npc_action:
            await self._handle_npc_action(npc, player, state_change.npc_action, game_state)
        
        # Execute command stack
        if state_change.commands:
            await self._execute_command_stack(npc, player, state_change.commands, game_state)
    
    async def _execute_command_stack(
        self,
        npc: 'Character',
        player: 'Character',
        commands: List[str],
        game_state: 'GameStateInterface'
    ) -> None:
        """
        Execute a stack of commands on behalf of the NPC.
        
        This allows the LLM to direct the NPC to perform game actions
        after their dialogue response.
        """
        from .command_handler import CommandHandler
        import asyncio
        
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            
            # Security: Limit what commands NPCs can execute
            allowed_prefixes = [
                "north", "south", "east", "west", "up", "down", "out", "in",
                "give", "emote", "say", "attack", "kill", "pause",
                "n", "s", "e", "w", "u", "d"
            ]
            
            cmd_lower = cmd.lower()
            cmd_word = cmd_lower.split()[0] if cmd_lower.split() else ""
            
            if cmd_word not in allowed_prefixes:
                self._logger.warning(f"NPC {npc.name} tried disallowed command: {cmd}")
                continue
            
            # Special handling for give command - replace "player" with actual player reference
            if cmd_word == "give":
                # Format: give <item> player -> give <item> <player_keyword>
                cmd = cmd.replace(" player", f" {player.name}")
            
            self._logger.debug(f"NPC {npc.name} executing command: {cmd}")
            
            try:
                # Small delay between commands for natural feel
                await asyncio.sleep(0.2)
                await CommandHandler.process_command(npc, cmd, {})
            except Exception as e:
                self._logger.error(f"Error executing NPC command '{cmd}': {e}")
    
    async def _handle_npc_action(
        self,
        npc: 'Character',
        player: 'Character',
        action: str,
        game_state: 'GameStateInterface'
    ) -> None:
        """Handle special NPC actions signaled by the LLM."""
        
        action = action.lower().strip()
        
        if action == "ends_conversation":
            self.clear_history(npc, player)
            self._logger.debug(f"NPC {npc.name} ended conversation with {player.name}")
        
        elif action == "attacks":
            # TODO: Integrate with combat system
            self._logger.debug(f"NPC {npc.name} wants to attack {player.name}")
            # This would trigger combat initiation
        
        elif action == "flees":
            # TODO: Integrate with movement system
            self._logger.debug(f"NPC {npc.name} wants to flee from {player.name}")
        
        elif action == "gives_item":
            # TODO: Integrate with inventory system
            self._logger.debug(f"NPC {npc.name} wants to give item to {player.name}")
        
        # Add more actions as needed
    
    def _context_to_dict(self, context: NPCConversationContext) -> dict:
        """Convert context to dict for storage."""
        return {
            "personality": context.personality,
            "speaking_style": context.speaking_style,
            "knowledge": [
                {"id": k.id, "content": k.content, "reveal_threshold": k.reveal_threshold, "is_secret": k.is_secret}
                for k in context.knowledge
            ],
            "goals": [
                {
                    "id": g.id, "description": g.description, "condition": g.condition,
                    "disposition_required": g.disposition_required,
                    "on_achieve_set_vars": g.on_achieve_set_vars,
                    "on_achieve_message": g.on_achieve_message
                }
                for g in context.goals
            ],
            "will_discuss": context.will_discuss,
            "will_not_discuss": context.will_not_discuss,
            "special_instructions": context.special_instructions,
            "common_knowledge_refs": context.common_knowledge_refs,
        }
    
    def _context_from_dict(self, data: dict) -> NPCConversationContext:
        """Reconstruct context from dict."""
        return NPCConversationContext(
            personality=data.get("personality", ""),
            speaking_style=data.get("speaking_style", ""),
            knowledge=[
                NPCKnowledge(
                    id=k["id"],
                    content=k["content"],
                    reveal_threshold=k.get("reveal_threshold", 60),
                    is_secret=k.get("is_secret", True)
                )
                for k in data.get("knowledge", [])
            ],
            goals=[
                ConversationGoal(
                    id=g["id"],
                    description=g["description"],
                    condition=g["condition"],
                    disposition_required=g.get("disposition_required"),
                    on_achieve_set_vars=g.get("on_achieve_set_vars", {}),
                    on_achieve_message=g.get("on_achieve_message")
                )
                for g in data.get("goals", [])
            ],
            will_discuss=data.get("will_discuss", []),
            will_not_discuss=data.get("will_not_discuss", []),
            special_instructions=data.get("special_instructions", ""),
            common_knowledge_refs=data.get("common_knowledge_refs", []),
        )


# Convenience function for creating configured NPCs
def configure_npc_for_conversation(
    npc: 'Character',
    personality: str,
    knowledge: Optional[List[dict]] = None,
    goals: Optional[List[dict]] = None,
    speaking_style: str = "",
    special_instructions: str = "",
    common_knowledge_refs: Optional[List[str]] = None
) -> None:
    """
    Configure an NPC for LLM-driven conversation.
    
    Example:
        configure_npc_for_conversation(
            npc=old_tom,
            personality="A grizzled gravedigger who has seen too much. Paranoid but kind-hearted.",
            knowledge=[
                {"id": "crypt_location", "content": "The old crypt is behind the willow tree", "reveal_threshold": 60},
                {"id": "ghost_story", "content": "A woman's ghost haunts the eastern graves", "is_secret": False},
            ],
            goals=[
                {
                    "id": "trust_earned",
                    "description": "Player earns the gravedigger's trust",
                    "condition": "Player shows genuine respect for the dead or helps with a task",
                    "on_achieve_set_vars": {"player.gravedigger_trusts": True},
                    "on_achieve_message": "Old Tom seems to regard you with newfound respect."
                }
            ],
            speaking_style="Speaks in a low, gravelly voice. Often trails off mid-sentence.",
            common_knowledge_refs=["village_rumors", "cemetery_history"],
        )
    """
    handler = NPCConversationHandler()
    
    context = NPCConversationContext(
        personality=personality,
        speaking_style=speaking_style,
        special_instructions=special_instructions,
        common_knowledge_refs=common_knowledge_refs or [],
        knowledge=[
            NPCKnowledge(
                id=k["id"],
                content=k["content"],
                reveal_threshold=k.get("reveal_threshold", 60),
                is_secret=k.get("is_secret", True)
            )
            for k in (knowledge or [])
        ],
        goals=[
            ConversationGoal(
                id=g["id"],
                description=g["description"],
                condition=g["condition"],
                disposition_required=g.get("disposition_required"),
                on_achieve_set_vars=g.get("on_achieve_set_vars", {}),
                on_achieve_message=g.get("on_achieve_message")
            )
            for g in (goals or [])
        ],
    )
    
    handler.set_npc_context(npc, context)


# Singleton handler instance for easy access
_default_handler: Optional[NPCConversationHandler] = None

def get_conversation_handler() -> NPCConversationHandler:
    """Get the default conversation handler instance."""
    global _default_handler
    if _default_handler is None:
        _default_handler = NPCConversationHandler()
    return _default_handler
