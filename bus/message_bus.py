"""
bus/message_bus.py — Per-agent asyncio.PriorityQueue message bus.
Each agent gets its own queue. BOWEN reads from all queues.
"""

import asyncio
from typing import Optional
from .schema import AgentMessage

AGENT_NAMES = ["BOWEN", "CAPTAIN", "SCOUT", "TAMARA", "HELEN"]


class MessageBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.PriorityQueue] = {
            name: asyncio.PriorityQueue() for name in AGENT_NAMES
        }
        self._message_log: list[AgentMessage] = []

    async def send(self, msg: AgentMessage) -> None:
        """Send a message to the recipient's queue."""
        if msg.recipient == "broadcast":
            for name in AGENT_NAMES:
                if name != msg.sender:
                    await self._queues[name].put(msg)
        elif msg.recipient in self._queues:
            await self._queues[msg.recipient].put(msg)
            self._message_log.append(msg)
        else:
            raise ValueError(f"Unknown recipient: {msg.recipient}")

    async def receive(self, agent_name: str, timeout: float = 0.1) -> Optional[AgentMessage]:
        """Non-blocking receive from an agent's queue. Returns None if empty."""
        try:
            return await asyncio.wait_for(
                self._queues[agent_name].get(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    def empty(self, agent_name: str) -> bool:
        return self._queues[agent_name].empty()

    def any_pending(self) -> bool:
        return any(not q.empty() for q in self._queues.values())

    async def drain_all(self) -> list[AgentMessage]:
        """Collect all pending messages across all queues."""
        messages = []
        for name in AGENT_NAMES:
            while not self._queues[name].empty():
                msg = await self._queues[name].get()
                messages.append(msg)
        return messages

    @property
    def log(self) -> list[AgentMessage]:
        return self._message_log.copy()
