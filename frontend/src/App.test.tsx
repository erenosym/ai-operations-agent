import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { runAgent } from './api/agent'
import type { AgentEvent } from './types/agent'

vi.mock('./api/agent', async original => ({ ...await original<typeof import('./api/agent')>(), runAgent: vi.fn() }))
const mockRun = vi.mocked(runAgent)
afterEach(() => { cleanup(); vi.resetAllMocks() })
function submit(text = 'Investigate refunds') {
  fireEvent.change(screen.getByLabelText('Task'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: /Run task/ }))
}
it('shows live tool state, safe failure and final answer', async () => {
  let receive!: (event: AgentEvent) => void
  let finish!: () => void
  mockRun.mockImplementation((_message, _signal, callback) => { receive = callback; return new Promise(resolve => { finish = resolve }) })
  render(<App />); submit()
  act(() => receive({ type: 'tool_started', step: 1, tool_name: 'search_policy', arguments: { query: 'damaged' } }))
  expect(screen.getByText('search_policy')).toBeTruthy()
  expect(screen.getByText('Running')).toBeTruthy()
  act(() => receive({ type: 'tool_failed', step: 1, tool_name: 'search_policy', duration_ms: 3, message: 'Tool invocation failed.' }))
  expect(screen.getByText('Failed · 3 ms')).toBeTruthy()
  act(() => receive({ type: 'tool_started', step: 2, tool_name: 'search_policy', arguments: {} }))
  act(() => receive({ type: 'tool_completed', step: 2, tool_name: 'search_policy', duration_ms: 4, result: {} }))
  expect(screen.getByText('Completed · 4 ms')).toBeTruthy()
  act(() => { receive({ type: 'answer', content: 'A grounded answer.' }); receive({ type: 'run_completed', tool_calls_count: 2, termination_reason: 'completed' }); finish() })
  expect(screen.getByText('A grounded answer.')).toBeTruthy()
  await waitFor(() => expect(screen.queryByText('Stop run')).toBeNull())
})
it('shows backend errors and clears the previous run', async () => {
  mockRun.mockImplementationOnce(async (_m, _s, callback) => {
    callback({ type: 'answer', content: 'Previous answer' })
    callback({ type: 'error', code: 'agent_infrastructure_error', message: 'The agent could not complete the request.' })
  }).mockImplementationOnce(() => new Promise(() => {}))
  render(<App />); submit()
  await screen.findByRole('alert')
  await waitFor(() => expect(screen.queryByText('Stop run')).toBeNull())
  submit('Second task')
  expect(screen.queryByText('Previous answer')).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
})
it('prevents duplicate submits and can cancel then restart', async () => {
  let signal!: AbortSignal
  mockRun.mockImplementationOnce((_m, s) => { signal = s; return new Promise((_resolve, reject) => s.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))) })
    .mockImplementationOnce(async (_m, _s, cb) => { cb({ type: 'answer', content: 'Hello again' }); cb({ type: 'run_completed', tool_calls_count: 0, termination_reason: 'completed' }) })
  render(<App />); submit()
  fireEvent.submit(screen.getByLabelText('Task').closest('form')!)
  expect(mockRun).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Stop run' }))
  expect(signal.aborted).toBe(true)
  expect(screen.getByText('Run cancelled')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
  submit('Hello')
  expect(await screen.findByText('Hello again')).toBeTruthy()
})
