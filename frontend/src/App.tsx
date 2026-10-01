import { useEffect, useRef, useState } from 'react'
import { AgentAPIError, runAgent } from './api/agent'
import { ExecutionTrace } from './components/ExecutionTrace'
import type { AgentEvent } from './types/agent'

const examples = [
  ['Refund ranking', 'Analyze the top 3 products by refund rate in September 2026.'],
  ['Product investigation', 'Why were StridePro Running Shoes being refunded in September 2026?'],
  ['Policy lookup', 'What does the policy say about receiving a damaged item?'],
  ['Combined analysis', 'Analyze the worst-performing product in September 2026, identify its main refund reason, and check whether the refund policy covers that situation.'],
]

export default function App() {
  const [input, setInput] = useState('')
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('Ready')
  const [running, setRunning] = useState(false)
  const active = useRef<AbortController | null>(null)
  useEffect(() => () => { active.current?.abort(); active.current = null }, [])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (active.current || !input.trim()) return
    const controller = new AbortController()
    active.current = controller
    setEvents([]); setAnswer(''); setError(''); setStatus('Connecting'); setRunning(true)
    try {
      await runAgent(input, controller.signal, e => {
        if (active.current !== controller) return
        setEvents(previous => [...previous, e])
        if (e.type === 'run_started') setStatus('Running')
        if (e.type === 'answer') setAnswer(e.content)
        if (e.type === 'error') { setError(e.message); setStatus('Failed') }
        if (e.type === 'run_completed') setStatus('Completed')
      })
    } catch (e) {
      if (active.current !== controller) return
      if (controller.signal.aborted) setStatus('Run cancelled')
      else { setError(e instanceof AgentAPIError ? e.message : 'The run could not complete. Please try again.'); setStatus('Failed') }
    } finally {
      if (active.current === controller) { active.current = null; setRunning(false) }
    }
  }
  function stop() {
    active.current?.abort(); active.current = null
    setRunning(false); setStatus('Run cancelled'); setError('')
  }

  return <div className="workspace">
    <header><div className="brand-mark" aria-hidden="true">O<span>↗</span></div><div><p className="eyebrow">OPERATIONS WORKSPACE</p><h1>AI Operations Agent</h1><p className="subtitle">Structured business data. Clear policy context.</p></div><span className="header-label">LOCAL WORKSPACE</span></header>
    <main>
      <section className="panel task-panel" aria-labelledby="task-title">
        <div className="panel-heading"><h2 id="task-title">What would you like to investigate?</h2><span className="badge">Operations + policies</span></div>
        <form onSubmit={submit}>
          <label htmlFor="task">Task</label>
          <textarea id="task" value={input} onChange={e => setInput(e.target.value)} maxLength={10000} placeholder="Ask about refunds, products, customer orders, or operational policies…" rows={4} required />
          <div className="form-footer"><span className="muted">One task at a time. Results stay in this session.</span><div className="actions">{running && <button type="button" className="secondary" onClick={stop}>Stop run</button>}<button type="submit" disabled={running || !input.trim()}>{running ? 'Running…' : 'Run task'} <span aria-hidden="true">↗</span></button></div></div>
        </form>
        <div className="examples"><span className="eyebrow">TRY A TASK</span>{examples.map(([label, prompt]) => <button type="button" className="example" key={label} onClick={() => setInput(prompt)}>{label}</button>)}</div>
      </section>
      <div className="run-bar" role="status" aria-live="polite"><span className={`dot ${running ? 'active' : ''}`} />{status}<span className="muted">Observable execution</span></div>
      {error && <div role="alert" className="error-banner">{error}</div>}
      <div className="results-grid"><ExecutionTrace events={events} running={running} /><section className="panel answer" aria-labelledby="answer-title"><div className="panel-heading"><h2 id="answer-title">Findings</h2><span className="eyebrow">AGENT RESPONSE</span></div>{answer ? <div className="answer-text">{answer}</div> : <div className="empty answer-empty"><span aria-hidden="true">↗</span><h3>Your findings, in context</h3><p>{running ? 'The agent is working on your task. Tool activity appears alongside the result.' : 'Run a task to bring operational facts and policy guidance together.'}</p></div>}</section></div>
    </main><footer>AI Operations Agent <span>Review findings against the returned data and policy sources.</span></footer>
  </div>
}
