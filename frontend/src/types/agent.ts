export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type ObjectValue = { [key: string]: Json }
export type AgentEvent =
  | { type: 'run_started' }
  | { type: 'tool_started'; step: number; tool_name: string; arguments: ObjectValue }
  | { type: 'tool_completed'; step: number; tool_name: string; duration_ms: number; result: ObjectValue }
  | { type: 'tool_failed'; step: number; tool_name: string; duration_ms: number; message: string }
  | { type: 'answer'; content: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'run_completed'; tool_calls_count: number; termination_reason: 'completed' }

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function json(value: unknown): value is Json {
  return value === null || typeof value === 'string' || typeof value === 'boolean' ||
    (typeof value === 'number' && Number.isFinite(value)) ||
    (Array.isArray(value) ? value.every(json) : record(value) && Object.values(value).every(json))
}
const nonnegative = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0

export function parseEvent(value: unknown): AgentEvent {
  if (!record(value)) throw new Error('Invalid agent event.')
  const tool = Number.isInteger(value.step) && Number(value.step) > 0 && typeof value.tool_name === 'string'
  let valid = false
  switch (value.type) {
    case 'run_started': valid = true; break
    case 'tool_started': valid = tool && record(value.arguments) && json(value.arguments); break
    case 'tool_completed': valid = tool && nonnegative(value.duration_ms) && record(value.result) && json(value.result); break
    case 'tool_failed': valid = tool && nonnegative(value.duration_ms) && typeof value.message === 'string'; break
    case 'answer': valid = typeof value.content === 'string'; break
    case 'error': valid = typeof value.code === 'string' && typeof value.message === 'string'; break
    case 'run_completed': valid = nonnegative(value.tool_calls_count) && Number.isInteger(value.tool_calls_count) && value.termination_reason === 'completed'; break
  }
  if (!valid) throw new Error('Invalid agent event.')
  return value as AgentEvent
}
