/**
 * ui.ts — DOM helpers for BOWEN chat UI.
 * Handles message rendering, tool cards, planning modal, approval modal, voice input.
 */

import type { ChatMessage, ToolActivity, OrbState } from './types'

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T

// ── DOM refs ──────────────────────────────────────────────────────────────────

const chatMessages = $<HTMLDivElement>('chat-messages')
const toolActivity = $<HTMLDivElement>('tool-activity')
const agentStateLabel = $<HTMLDivElement>('agent-state-label')
const activeAgentLabel = $<HTMLSpanElement>('active-agent-label')
const connectionDot = $<HTMLSpanElement>('connection-dot')
const planningModal = $<HTMLDivElement>('planning-modal')
const planningQuestionsEl = $<HTMLDivElement>('planning-questions')
const approvalModal = $<HTMLDivElement>('approval-modal')
const approvalContent = $<HTMLDivElement>('approval-content')

// ── State labels ──────────────────────────────────────────────────────────────

const STATE_LABELS: Record<OrbState, string> = {
  idle: 'READY',
  listening: 'LISTENING',
  thinking: 'ROUTING',
  speaking: 'SPEAKING',
  working: 'WORKING',
}

export function setOrbStateLabel(state: OrbState): void {
  agentStateLabel.textContent = STATE_LABELS[state]
  agentStateLabel.className = `state-${state}`
}

export function setActiveAgent(agent: string): void {
  activeAgentLabel.textContent = agent
  document.querySelectorAll<HTMLButtonElement>('.agent-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset['agent'] === agent)
  })
}

export function setConnectionState(connected: boolean): void {
  connectionDot.className = `dot ${connected ? 'connected' : 'disconnected'}`
  connectionDot.title = connected ? 'Connected' : 'Reconnecting...'
}

// ── Chat messages ─────────────────────────────────────────────────────────────

let currentAssistantEl: HTMLDivElement | null = null

export function addUserMessage(content: string, _agent: string): ChatMessage {
  const id = crypto.randomUUID()
  const el = document.createElement('div')
  el.className = 'message user'
  el.id = `msg-${id}`
  el.innerHTML = `<div class="msg-bubble">${escHtml(content)}</div>`
  chatMessages.appendChild(el)
  scrollToBottom()
  return { id, role: 'user', agent: 'user', content, timestamp: Date.now() }
}

export function startAssistantMessage(agent: string): string {
  const id = crypto.randomUUID()
  const el = document.createElement('div')
  el.className = 'message assistant'
  el.id = `msg-${id}`
  el.innerHTML = `
    <div class="msg-agent">${escHtml(agent)}</div>
    <div class="msg-bubble" id="bubble-${id}"></div>
  `
  chatMessages.appendChild(el)
  currentAssistantEl = el.querySelector(`#bubble-${id}`)
  scrollToBottom()
  return id
}

export function appendChunk(chunk: string): void {
  if (!currentAssistantEl) return
  // Render markdown-lite: newlines → <br>, code blocks preserved
  currentAssistantEl.innerHTML = renderMarkdownLite(
    (currentAssistantEl.dataset['raw'] ?? '') + chunk,
  )
  currentAssistantEl.dataset['raw'] = (currentAssistantEl.dataset['raw'] ?? '') + chunk
  scrollToBottom()
}

export function finalizeAssistantMessage(): void {
  currentAssistantEl = null
}

// ── Tool activity ─────────────────────────────────────────────────────────────

const activeTools = new Map<string, HTMLDivElement>()
// Maps "tool-agent" → latest card ID — updated on each tool_call event
const lastToolId = new Map<string, string>()

export function setLastToolId(tool: string, agent: string, id: string): void {
  lastToolId.set(`${tool}-${agent}`, id)
}

export function getLastToolId(tool: string, agent: string): string | undefined {
  return lastToolId.get(`${tool}-${agent}`)
}

export function addToolCall(activity: ToolActivity): void {
  toolActivity.classList.remove('hidden')
  const el = document.createElement('div')
  el.className = 'tool-card running'
  el.id = `tool-${activity.id}`
  el.innerHTML = `
    <span class="tool-name">${escHtml(activity.tool)}</span>
    <span class="tool-args">${escHtml(JSON.stringify(activity.args)).slice(0, 80)}</span>
    <span class="tool-status">running</span>
  `
  toolActivity.appendChild(el)
  activeTools.set(activity.id, el)
  scrollToBottom()
}

