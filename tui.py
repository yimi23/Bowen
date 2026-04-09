"""
tui.py — BOWEN Terminal Interface.
Aesthetic: Summit Technical Partners — ultra-deep black, warm tan, cream text.

Shortcuts:
  Enter       — send message
  Tab         — cycle agent (BOWEN → CAPTAIN → SCOUT → TAMARA → HELEN)
  Ctrl+V      — toggle voice mode (wake word + mic)
  Escape      — clear input
  Ctrl+C      — quit
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, RichLog, Static
from textual import work

from config import Config
from memory.store import MemoryStore
from memory.mem0_layer import Mem0Layer
from bus.message_bus import MessageBus
from agents.bowen import BOWENAgent
from agents.captain import CaptainAgent
from agents.scout import ScoutAgent
from agents.tamara import TamaraAgent
from agents.helen import HelenAgent
import tools.registry as registry


# ── Palette ───────────────────────────────────────────────────────────────────

BG        = "#0a0a0a"
BG_PANEL  = "#0f0f0f"
BORDER    = "#1e1e1e"
TAN       = "#c8b89a"
CREAM     = "#f5f2ee"
DIM       = "#4a4540"
MUTED     = "#2a2520"
ERR       = "#c0705a"
GREEN     = "#8ab89a"    # voice active indicator

AGENT_ORDER = ["BOWEN", "CAPTAIN", "SCOUT", "TAMARA", "HELEN"]

AGENT_ROLE = {
    "BOWEN":   "Orchestrator",
    "CAPTAIN": "Code & Builds",
    "SCOUT":   "Research",
    "TAMARA":  "Communications",
    "HELEN":   "Calendar & Tasks",
}


# ── Sidebar ───────────────────────────────────────────────────────────────────

class AgentPanel(Static):
    active_agent: reactive[str] = reactive("BOWEN")
    voice_active: reactive[bool] = reactive(False)

    def render(self) -> str:
        lines = []
        lines.append(f"[bold {TAN}]BOWEN[/bold {TAN}]")
        lines.append(f"[{DIM}]personal OS[/{DIM}]")
        lines.append("")
        lines.append(f"[{MUTED}]{'─' * 16}[/{MUTED}]")
        lines.append("")

        for name in AGENT_ORDER:
            if name == self.active_agent:
                lines.append(f"[bold {TAN}]▸ {name}[/bold {TAN}]")
                lines.append(f"  [{DIM}]{AGENT_ROLE[name]}[/{DIM}]")
            else:
                lines.append(f"  [{DIM}]{name}[/{DIM}]")
            lines.append("")

        lines.append(f"[{MUTED}]{'─' * 16}[/{MUTED}]")
        lines.append("")

        # Voice status
        if self.voice_active:
            lines.append(f"[bold {GREEN}]◉ voice on[/bold {GREEN}]")
        else:
            lines.append(f"[{DIM}]○ voice off[/{DIM}]")
        lines.append("")
        lines.append(f"[{DIM}]Tab   cycle[/{DIM}]")
        lines.append(f"[{DIM}]^V    voice[/{DIM}]")
        lines.append(f"[{DIM}]^C    quit[/{DIM}]")
        return "\n".join(lines)


# ── Status strip ──────────────────────────────────────────────────────────────

class StatusStrip(Static):
    status: reactive[str] = reactive("")

    def render(self) -> str:
        return f"[{DIM}]{self.status}[/{DIM}]" if self.status else ""


# ── App ───────────────────────────────────────────────────────────────────────

class BOWENApp(App):

    CSS = f"""
    Screen {{
        background: {BG};
    }}

    #sidebar {{
        width: 22;
        height: 1fr;
        background: {BG_PANEL};
        border-right: solid {BORDER};
        padding: 2 2;
        color: {CREAM};
    }}

    #main {{
        background: {BG};
        height: 1fr;
    }}

    #chat-log {{
        height: 1fr;
        background: {BG};
        border: none;
        padding: 1 3;
        color: {CREAM};
        scrollbar-color: {MUTED} {BG};
        scrollbar-size: 1 1;
    }}

    #input-row {{
        height: 3;
        background: {BG_PANEL};
        border-top: solid {BORDER};
        padding: 0 3;
        align: left middle;
    }}

    #prompt-label {{
        color: {TAN};
        width: 14;
        content-align: left middle;
    }}

    #chat-input {{
        background: {BG_PANEL};
        color: {CREAM};
        border: none;
        width: 1fr;
    }}

    #chat-input:focus {{
        border: none;
    }}

    #status-strip {{
        height: 1;
        background: {BG};
        padding: 0 3;
        color: {DIM};
    }}

    Footer {{
        display: none;
    }}
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", show=False),
        Binding("tab", "cycle_agent", show=False),
        Binding("ctrl+v", "toggle_voice", show=False),
        Binding("escape", "clear_input", show=False),
    ]

    active_agent: reactive[str] = reactive("BOWEN")
    voice_active: reactive[bool] = reactive(False)

    def __init__(self):
        super().__init__()
        self.config: Optional[Config] = None
        self.memory: Optional[MemoryStore] = None
        self.mem0: Optional[Mem0Layer] = None
        self.bus: Optional[MessageBus] = None
        self.agents: dict = {}
        self.session_id = str(uuid.uuid4())
        self._thinking = False
        self._voice = None   # VoicePipeline, set after boot

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield AgentPanel(id="sidebar")
            with Vertical(id="main"):
                yield RichLog(id="chat-log", highlight=False, markup=True, wrap=True)
                with Horizontal(id="input-row"):
                    yield Label("▸ BOWEN        ", id="prompt-label")
                    yield Input(placeholder="", id="chat-input")
        yield StatusStrip(id="status-strip")

    async def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()
        self._boot()

    # ── Boot sequence ─────────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _boot(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        strip = self.query_one("#status-strip", StatusStrip)

        def s(msg: str) -> None:
            strip.status = msg

        try:
            s("loading config")
            self.config = Config()
            missing = self.config.validate()
            if missing:
                log.write(f"[{ERR}]missing env vars: {', '.join(missing)}[/{ERR}]")
                return

            s("initializing memory")
            self.memory = MemoryStore(self.config.DB_PATH, self.config.CHROMA_PATH)
            self.memory.set_profile_path(self.config.PROFILE_PATH)
            await self.memory.initialize()

            # Mem0 — local LLM-powered memory (non-blocking init, falls back if Ollama down)
            s("connecting mem0")
            self.mem0 = Mem0Layer(user_id="praise")
            mem0_ok = await asyncio.to_thread(self.mem0.initialize)

            s("loading tools")
            registry.initialize(
                brave_api_key=self.config.BRAVE_API_KEY,
                google_credentials_path=self.config.GOOGLE_CREDENTIALS_PATH,
                google_token_path=self.config.GOOGLE_TOKEN_PATH,
                db_path=self.config.DB_PATH,
                user_timezone=self.config.USER_TIMEZONE,
                memory_store=self.memory,
            )

            self.bus = MessageBus()

            s("spinning up agents")
            self.agents = {
                "BOWEN":   BOWENAgent(self.config, self.memory, self.bus),
                "CAPTAIN": CaptainAgent(self.config, self.memory, self.bus),
                "SCOUT":   ScoutAgent(self.config, self.memory, self.bus),
                "TAMARA":  TamaraAgent(self.config, self.memory, self.bus),
                "HELEN":   HelenAgent(self.config, self.memory, self.bus),
            }
            for agent in self.agents.values():
                agent.set_session(self.session_id)

            # Voice pipeline — init in background, non-blocking
            s("initializing voice")
            await self._init_voice()

            # Tool status summary
            tools_status = _build_tools_status(self.config)
            mem0_note = "mem0 ✓" if mem0_ok else "mem0 offline"

            s(f"ready  ·  {self.session_id[:8]}  ·  {mem0_note}")

            log.write("")
            log.write(
                f"[bold {TAN}]BOWEN[/bold {TAN}]"
                f"[{DIM}]  ·  all systems online  ·  five agents standing by[/{DIM}]"
            )
            if tools_status:
                log.write(f"[{DIM}]       {tools_status}[/{DIM}]")
            log.write("")

        except Exception as e:
            import traceback
            log.write(f"[{ERR}]boot error: {e}[/{ERR}]")
            log.write(f"[{DIM}]{traceback.format_exc()}[/{DIM}]")
            s(f"failed: {e}")

    async def _init_voice(self) -> None:
        """Initialize voice pipeline. Non-blocking — voice works if available."""
        try:
            from voice.pipeline import VoicePipeline
            self._voice = VoicePipeline(
                config=self.config,
                agents=self.agents,
                on_transcript=self._on_voice_transcript,
                on_response=self._on_voice_response,
            )
            status = await asyncio.to_thread(self._voice.initialize)
            if status.get("stt") or status.get("tts"):
                log = self.query_one("#chat-log", RichLog)
                ready_parts = [k for k, v in status.items() if v and k != "active"]
                log.write(
                    f"[{DIM}]       voice: {', '.join(ready_parts)} ready"
                    f"  ·  Ctrl+V to activate[/{DIM}]"
                )
        except Exception as e:
            pass  # voice is optional — silently skip if unavailable

    # ── Voice callbacks (called from voice pipeline thread) ───────────────────

    def _on_voice_transcript(self, text: str, source: str) -> None:
        """Called when user speech is transcribed."""
        self.call_from_thread(self._show_voice_transcript, text)

    def _on_voice_response(self, text: str, agent_name: str) -> None:
        """Called when agent response is ready (after TTS spoke it)."""
        self.call_from_thread(self._show_voice_response, text, agent_name)

    def _show_voice_transcript(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M")
        log.write(f"[{DIM}]{ts}[/{DIM}]  [{CREAM}]you  {text}[/{CREAM}]")
        log.write("")
        log.scroll_end(animate=False)

    def _show_voice_response(self, text: str, agent_name: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M")
        lines = text.strip().split("\n")
        for i, line in enumerate(lines):
            if line.strip():
                if i == 0:
                    log.write(
                        f"[{DIM}]{ts}[/{DIM}]"
                        f"[bold {TAN}]  {agent_name.lower()}  [/bold {TAN}]"
                        f"[{CREAM}]{line}[/{CREAM}]"
                    )
                else:
                    pad = " " * (6 + 2 + len(agent_name) + 2)
                    log.write(f"[{CREAM}]{pad}{line}[/{CREAM}]")
        log.write("")
        log.scroll_end(animate=False)

    # ── Text input ────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        self.query_one("#chat-input", Input).clear()
        if not self.agents:
            self.query_one("#chat-log", RichLog).write(
                f"[{DIM}]still initializing...[/{DIM}]"
            )
            return
        if self._thinking:
            return
        self._send_message(text)

    @work(exclusive=False, thread=False)
    async def _send_message(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        strip = self.query_one("#status-strip", StatusStrip)
        self._thinking = True

        # Route
        agent_name = self.active_agent
        if agent_name == "BOWEN":
            try:
                agent_name = await self.agents["BOWEN"].route(text)
            except Exception:
                agent_name = "BOWEN"

        agent = self.agents.get(agent_name)
        if not agent:
            log.write(f"[{ERR}]agent {agent_name} not found[/{ERR}]")
            self._thinking = False
            return

        ts = datetime.now().strftime("%H:%M")
        log.write(
            f"[{DIM}]{ts}[/{DIM}]"
            f"[{CREAM}]  you  [/{CREAM}]"
            f"[{CREAM}]{text}[/{CREAM}]"
        )
        log.write("")

        strip.status = f"{agent_name.lower()}  ·  thinking"

        # Streaming buffer
        buf: list[str] = []
        all_chunks: list[str] = []   # accumulates every chunk for Mem0
        header_written = False
        conversation: list[dict] = [{"role": "user", "content": text}]

        async def send_chunk(data: dict) -> None:
            nonlocal header_written
            t = data.get("type")
            if t == "chunk":
                all_chunks.append(data["content"])
                buf.append(data["content"])
                full = "".join(buf)
                lines = full.split("\n")
                if len(lines) > 1:
                    for line in lines[:-1]:
                        _write_agent_line(log, agent_name, ts, line, header_written)
                        header_written = True
                    buf.clear()
                    buf.append(lines[-1])
            elif t == "tool_call":
                pending = "".join(buf).strip()
                if pending:
                    _write_agent_line(log, agent_name, ts, pending, header_written)
                    header_written = True
                buf.clear()
                log.write(f"   [{DIM}]⟳  {data['tool']}[/{DIM}]")
            elif t == "tool_result":
                icon = "✓" if data["status"] == "OK" else "✗"
                log.write(f"   [{DIM}]{icon}  {data['preview'][:100]}[/{DIM}]")
            elif t == "error":
                log.write(f"   [{ERR}]{data['content']}[/{ERR}]")

        try:
            await agent.respond(text, send=send_chunk)
            remaining = "".join(buf).strip()
            if remaining:
                _write_agent_line(log, agent_name, ts, remaining, header_written)

            # Drain inter-agent bus messages (e.g. SCOUT → CAPTAIN chains)
            if self.bus and self.bus.any_pending():
                depth = 0
                while self.bus.any_pending() and depth < 5:
                    pending_msgs = await self.bus.drain_all()
                    for bmsg in pending_msgs:
                        target = self.agents.get(bmsg.recipient)
                        if not target:
                            continue
                        log.write(f"   [{DIM}]⟳  {bmsg.sender} → {bmsg.recipient}[/{DIM}]")
                        try:
                            await target.handle(bmsg, send=send_chunk)
                        except Exception:
                            pass
                    depth += 1

            # Feed full response to Mem0 in background (non-blocking)
            full_response = "".join(all_chunks)
            if self.mem0 and self.mem0.ready and full_response:
                conversation.append({"role": "assistant", "content": full_response})
                asyncio.create_task(
                    asyncio.to_thread(self.mem0.add_conversation, conversation)
                )

            log.write("")
            log.scroll_end(animate=False)
            strip.status = f"ready  ·  {self.session_id[:8]}"
        except Exception as e:
            log.write(f"   [{ERR}]{e}[/{ERR}]")
            strip.status = f"error: {e}"
        finally:
            self._thinking = False

    # ── Actions ───────────────────────────────────────────────────────────────

    def watch_active_agent(self, name: str) -> None:
        self.query_one("#sidebar", AgentPanel).active_agent = name
        self.query_one("#prompt-label", Label).update(f"▸ {name:<12} ")

    def watch_voice_active(self, active: bool) -> None:
        self.query_one("#sidebar", AgentPanel).voice_active = active

    def action_cycle_agent(self) -> None:
        idx = AGENT_ORDER.index(self.active_agent)
        self.active_agent = AGENT_ORDER[(idx + 1) % len(AGENT_ORDER)]

    def action_clear_input(self) -> None:
        self.query_one("#chat-input", Input).clear()

    @work(exclusive=False, thread=False)
    async def action_toggle_voice(self) -> None:
        """Toggle voice pipeline on/off."""
        if not self._voice:
            log = self.query_one("#chat-log", RichLog)
            log.write(f"   [{DIM}]voice not available — check mic permissions and model files[/{DIM}]")
            return

        if self.voice_active:
            await self._voice.stop()
            self.voice_active = False
            self.query_one("#status-strip", StatusStrip).status = (
                f"voice off  ·  ready  ·  {self.session_id[:8]}"
            )
        else:
            await self._voice.start()
            self.voice_active = True
            self.query_one("#status-strip", StatusStrip).status = (
                f"◉ listening for wake word  ·  {self.session_id[:8]}"
            )

    async def action_quit(self) -> None:
        if self._voice and self.voice_active:
            await self._voice.stop()
        if self.memory:
            await self.memory.close()
        self.exit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_agent_line(
    log: RichLog,
    agent_name: str,
    ts: str,
    line: str,
    continuation: bool,
) -> None:
    if not continuation:
        log.write(
            f"[{DIM}]{ts}[/{DIM}]"
            f"[bold {TAN}]  {agent_name.lower()}  [/bold {TAN}]"
            f"[{CREAM}]{line}[/{CREAM}]"
        )
    else:
        pad = " " * (6 + 2 + len(agent_name) + 2)
        log.write(f"[{CREAM}]{pad}{line}[/{CREAM}]")


def _build_tools_status(config: Config) -> str:
    """Show which tool integrations are active."""
    parts = []
    if config.BRAVE_API_KEY:
        parts.append("search ✓")
    if config.GOOGLE_CREDENTIALS_PATH.exists():
        parts.append("google ✓")
    else:
        parts.append("google ✗ (run: python tools/google_auth.py)")
    if config.GROQ_API_KEY:
        parts.append("stt ✓")
    return "  ·  ".join(parts) if parts else ""


if __name__ == "__main__":
    BOWENApp().run()
