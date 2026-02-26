"""
LLM-Driven NPC Conversation Handler
Final Consolidated Version: Includes Quest Variable Support and Scripted Action Menu.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum

from .structured_logger import StructuredLogger
from .communication import CommTypes

if TYPE_CHECKING:
    from .nondb_models.characters import Character
    from .comprehensive_game_state_interface import GameStateInterface

# ==========================================
# DATA MODELS
# ==========================================

@dataclass
class StateChange:
    """Represents a state change signaled by the LLM response."""
    disposition_delta: int = 0
    revealed_knowledge: List[str] = field(default_factory=list)
    achieved_goals: List[str] = field(default_factory=list)
    set_variables: Dict[str, Any] = field(default_factory=dict)
    npc_action: Optional[str] = None  
    
    # PHASE 5 INTEGRATION
    selected_action: Optional[str] = None  # The ID chosen from the NPC's 'llm_actions' menu
    quest_updates: Dict[str, Any] = field(default_factory=dict)  # Updates for the Quest State Machine

@dataclass
class ConversationResult:
    dialogue: str
    state_change: StateChange
    raw_response: str
    emotes: List[str] = field(default_factory=list)
    error: Optional[str] = None

# ==========================================
# CORE HANDLER
# ==========================================

class NPCConversationHandler:
    VAR_DISPOSITION = "llm_disposition"
    VAR_CONVERSATION_HISTORY = "llm_convo"
    VAR_REVEALED = "llm_revealed"
    VAR_ACHIEVED = "llm_achieved"
    VAR_CONTEXT = "llm_context"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key_override = api_key
        self._model_override = model
        self._client = None
        self._logger = StructuredLogger(__name__, prefix="NPCConversationHandler> ")

    @property
    def client(self):
        if self._client is None:
            # Create client from app config (no separate helpers module)
            from .config import default_app_config
            from .llm_client import create_client
            from . import llm_client_gemini  # noqa: F401 - register Gemini provider
            llm_cfg = default_app_config.LLM or {}
            provider = llm_cfg.get("provider", "gemini")
            api_key = self._api_key_override or llm_cfg.get("api_key")
            model = self._model_override or llm_cfg.get("model")
            self._client = create_client(provider, api_key=api_key, model=model)
        return self._client

    async def process_speech(self, player, npc, speech, game_state, trigger_actions=None) -> ConversationResult:
        """Processes player speech and handles the 'Action Menu' and Quest Updates."""
        try:
            # 1. Gather State
            disposition = self.get_disposition(npc, player)
            history = self.get_conversation_history(npc, player)
            revealed = self.get_revealed_knowledge(npc, player)
            
            # 2. Build the Prompt (Including the Action Menu)
            prompt = self._build_prompt(npc, player, disposition, history, revealed, speech, trigger_actions, game_state)

            # 3. Call LLM
            from .llm_client import LLMConfig
            llm_settings = game_state.app_config.LLM or {}
            config = LLMConfig(
                temperature=llm_settings.get("temperature", 0.8),
                max_output_tokens=llm_settings.get("max_output_tokens", 500),
            )
            response = await self.client.generate_async(prompt, config=config)
            
            # 4. Parse Dialogue and JSON
            dialogue, state_change, emotes = self._parse_response(response.content)

            # Log request/response (and parsed state) to file if LLM_CONVERSATION_LOG is set (append)
            log_path = os.environ.get("LLM_CONVERSATION_LOG", "").strip().strip('"').strip("'")
            if log_path:
                try:
                    entry = {
                        "request": {"prompt": prompt, "speech": speech},
                        "response": response.content,
                        "parsed": {
                            "quest_updates": state_change.quest_updates,
                            "selected_action": state_change.selected_action,
                            "disposition_delta": state_change.disposition_delta,
                            "revealed": state_change.revealed_knowledge,
                        },
                    }
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
                except Exception as log_err:
                    self._logger.warning(f"Failed to write LLM conversation log: {log_err}")

            # 5. EXECUTE STATE CHANGES (Applying Quest and Action logic)
            await self._apply_state_changes(npc, player, state_change, game_state)

            # 6. Save History
            self.add_to_history(npc, player, "user", speech)
            self.add_to_history(npc, player, "assistant", dialogue)

            return ConversationResult(dialogue, state_change, response.content, emotes)

        except Exception as e:
            self._logger.error(f"Conversation error: {e}")
            return ConversationResult("*looks confused*", StateChange(), "", error=str(e))

    def _build_prompt(self, npc, player, disposition, history, revealed, speech, trigger_actions, game_state=None) -> str:
        """Injects goals (behavior), conversation_results (when/then vars), scripted actions, and player's current knowledge into the system instructions."""
        
        context = npc.get_perm_var(self.VAR_CONTEXT, {})

        # Goals: behavioral guidance for the NPC ("your goal is to ...")
        goals = context.get("goals", [])
        goals_section = ""
        if goals:
            lines = []
            for g in goals:
                desc = (g.get("description") or "").strip()
                cond = (g.get("condition") or "").strip()
                if desc:
                    lines.append(f"- {desc}")
                if cond:
                    lines.append(f"  (when: {cond})")
            if lines:
                goals_section = "\n## YOUR GOALS\nHow you should behave; pursue these as the conversation allows:\n" + "\n".join(lines) + "\n"

        # Scripted actions: "here are the actions you can perform: give_note: you give the player the note"
        actions = npc.get_perm_var("llm_actions", {})
        action_menu = ""
        if actions:
            items = [f'- "{aid}": {data.get("description", "")}' for aid, data in actions.items()]
            action_menu = "\n## ACTIONS YOU CAN PERFORM\nUse selected_action in your JSON to trigger one of these (or null for none):\n" + "\n".join(items) + "\n"

        # When/then variable setting: "if and when you tell the player X, set Y to Z"
        conversation_results = context.get("conversation_results", [])
        if not conversation_results:
            # Fallback: derive from goals' on_achieve_set_vars + description
            for g in goals:
                set_vars = g.get("on_achieve_set_vars") or {}
                desc = (g.get("description") or "").strip()
                if set_vars and desc:
                    conversation_results = conversation_results + [{"condition": desc, "set": set_vars}]
        quest_section = ""
        if conversation_results:
            lines = []
            for cr in conversation_results:
                cond = cr.get("condition", "").strip()
                set_dict = cr.get("set") or {}
                if cond and set_dict:
                    vars_list = ", ".join(f'"{k}": {json.dumps(v)}' for k, v in set_dict.items())
                    lines.append(f"- When: \"{cond}\" → set quest_updates to {{{vars_list}}}")
            if lines:
                quest_section = "\n## CONVERSATION RESULTS (set these in quest_updates when your reply matches)\n" + "\n".join(lines) + "\n"

        # Player's current knowledge (resolved from zone common_knowledge; replacement/supersede already applied)
        player_knowledge_section = ""
        if game_state is not None:
            from .nondb_models.quests import get_resolved_llm_knowledge
            resolved = get_resolved_llm_knowledge(game_state, player)
            if resolved:
                blocks = []
                for _kid, content in resolved.items():
                    text = (content or "").strip()
                    if text:
                        blocks.append(text)
                if blocks:
                    player_knowledge_section = "\n## WHAT THE PLAYER ALREADY KNOWS\nUse this as the current state of what this player has learned. Avoid repeating it; tailor your reply to it.\n\n" + "\n\n".join(blocks) + "\n"

        return f"""[SYSTEM: MUD_NPC_PROTOCOL]
You are {npc.name}. 
Personality: {npc.description}
Current Disposition: {disposition}/100
{goals_section}
{action_menu}
{quest_section}
{player_knowledge_section}
## RESPONSE FORMAT
Respond with dialogue first, then a JSON block:
```json
{{
  "disposition_delta": 0,
  "selected_action": "ACTION_ID_OR_NULL",
  "quest_updates": {{"variable.name": value}},
  "revealed": []
}}
```
Player says: "{speech}"
"""

    def _parse_response(self, response: str):
        """Extracts text and JSON safely."""
        
        # Search for the JSON block in the LLM response
        json_match = re.search(r'`{3}json\s*(\{.*?\})\s*`{3}', response, re.DOTALL)
        
        if json_match:
            dialogue = response[:json_match.start()].strip()
            try:
                data = json.loads(json_match.group(1))
                state_change = StateChange(
                    disposition_delta=data.get("disposition_delta", 0),
                    selected_action=data.get("selected_action"),
                    quest_updates=data.get("quest_updates", {}),
                    revealed_knowledge=data.get("revealed", [])
                )
            except Exception as e:
                self._logger.error(f"Failed to parse LLM JSON: {e}")
                state_change = StateChange()
        else:
            dialogue = response.strip()
            state_change = StateChange()

        # REQUIRED: Basic emote extraction (e.g., *nods slowly*)
        emotes = re.findall(r'\*(.*?)\*', dialogue)
        dialogue = re.sub(r'\*.*?\*', '', dialogue).strip()
        
        return dialogue, state_change, emotes
    
    async def _apply_state_changes(self, npc, player, state_change, game_state):
        """The Engine: Executes the LLM's intents."""
        
        # 1. Update Disposition
        if state_change.disposition_delta != 0:
            new_val = self.get_disposition(npc, player) + state_change.disposition_delta
            self.set_disposition(npc, player, new_val)

        # 2. Execute Quest Variable Updates
        if state_change.quest_updates:
            from .nondb_models.quests import set_quest_var
            for var_path, val in state_change.quest_updates.items():
                set_quest_var(player, var_path, val)

        # 3. Execute Scripted Actions (The Action Menu Logic)
        if state_change.selected_action:
            available = npc.get_perm_var("llm_actions", {})
            if state_change.selected_action in available:
                action_def = available[state_change.selected_action]
                commands = action_def.get("commands", [])
                
                from .command_handler import CommandHandler
                for cmd in commands:
                    # Token replacement for player identity
                    final_cmd = cmd.replace("%s%", player.name).replace("%S%", player.rid)
                    # Execute command AS the NPC
                    await CommandHandler.process_command(npc, final_cmd, {}, from_script=True)

    def get_disposition(self, npc, player):
        return npc.get_perm_var(f"{self.VAR_DISPOSITION}_{player.id}", 50)

    def set_disposition(self, npc, player, val):
        npc.perm_variables[f"{self.VAR_DISPOSITION}_{player.id}"] = max(0, min(100, val))

    def get_conversation_history(self, npc, player):
        return npc.get_temp_var(f"{self.VAR_CONVERSATION_HISTORY}_{player.id}", [])

    def add_to_history(self, npc, player, role, content):
        key = f"{self.VAR_CONVERSATION_HISTORY}_{player.id}"
        history = self.get_conversation_history(npc, player)
        history.append({"role": role, "content": content})
        npc.temp_variables[key] = history[-20:] # Keep last 20

    def get_revealed_knowledge(self, npc, player):
        return npc.get_perm_var(f"{self.VAR_REVEALED}_{player.id}", [])


_conversation_handler_instance: Optional[NPCConversationHandler] = None


def get_conversation_handler() -> NPCConversationHandler:
    """Return the singleton NPC conversation handler instance."""
    global _conversation_handler_instance
    if _conversation_handler_instance is None:
        _conversation_handler_instance = NPCConversationHandler()
    return _conversation_handler_instance