"""
tui.py — BOWEN Terminal Interface (WebSocket client).
Connects to main.py FastAPI backend at ws://localhost:8000/ws/chat.
No agent or memory imports — pure display + input layer.

Start backend first:
    uvicorn main:app --host 0.0.0.0 --port 8000

Then run TUI:
    .venv/bin/python3 tui.py

Or use start.sh which handles both.

Shortcuts:
  Enter       — send message
  Tab         — cycle active agent (forces routing to that agent)
  Ctrl+V      — toggle voice mode
  Escape      — clear input
  Ctrl+C      — quit
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

import httpx
import websockets
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, RichLog, Static
from textual import work

# ── Palette ───────────────────────────────────────────────────────────────────

BG        = "#0a0a0a"
BG_PANEL  = "#0f0f0f"
BORDER    = "#1e1e1e"
TAN       = "#c8b89a"
CREAM     = "#f5f2ee"
DIM       = "#4a4540"
MUTED     = "#2a2520"
ERR       = "#c0705a"
GREEN     = "#8ab89a"

BACKEND_URL  = "http://localhost:8000"
HEALTH_URL   = f"{BACKEND_URL}/api/health"

def _ws_url() -> str:
    """Build WebSocket URL with API key from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("ADMIN_API_KEY", "")
    base = "ws://localhost:8000/ws/chat"
    return f"{base}?key={key}" if key else base

AGENT_ORDER = ["BOWEN", "CAPTAIN", "DEVOPS", "SCOUT", "TAMARA", "HELEN"]

