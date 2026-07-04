/**
 * main.ts — BOWEN browser UI entry point.
 *
 * Voice-first interface: tap the orb to speak, chat panel is a slide-in drawer.
 *
 * Wires together:
 *  - BowenWS (WebSocket client with auto-reconnect)
 *  - Orb (Three.js particle orb, state + amplitude driven)
 *  - UI helpers (chat rendering, tool cards, modals)
 *  - Web Audio API (mic amplitude → orb reactivity)
 *  - Web Speech API (voice input via orb tap)
 */

import './style.css'
import { BowenWS } from './ws'
import { Orb } from './orb'
import * as ui from './ui'
import type { OrbState, ToolActivity } from './types'

// ── Constants ─────────────────────────────────────────────────────────────────

// Tenant key: ?key=... in the URL (stored for next visits) or a prior visit's stored key.
const _urlKey = new URLSearchParams(location.search).get('key') || ''
if (_urlKey) localStorage.setItem('bowen_key', _urlKey)
const _key = _urlKey || localStorage.getItem('bowen_key') || ''
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat${_key ? `?key=${encodeURIComponent(_key)}` : ''}`

// ── State ─────────────────────────────────────────────────────────────────────

let orbState: OrbState = 'idle'
const pendingPlanningQuestions: string[] = []
let toolCallCounter = 0
let ttsBuffer = ''

// ── Init ──────────────────────────────────────────────────────────────────────

const canvas = document.getElementById('orb-canvas') as HTMLCanvasElement
const orb = new Orb(canvas)
const ws = new BowenWS(WS_URL)

const voiceMode   = document.getElementById('voice-mode')!
const systemPulse = document.getElementById('system-pulse')!
const micBarFill  = document.getElementById('mic-bar-fill') as HTMLDivElement

function setOrbState(state: OrbState): void {
  orbState = state
  orb.setOrbState(state)
  ui.setOrbStateLabel(state)
  voiceMode.className = `orb-${state}`
  systemPulse.classList.toggle('active', state !== 'idle')
}

// Resize orb to fill full viewport
function resizeOrb(): void {
  orb.resize(window.innerWidth, window.innerHeight)
}
window.addEventListener('resize', resizeOrb)
resizeOrb()

// ── TTS (stub — Phase A: Kokoro ONNX) ────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function ttsSpeak(_text: string): void {
  // Kokoro TTS integration — Phase A
}

// ── Web Audio: mic amplitude ──────────────────────────────────────────────────

let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null
let micStream: MediaStream | null = null
let micData: Uint8Array<ArrayBuffer> | null = null
let micRafId = 0

async function startMicAmplitude(): Promise<void> {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    audioCtx = new AudioContext()
    analyser = audioCtx.createAnalyser()
    analyser.fftSize = 256
    micData = new Uint8Array(analyser.frequencyBinCount) as Uint8Array<ArrayBuffer>
    audioCtx.createMediaStreamSource(micStream).connect(analyser)

    const tick = () => {
      micRafId = requestAnimationFrame(tick)
      if (!analyser || !micData) return
      analyser.getByteFrequencyData(micData)
      const avg = micData.reduce((a, b) => a + b, 0) / micData.length
      const level = Math.min(1, avg / 80)
      orb.setAmplitude(level)
      micBarFill.style.width = `${Math.round(level * 100)}%`
    }
    tick()
  } catch {
    // Mic not available — silent degradation
  }
}

function stopMicAmplitude(): void {
  cancelAnimationFrame(micRafId)
  micStream?.getTracks().forEach(t => t.stop())
  micStream = null
  audioCtx?.close()
  audioCtx = null
  analyser = null
  micData = null
  orb.setAmplitude(0)
  micBarFill.style.width = '0%'
}

// ── Voice input (Web Speech API — triggered by orb tap) ───────────────────────

const orbTap = document.getElementById('orb-tap') as HTMLDivElement

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SpeechRecognitionClass: any =
  (window as unknown as Record<string, unknown>)['SpeechRecognition'] ||
  (window as unknown as Record<string, unknown>)['webkitSpeechRecognition']

let speechListening = false

if (SpeechRecognitionClass) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognition: any = new SpeechRecognitionClass()
  recognition.lang = 'en-US'
  recognition.interimResults = false
  recognition.maxAlternatives = 1

  orbTap.addEventListener('click', async () => {
    if (speechListening) {
      recognition.stop()
      return
    }
    await startMicAmplitude()
    recognition.start()
    setOrbState('listening')
    speechListening = true
  })

  recognition.onresult = (e: { results: { [n: number]: { [n: number]: { transcript: string } } } }) => {
    const transcript = e.results[0]?.[0]?.transcript ?? ''
    if (transcript) {
      // Auto-send voice input
      const input = document.getElementById('chat-input') as HTMLTextAreaElement
      input.value = transcript
      sendMessage()
    }
  }

  recognition.onend = () => {
    speechListening = false
    stopMicAmplitude()
    if (orbState === 'listening') setOrbState('idle')
  }

  recognition.onerror = () => {
    speechListening = false
    stopMicAmplitude()
    if (orbState === 'listening') setOrbState('idle')
  }
} else {
  // No speech API — orb tap opens chat instead
  orbTap.addEventListener('click', openChat)
  orbTap.title = 'Open chat (voice not supported in this browser)'
}

// ── Chat panel toggle ─────────────────────────────────────────────────────────

function openChat(): void {
  document.body.classList.add('chat-open')
}

function closeChat(): void {
  document.body.classList.remove('chat-open')
}

document.getElementById('chat-toggle')!.addEventListener('click', openChat)
document.getElementById('chat-close')!.addEventListener('click', closeChat)

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
      break

    case 'chunk':
      if (orbState !== 'speaking') setOrbState('speaking')
      ui.appendChunk(msg.content)
      ttsBuffer += msg.content
      break

    case 'tool_call': {
      setOrbState('working')
      const actId = `${msg.tool}-${msg.agent}-${++toolCallCounter}`
      const activity: ToolActivity = {
        id: actId,
        tool: msg.tool,
        args: msg.args,
        status: 'running',
      }
      ui.addToolCall(activity)
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
      ttsSpeak(ttsBuffer)
      ttsBuffer = ''
      toolCallCounter = 0
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
        openChat()
        ui.showPlanningModal(
          questions,
          (answers) => {
            answers.forEach(({ question, answer }) => {
              ws.send({ type: 'planning_answer', question, answer })
            })
          },
          () => {
            questions.forEach((q) => {
              ws.send({ type: 'planning_answer', question: q, answer: '' })
            })
          },
        )
      }
      break

    case 'approval_required':
      openChat()
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

  openChat()
  ui.startAssistantMessage('BOWEN')
  ui.addUserMessage(text, 'user')
  setOrbState('thinking')

  ws.sendMessage(text)

  input.value = ''
  input.style.height = 'auto'
}

sendBtn.addEventListener('click', () => {
  ui.clearToolActivity()
  sendMessage()
})

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    ui.clearToolActivity()
    sendMessage()
  }
})

// Auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`
})
