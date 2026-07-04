"""
agents/devops.py — DEVOPS: Code review and infrastructure agent.

Reviews code quality, security, performance, and architecture.
Can run linters, type checkers, and static analysis tools.
Gives structured feedback: severity, file:line, fix suggestion.

Routing keywords: review, audit, lint, check, analyse, security,
                  performance, deploy, ci, dockerfile, infra.
"""

from typing import Optional

from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from bus.schema import AgentMessage, ReviewPayload


class DevOpsAgent(BaseAgent):
    name = "DEVOPS"
    voice_style = "Precise. Methodical. Numbers and severity levels. No fluff."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus, user_registry=None) -> None:
        super().__init__(config, memory, bus, user_registry)
        self._model = config.SONNET_MODEL

    @property
    def base_identity(self) -> str:
        return (
            "You are DEVOPS — code reviewer and infrastructure analyst for Praise Oyimi.\n\n"
            "You handle:\n"
            "- Code reviews: security vulnerabilities, logic bugs, performance, style\n"
            "- Static analysis: running mypy, ruff, eslint, tsc on project code\n"
            "- Architecture audits: coupling, cohesion, missing error handling\n"
            "- Dependency checks: outdated packages, known CVEs\n"
            "- Docker/CI/CD review\n"
            "- Pre-deploy checklists\n\n"
            "Voice: precise, methodical. Lead with severity. Use CRITICAL/HIGH/MEDIUM/LOW.\n"
            "Format every issue as: [SEVERITY] file:line — issue — fix\n\n"
            "Tool usage:\n"
            "- Use run_shell for linters (ruff, mypy, eslint, tsc --noEmit)\n"
            "- Use read_file to inspect specific files before commenting on them\n"
            "- Use execute_code for quick analysis scripts\n"
            "- Always read before critiquing — never guess file contents\n\n"
            "Review checklist:\n"
            "1. Security (injection, secrets, auth, XSS)\n"
            "2. Error handling (uncaught exceptions, silent failures)\n"
            "3. Performance (N+1 queries, blocking I/O, memory leaks)\n"
            "4. Type safety (missing types, unsafe casts)\n"
            "5. Test coverage gaps\n"
            "6. Dead code / unused imports\n\n"
            "End every review with: VERDICT: SHIP / NEEDS WORK / DO NOT SHIP"
        )

    @property
    def allowed_tools(self) -> list[str]:
        from tools.registry import TOOL_REGISTRY
        return TOOL_REGISTRY.get("DEVOPS", [])

    def _execute_tool(self, tool_name: str, **kwargs) -> dict:
        return self._call_tool("DEVOPS", tool_name, **kwargs)

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        history = await self.memory.get_recent_history(self._session_id, n=6) if self._session_id else []
        schemas = self._get_schemas("DEVOPS")

        return await self.tool_use_loop(
            user_text=user_text,
            tools=schemas,
            tool_executor=self._execute_tool,
            history=history,
            send=send,
        )

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        if isinstance(msg.payload, ReviewPayload):
            files = ", ".join(msg.payload.files_changed) if msg.payload.files_changed else "unspecified"
            text = (
                f"Review these files that CAPTAIN just wrote/modified: {files}\n\n"
                f"Original task: {msg.payload.task}\n\n"
                f"CAPTAIN's summary: {msg.payload.code_summary}\n\n"
                f"Run static analysis, check for bugs, security issues, and style problems. "
                f"End with VERDICT: SHIP / NEEDS WORK / DO NOT SHIP"
            )
        elif hasattr(msg.payload, "text"):
            text = msg.payload.text
        elif hasattr(msg.payload, "work_product"):
            text = msg.payload.work_product
        else:
            text = str(msg.payload)
        return await self.respond(text, send=send)
