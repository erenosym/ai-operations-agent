import type { AgentEvent, Json } from '../types/agent'

function object(value: Json): value is { [key: string]: Json } {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
export function ExecutionTrace({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const starts = events.filter(e => e.type === 'tool_started')
  return <section className="panel trace" aria-labelledby="trace-title">
    <div className="panel-heading"><h2 id="trace-title">Execution trace</h2><span className="count">{starts.length} calls</span></div>
    <p className="muted">Live activity from operational tools.</p>
    {!starts.length && <div className="empty">{running ? 'Waiting for the first tool call…' : 'Tool calls will appear here when a task needs data or policy context.'}</div>}
    <ol className="steps">{starts.map(start => {
      const end = events.find(e => (e.type === 'tool_completed' || e.type === 'tool_failed') && e.step === start.step)
      const completed = end?.type === 'tool_completed' ? end : undefined
      const failed = end?.type === 'tool_failed' ? end : undefined
      const state = completed ? 'Completed' : failed ? 'Failed' : running ? 'Running' : 'Interrupted'
      const products = completed?.result.products
      const policies = completed?.result.results
      return <li key={start.step} className="step"><details>
        <summary><span className="step-number">{start.step}</span><span className="tool-name">{start.tool_name}</span><span className={`tool-status ${state.toLowerCase()}`}>{state}{completed || failed ? ` · ${Math.round((completed || failed)!.duration_ms)} ms` : ''}</span></summary>
        <div className="tool-details"><h3>Arguments</h3><pre>{JSON.stringify(start.arguments, null, 2)}</pre>
          {completed && <><h3>Result</h3><pre>{JSON.stringify(completed.result, null, 2)}</pre></>}
          {failed && <p className="error">{failed.message}</p>}
        </div>
      </details>
      {start.tool_name === 'get_top_refunded_products' && Array.isArray(products) && <ol className="preview">{products.filter(object).map((p, i) => <li key={i}>{typeof p.product_name === 'string' ? p.product_name : 'Product'}</li>)}</ol>}
      {start.tool_name === 'search_policy' && Array.isArray(policies) && <ul className="preview policy-preview">{policies.filter(object).map((p, i) => <li key={i}>{typeof p.section_title === 'string' && <strong>{p.section_title}</strong>}<small>{typeof p.policy_type === 'string' ? p.policy_type : ''} · {typeof p.source === 'string' ? p.source : ''}</small></li>)}</ul>}
      </li>
    })}</ol>
  </section>
}
