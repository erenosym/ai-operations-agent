import { describe, it, expect, vi, afterEach } from 'vitest'
import { readEvents, runAgent } from './agent'

const encoder = new TextEncoder()
function stream(chunks: string[]) {
  return new ReadableStream<Uint8Array>({ start(controller) { chunks.forEach(c => controller.enqueue(encoder.encode(c))); controller.close() } })
}
async function collect(chunks: string[]) {
  const result = []
  for await (const event of readEvents(stream(chunks))) result.push(event)
  return result
}
afterEach(() => vi.unstubAllGlobals())
describe('NDJSON stream', () => {
  it('buffers a line across chunks', async () => {
    expect(await collect(['{"ty', 'pe":"answer",', '"content":"hello"}\n'])).toEqual([{ type: 'answer', content: 'hello' }])
  })
  it('handles multiple lines, blanks and final unterminated line', async () => {
    expect(await collect(['\n{"type":"run_started"}\n\n{"type":"answer","content":"ok"}'])).toHaveLength(2)
  })
  it('rejects malformed JSON safely', async () => {
    await expect(collect(['not json\n'])).rejects.toThrow('invalid event')
  })
  it('rejects invalid event shapes', async () => {
    await expect(collect(['{"type":"answer","content":5}\n'])).rejects.toThrow('invalid event')
  })
  it('delivers an event before the network stream closes', async () => {
    let controller!: ReadableStreamDefaultController<Uint8Array>
    const input = new ReadableStream<Uint8Array>({ start(c) { controller = c } })
    const events = readEvents(input)
    controller.enqueue(encoder.encode('{"type":"run_started"}\n'))
    expect((await events.next()).value).toEqual({ type: 'run_started' })
    await events.return(undefined)
  })
  it('preserves split UTF-8 characters', async () => {
    const bytes = encoder.encode('{"type":"answer","content":"İş"}\n')
    const input = new ReadableStream<Uint8Array>({ start(c) { for (const byte of bytes) c.enqueue(new Uint8Array([byte])); c.close() } })
    const events = []
    for await (const event of readEvents(input)) events.push(event)
    expect(events).toEqual([{ type: 'answer', content: 'İş' }])
  })
})
it('posts the narrow request and processes stream events', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(stream(['{"type":"run_started"}\n{"type":"run_completed","tool_calls_count":0,"termination_reason":"completed"}\n']), { headers: { 'content-type': 'application/x-ndjson' } }))
  vi.stubGlobal('fetch', fetchMock)
  const receive = vi.fn()
  await runAgent(' hello ', new AbortController().signal, receive)
  expect(fetchMock.mock.calls[0][1].body).toBe('{"message":"hello"}')
  expect(receive).toHaveBeenCalledTimes(2)
})
it('reports premature EOF', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream(['{"type":"run_started"}\n']), { headers: { 'content-type': 'application/x-ndjson' } })))
  await expect(runAgent('hello', new AbortController().signal, () => {})).rejects.toThrow('before the run completed')
})
it('reports HTTP validation failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 422 })))
  await expect(runAgent('hello', new AbortController().signal, () => {})).rejects.toThrow('valid task')
})
