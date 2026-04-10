/**
 * ws.ts — WebSocket client with auto-reconnect and typed event dispatch.
 */

import type { WsMessage } from './types'

type WsEventMap = {
  message: WsMessage
  open: void
  close: void
}

type Listener<T> = (data: T) => void

export class BowenWS {
  private ws: WebSocket | null = null
  private url: string
  private reconnectDelay = 1000
  private maxDelay = 16000
  private alive = true
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private listeners: { [K in keyof WsEventMap]?: Listener<WsEventMap[K]>[] } = {}

  conversationId: string | null = null
  topicId = 'default'

  constructor(url: string) {
    this.url = url
  }

  connect(): void {
    if (!this.alive) return
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      this.reconnectDelay = 1000
      this._emit('open', undefined as void)
      this._startPing()
    }

    this.ws.onmessage = (evt) => {
      try {
        const msg: WsMessage = JSON.parse(evt.data as string)
        if (msg.type === 'conversation_created') {
          this.conversationId = msg.conversation_id
          this.topicId = msg.topic_id
        }
        this._emit('message', msg)
      } catch {
        // ignore malformed frames
      }
    }

    this.ws.onclose = () => {
      this._stopPing()
      this._emit('close', undefined as void)
      if (this.alive) {
        setTimeout(() => this.connect(), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  sendMessage(content: string, targetAgent?: string): void {
    this.send({
      type: 'message',
      content,
      topic_id: this.topicId,
      conversation_id: this.conversationId ?? undefined,
      ...(targetAgent ? { target_agent: targetAgent } : {}),
    })
  }

  on<K extends keyof WsEventMap>(event: K, fn: Listener<WsEventMap[K]>): () => void {
    if (!this.listeners[event]) this.listeners[event] = [] as never
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(this.listeners[event] as any).push(fn)
    return () => this.off(event, fn)
  }

  off<K extends keyof WsEventMap>(event: K, fn: Listener<WsEventMap[K]>): void {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    this.listeners[event] = (this.listeners[event] as any)?.filter((l: unknown) => l !== fn)
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  destroy(): void {
    this.alive = false
    this._stopPing()
    this.ws?.close()
  }

  private _emit<K extends keyof WsEventMap>(event: K, data: WsEventMap[K]): void {
    this.listeners[event]?.forEach((fn) => (fn as Listener<WsEventMap[K]>)(data))
  }

  private _startPing(): void {
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping' })
    }, 20000)
  }

  private _stopPing(): void {
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