AGENT_ROLE = {
    "BOWEN":   "Orchestrator",
    "CAPTAIN": "Code & Builds",
    "DEVOPS":  "Review & Audit",
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
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._conversation_id: Optional[str] = None
        self._thinking = False
        self._voice = None
        self._voice_chunks: list[str] = []  # accumulates chunks for TTS

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

    # ── Boot ──────────────────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _boot(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        strip = self.query_one("#status-strip", StatusStrip)

        def s(msg: str) -> None:
            strip.status = msg

        s("checking backend")

        # Check backend health
        backend_ok = await self._check_backend()
        if not backend_ok:
            log.write(f"[{ERR}]backend not running[/{ERR}]")
            log.write(f"[{DIM}]start it with:[/{DIM}]")
            log.write(f"[{TAN}]  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000[/{TAN}]")
            log.write("")
            log.write(f"[{DIM}]or use: bash start.sh[/{DIM}]")
            s("backend offline — see instructions above")
            return

        # Connect WebSocket
        s("connecting to backend")
        connected = await self._connect_ws()
        if not connected:
            log.write(f"[{ERR}]WebSocket connection failed[/{ERR}]")
            s("connection failed")
            return

        # Init voice
        s("initializing voice")
        await self._init_voice()

        # Done
        log.write("")
        log.write(
            f"[bold {TAN}]BOWEN[/bold {TAN}]"
            f"[{DIM}]  ·  connected to backend  ·  five agents standing by[/{DIM}]"
        )
        log.write("")
        s(f"ready  ·  {self._conversation_id[:8] if self._conversation_id else 'connecting'}")

    async def _check_backend(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(HEALTH_URL)
                return r.status_code == 200
        except Exception:
            return False

    async def _connect_ws(self) -> bool:
        try:
            self._ws = await websockets.connect(
                _ws_url(),
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            # Start background receive loop
            asyncio.create_task(self._ws_receive_loop())
            return True
        except Exception as e:
            return False

    async def _ws_receive_loop(self) -> None:
        """
        Background task — receives all messages from backend and routes to UI.
        Runs until WebSocket closes.
        """
        log = self.query_one("#chat-log", RichLog)
        strip = self.query_one("#status-strip", StatusStrip)

        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                t = data.get("type")

                if t == "auth_ok":
                    pass  # connection established — boot() already handles the welcome message

                elif t == "conversation_created":
                    self._conversation_id = data.get("conversation_id", "")
                    strip.status = f"ready  ·  {self._conversation_id[:8]}"

                elif t == "routing":
                    to = data.get("to", "")
                    if to and to != "user":
                        # Update active agent display to match where message routed
                        self.active_agent = to

                elif t == "chunk":
                    content = data.get("content", "")
                    if content:
                        self._stream_chunk(content)
                        self._voice_chunks.append(content)

                elif t == "tool_call":
                    self._flush_stream()
                    log.write(f"   [{DIM}]⟳  {data.get('tool', '')}[/{DIM}]")
                    log.scroll_end(animate=False)

                elif t == "tool_result":
                    icon = "✓" if data.get("status") == "OK" else "✗"
                    log.write(f"   [{DIM}]{icon}  {data.get('preview', '')[:100]}[/{DIM}]")
                    log.scroll_end(animate=False)

                elif t == "error":
                    self._flush_stream()
                    log.write(f"   [{ERR}]{data.get('message', 'error')}[/{ERR}]")
                    log.scroll_end(animate=False)

                elif t == "done":
                    self._flush_stream()
                    log.write("")
                    log.scroll_end(animate=False)
                    self._thinking = False
                    strip.status = f"ready  ·  {(self._conversation_id or '')[:8]}"

                    # Speak full response via TTS if voice is active
                    if self.voice_active and self._voice and self._voice_chunks:
                        full = "".join(self._voice_chunks)
                        if full.strip():
                            asyncio.create_task(self._speak(full))
                    self._voice_chunks.clear()

                elif t == "pong":
                    pass

        except websockets.ConnectionClosed:
            log.write(f"[{ERR}]backend disconnected[/{ERR}]")
            strip.status = "disconnected — restart with: bash start.sh"
            self._thinking = False
        except Exception as e:
            log.write(f"[{ERR}]ws error: {e}[/{ERR}]")
            self._thinking = False

    # ── Stream rendering ──────────────────────────────────────────────────────

    _stream_buf: list[str] = []
    _stream_agent: str = ""
    _stream_ts: str = ""
    _stream_header_written: bool = False

    def _stream_chunk(self, content: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        self._stream_buf.append(content)
        full = "".join(self._stream_buf)
        lines = full.split("\n")
        if len(lines) > 1:
            for line in lines[:-1]:
                _write_agent_line(log, self._stream_agent, self._stream_ts, line, self._stream_header_written)
                self._stream_header_written = True
            self._stream_buf = [lines[-1]]
            log.scroll_end(animate=False)

    def _flush_stream(self) -> None:
        if not self._stream_buf:
            return
        log = self.query_one("#chat-log", RichLog)
        remaining = "".join(self._stream_buf).strip()
        if remaining:
            _write_agent_line(log, self._stream_agent, self._stream_ts, remaining, self._stream_header_written)
            log.scroll_end(animate=False)
        self._stream_buf = []
        self._stream_header_written = False

    # ── Text input ────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._thinking:
            return
        self.query_one("#chat-input", Input).clear()
        if not self._ws:
            self.query_one("#chat-log", RichLog).write(
                f"[{ERR}]not connected to backend[/{ERR}]"
            )
            return
        await self._send(text)

    async def _send(self, text: str, target_agent: str = "") -> None:
        log = self.query_one("#chat-log", RichLog)
        strip = self.query_one("#status-strip", StatusStrip)

        if not self._ws:
            return

        self._thinking = True
        self._voice_chunks.clear()

        # Determine target — if user manually selected an agent via Tab, honour it
        agent = target_agent or (self.active_agent if self.active_agent != "BOWEN" else "")

        ts = datetime.now().strftime("%H:%M")
        log.write(
            f"[{DIM}]{ts}[/{DIM}]"
            f"[{CREAM}]  you  [/{CREAM}]"
            f"[{CREAM}]{text}[/{CREAM}]"
        )
        log.write("")

        # Reset stream state
        self._stream_buf = []
        self._stream_agent = agent or "BOWEN"
        self._stream_ts = ts
        self._stream_header_written = False

        strip.status = f"{(agent or 'bowen').lower()}  ·  thinking"

        # Build payload
        payload: dict = {"type": "message", "content": text}
        if self._conversation_id:
            payload["conversation_id"] = self._conversation_id
        if agent and agent != "BOWEN":
            payload["target_agent"] = agent

        try:
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            log.write(f"   [{ERR}]send failed: {e}[/{ERR}]")
            self._thinking = False

    # ── Voice ─────────────────────────────────────────────────────────────────

    async def _init_voice(self) -> None:
        try:
            from config import Config
            from voice.pipeline import VoicePipeline
            config = Config()
            self._voice = VoicePipeline(
                config=config,
                agents={},  # voice routes through WebSocket, not direct agent calls
                on_transcript=self._on_voice_transcript,
                on_response=None,  # response comes back via WS chunks
            )
            # Override pipeline's agent routing to go through WebSocket
            self._voice._ws_send = self._send_voice_transcript

            status = await asyncio.to_thread(self._voice.initialize)
            log = self.query_one("#chat-log", RichLog)
            if status.get("stt") or status.get("tts"):
                ready_parts = [k for k, v in status.items() if v and k != "active"]
                log.write(
                    f"[{DIM}]       voice: {', '.join(ready_parts)} ready"
                    f"  ·  Ctrl+V to activate[/{DIM}]"
                )
        except Exception:
            pass

    async def _speak(self, text: str) -> None:
        if self._voice and self._voice.tts.ready:
            await self._voice.tts.speak_streaming(text)

    def _on_voice_transcript(self, text: str, source: str) -> None:
        self.call_from_thread(self._show_voice_transcript, text)

    def _show_voice_transcript(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        ts = datetime.now().strftime("%H:%M")
        log.write(f"[{DIM}]{ts}[/{DIM}]  [{CREAM}]you  {text}[/{CREAM}]")
        log.write("")
        log.scroll_end(animate=False)
        # WS send is handled by pipeline._ws_send — do not duplicate here

    async def _send_voice_transcript(self, text: str) -> None:
        await self._send(text)

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
        if not self._voice:
            log = self.query_one("#chat-log", RichLog)
            log.write(f"   [{DIM}]voice not available[/{DIM}]")
            return

        if self.voice_active:
            await self._voice.stop()
            self.voice_active = False
            self.query_one("#status-strip", StatusStrip).status = (
                f"voice off  ·  ready  ·  {(self._conversation_id or '')[:8]}"
            )
        else:
            await self._voice.start()
            self.voice_active = True
            self.query_one("#status-strip", StatusStrip).status = (
                f"◉ listening  ·  {(self._conversation_id or '')[:8]}"
            )

    async def action_quit(self) -> None:
        if self._voice and self.voice_active:
            await self._voice.stop()
        if self._ws:
            await self._ws.close()
        self.exit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_agent_line(
    log: RichLog,
    agent_name: str,
    ts: str,
    line: str,
    continuation: bool,
) -> None:
    if not line.strip():
        return
    if not continuation:
        log.write(
            f"[{DIM}]{ts}[/{DIM}]"
            f"[bold {TAN}]  {agent_name.lower()}  [/bold {TAN}]"
            f"[{CREAM}]{line}[/{CREAM}]"
        )
    else:
        pad = " " * (6 + 2 + len(agent_name) + 2)
        log.write(f"[{CREAM}]{pad}{line}[/{CREAM}]")


if __name__ == "__main__":
    BOWENApp().run()
