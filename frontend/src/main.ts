/**
 * main.ts — BOWEN browser UI entry point.
 *
 * Wires together:
 *  - BowenWS (WebSocket client with auto-reconnect)
 *  - Orb (Three.js particle orb, state-driven)
 *  - UI helpers (chat rendering, tool cards, modals)
 *  - Voice input (Web Speech API)
 */

import './style.css'
import { BowenWS } from './ws'
import { Orb } from './orb'
import * as ui from './ui'
import type { OrbState, ToolActivity } from './types'

// ── Constants ─────────────────────────────────────────────────────────────────

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat`

// ── State ─────────────────────────────────────────────────────────────────────

let selectedAgent: string | null = null   // null = let BOWEN route
let orbState: OrbState = 'idle'
const pendingPlanningQuestions: string[] = []
let toolCallCounter = 0   // per-turn counter for unique tool card IDs

// ── Init ──────────────────────────────────────────────────────────────────────

const canvas = document.getElementById('orb-canvas') as HTMLCanvasElement
const orb = new Orb(canvas)
const ws = new BowenWS(WS_URL)

function setOrbState(state: OrbState): void {
  orbState = state
  orb.setOrbState(state)
  ui.setOrbStateLabel(state)
}

// Resize orb to fill left panel
function resizeOrb(): void {
  const leftPanel = document.getElementById('left-panel')!
  const w = leftPanel.clientWidth
  const h = leftPanel.clientHeight
  canvas.style.width = `${w}px`
  canvas.style.height = `${h}px`
  orb.resize(w, h)
}
window.addEventListener('resize', resizeOrb)
resizeOrb()

// ── WebSocket events ──────────────────────────────────────────────────────────

ws.on('open', () => {
  ui.setConnectionState(true)
  setOrbState('idle')
})

ws.on('close', () => {
  ui.setConnectionState(false)
})

ws.on('message', (msg) => {
  switch (msg.type) {
    case 'routing':
      setOrbState('thinking')
      ui.setActiveAgent(msg.to)
      ui.addSystemMessage(`→ ${msg.to}`)
      break

    case 'chunk':
      if (orbState !== 'speaking') setOrbState('speaking')
      ui.appendChunk(msg.content)
      break

    case 'tool_call': {
      setOrbState('working')
      // Unique ID per call — same tool can be called multiple times in one turn
      const actId = `${msg.tool}-${msg.agent}-${++toolCallCounter}`
      const activity: ToolActivity = {
        id: actId,
        tool: msg.tool,
        args: msg.args,
        status: 'running',
      }
      ui.addToolCall(activity)
      // Store latest ID for this tool so result can find it
      ui.setLastToolId(msg.tool, msg.agent, actId)
      break
    }

    case 'tool_result': {
      setOrbState('working')
      const resultId = ui.getLastToolId(msg.tool, msg.agent)
      if (resultId) ui.updateToolResult(resultId, msg.status, msg.preview)
      break
    }

    case 'done':
      setOrbState('idle')
      ui.finalizeAssistantMessage()
      toolCallCounter = 0   // reset for next turn
      break

    case 'error':
      setOrbState('idle')
      ui.showError(msg.message)
      ui.finalizeAssistantMessage()
      break

    case 'planning_start':
      setOrbState('thinking')
      pendingPlanningQuestions.length = 0
      break

    case 'planning_question':
      pendingPlanningQuestions.push(msg.question)
      break

    case 'planning_end':
      if (pendingPlanningQuestions.length > 0) {
        const questions = [...pendingPlanningQuestions]
        pendingPlanningQuestions.length = 0
        ui.showPlanningModal(
          questions,
          (answers) => {
            // Send each answer (may be empty string if user skipped)
            answers.forEach(({ question, answer }) => {
              ws.send({ type: 'planning_answer', question, answer })
            })
          },
          () => {
            // User skipped — send empty answers so backend doesn't hang
            questions.forEach((q) => {
              ws.send({ type: 'planning_answer', question: q, answer: '' })
            })
          },
        )
      }
      break

    case 'approval_required':
      ui.showApprovalModal(
        `${msg.from} → ${msg.to}: ${msg.description}`,
        (approved) => {
          ws.send({ type: 'approval_response', correlation_id: msg.correlation_id, approved })
        },
      )
      break
  }
})

ws.connect()

// ── Send message ──────────────────────────────────────────────────────────────

const input = document.getElementById('chat-input') as HTMLTextAreaElement
const sendBtn = document.getElementById('send-btn') as HTMLButtonElement

function sendMessage(): void {
  const text = input.value.trim()
  if (!text || !ws.connected) return

  ui.startAssistantMessage(selectedAgent ?? 'BOWEN')
  ui.addUserMessage(text, 'user')
  setOrbState('thinking')

  ws.sendMessage(text, selectedAgent ?? undefined)

  input.value = ''
  input.style.height = 'auto'
}

sendBtn.addEventListener('click', sendMessage)

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
})

// Auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`
})

// ── Agent selector ────────────────────────────────────────────────────────────

document.querySelectorAll<HTMLButtonElement>('.agent-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const agent = btn.dataset['agent'] ?? null
    selectedAgent = agent === 'BOWEN' ? null : agent
    ui.setActiveAgent(agent ?? 'BOWEN')
    input.placeholder = agent === 'BOWEN' ? 'Talk to BOWEN...' : `Talk to ${agent}...`
  })
})

// ── Voice input (Web Speech API) ──────────────────────────────────────────────

const voiceBtn = document.getElementById('voice-btn') as HTMLButtonElement

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SpeechRecognitionClass: any =
  (window as unknown as Record<string, unknown>)['SpeechRecognition'] ||
  (window as unknown as Record<string, unknown>)['webkitSpeechRecognition']

if (SpeechRecognitionClass) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognition: any = new SpeechRecognitionClass()
  recognition.lang = 'en-US'
  recognition.interimResults = false
  recognition.maxAlternatives = 1

  let listening = false

  voiceBtn.addEventListener('click', () => {
    if (listening) {
      recognition.stop()
      return
    }
    recognition.start()
    setOrbState('listening')
    voiceBtn.classList.add('active')
    listening = true
  })

  recognition.onresult = (e: { results: { [n: number]: { [n: number]: { transcript: string } } } }) => {
    const transcript = e.results[0]?.[0]?.transcript ?? ''
    if (transcript) {
      input.value = transcript
      input.dispatchEvent(new Event('input'))
    }
  }

  recognition.onend = () => {
    listening = false
    voiceBtn.classList.remove('active')
    if (orbState === 'listening') setOrbState('idle')
  }

  recognition.onerror = () => {
    listening = false
    voiceBtn.classList.remove('active')
    if (orbState === 'listening') setOrbState('idle')
  }
} else {
  voiceBtn.title = 'Voice input not supported in this browser'
  voiceBtn.style.opacity = '0.3'
  voiceBtn.style.cursor = 'not-allowed'
}

// Clear tool activity panel on each new outbound message
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) ui.clearToolActivity()
})
sendBtn.addEventListener('click', () => ui.clearToolActivity())
