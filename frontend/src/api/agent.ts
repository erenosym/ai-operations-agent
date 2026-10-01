import { parseEvent, type AgentEvent } from '../types/agent'

export class AgentAPIError extends Error {}

export async function* readEvents(stream: ReadableStream<Uint8Array>): AsyncGenerator<AgentEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let buffer = ''
  function parse(line: string) {
    try { return parseEvent(JSON.parse(line) as unknown) }
    catch { throw new AgentAPIError('The server sent an invalid event. Please try again.') }
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      let index: number
      while ((index = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, index).trim()
        buffer = buffer.slice(index + 1)
        if (line) yield parse(line)
      }
      if (buffer.length > 2_000_000) throw new AgentAPIError('The server event exceeds the display limit.')
      if (done) break
    }
    if (buffer.trim()) yield parse(buffer)
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

export async function runAgent(message: string, signal: AbortSignal, onEvent: (event: AgentEvent) => void): Promise<void> {
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001').replace(/\/$/, '')
  let terminal = false
  try {
    const response = await fetch(`${base}/agent/run`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message.trim() }), signal,
    })
    if (!response.ok) throw new AgentAPIError(response.status === 422
      ? 'Please enter a valid task (up to 10,000 characters).'
      : `The request could not start (HTTP ${response.status}).`)
    if (!response.body || !response.headers.get('content-type')?.includes('application/x-ndjson')) {
      throw new AgentAPIError('The server did not return an event stream.')
    }
    for await (const event of readEvents(response.body)) {
      if (signal.aborted) throw new DOMException('Cancelled', 'AbortError')
      onEvent(event)
      if (event.type === 'error' || event.type === 'run_completed') { terminal = true; break }
    }
    if (!terminal) throw new AgentAPIError('The connection ended before the run completed. Please try again.')
  } catch (error) {
    if (signal.aborted || error instanceof AgentAPIError) throw error
    throw new AgentAPIError('Could not reach the agent. Check the connection and try again.')
  }
}