export function updateToolResult(id: string, status: string, preview: string): void {
  const el = activeTools.get(id)
  if (!el) return
  el.className = `tool-card ${status === 'OK' ? 'ok' : 'error'}`
  const statusEl = el.querySelector('.tool-status')
  if (statusEl) statusEl.textContent = `${status}: ${preview.slice(0, 60)}`
}

export function clearToolActivity(): void {
  toolActivity.innerHTML = ''
  toolActivity.classList.add('hidden')
  activeTools.clear()
  lastToolId.clear()
}

// ── Planning modal ────────────────────────────────────────────────────────────

export function showPlanningModal(
  questions: string[],
  onSubmit: (answers: { question: string; answer: string }[]) => void,
  onSkip?: () => void,
): void {
  planningQuestionsEl.innerHTML = ''

  questions.forEach((q) => {
    const item = document.createElement('div')
    item.className = 'planning-item'
    item.innerHTML = `
      <label>${escHtml(q)}</label>
      <input type="text" class="planning-answer" placeholder="Your answer..." data-question="${escHtml(q)}" />
    `
    planningQuestionsEl.appendChild(item)
  })

  planningModal.classList.remove('hidden')
  ;(planningQuestionsEl.querySelector('input') as HTMLInputElement)?.focus()

  const submit = $<HTMLButtonElement>('planning-submit')
  const skip = $<HTMLButtonElement>('planning-skip')

  const submitHandler = () => {
    const answers = Array.from(
      planningQuestionsEl.querySelectorAll<HTMLInputElement>('.planning-answer'),
    ).map((inp) => ({ question: inp.dataset['question'] ?? '', answer: inp.value.trim() }))
    planningModal.classList.add('hidden')
    submit.removeEventListener('click', submitHandler)
    skip.removeEventListener('click', skipHandler)
    onSubmit(answers)
  }

  const skipHandler = () => {
    planningModal.classList.add('hidden')
    submit.removeEventListener('click', submitHandler)
    skip.removeEventListener('click', skipHandler)
    onSkip?.()
  }

  submit.addEventListener('click', submitHandler)
  skip.addEventListener('click', skipHandler)
}

export function hidePlanningModal(): void {
  planningModal.classList.add('hidden')
}

// ── Approval modal ────────────────────────────────────────────────────────────

export function showApprovalModal(
  description: string,
  onDecide: (approved: boolean) => void,
): void {
  approvalContent.textContent = description
  approvalModal.classList.remove('hidden')

  const approveBtn = $<HTMLButtonElement>('approval-approve')
  const denyBtn = $<HTMLButtonElement>('approval-deny')

  const decide = (approved: boolean) => () => {
    approvalModal.classList.add('hidden')
    approveBtn.removeEventListener('click', approveH)
    denyBtn.removeEventListener('click', denyH)
    onDecide(approved)
  }
  const approveH = decide(true)
  const denyH = decide(false)

  approveBtn.addEventListener('click', approveH)
  denyBtn.addEventListener('click', denyH)
}

// ── System messages ───────────────────────────────────────────────────────────

export function addSystemMessage(text: string): void {
  const el = document.createElement('div')
  el.className = 'message system'
  el.textContent = text
  chatMessages.appendChild(el)
  scrollToBottom()
}

// ── Error banner ──────────────────────────────────────────────────────────────

export function showError(msg: string): void {
  const el = document.createElement('div')
  el.className = 'message error'
  el.textContent = msg
  chatMessages.appendChild(el)
  scrollToBottom()
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function scrollToBottom(): void {
  chatMessages.scrollTop = chatMessages.scrollHeight
}

function escHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMarkdownLite(text: string): string {
  // Fenced code blocks — escape HTML inside (already done by regex capture)
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code: string) => {
    return `<pre><code class="lang-${lang}">${escHtml(code)}</code></pre>`
  })
  // Inline code — escape HTML inside backticks to prevent XSS
  text = text.replace(/`([^`]+)`/g, (_, code: string) => `<code>${escHtml(code)}</code>`)
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Newlines
  text = text.replace(/\n/g, '<br>')
  return text
}
