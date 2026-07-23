import { useState, useEffect, useCallback } from 'react'

// change this if the gateway isn't running locally
const GATEWAY_URL = 'http://127.0.0.1:8000'

export default function App() {
  const [op, setOp] = useState('GET')
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')
  const [log, setLog] = useState([])
  const [nodes, setNodes] = useState([])
  const [pinged, setPinged] = useState(null)
  const [loading, setLoading] = useState(false)

  const refreshHealth = useCallback(async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/health`)
      const data = await res.json()
      setNodes(data.nodes)
    } catch {
      setNodes([])
    }
  }, [])

  useEffect(() => {
    refreshHealth()
    const interval = setInterval(refreshHealth, 4000)
    return () => clearInterval(interval)
  }, [refreshHealth])

  const flashNode = (nodeAddr) => {
    setPinged(nodeAddr)
    setTimeout(() => setPinged(null), 600)
  }

  const pushLog = (entry) => {
    setLog((prev) => [entry, ...prev].slice(0, 100))
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!key) return
    setLoading(true)
    try {
      let res, data
      if (op === 'SET') {
        res = await fetch(`${GATEWAY_URL}/kv`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value }),
        })
      } else if (op === 'GET') {
        res = await fetch(`${GATEWAY_URL}/kv/${encodeURIComponent(key)}`)
      } else {
        res = await fetch(`${GATEWAY_URL}/kv/${encodeURIComponent(key)}`, { method: 'DELETE' })
      }
      data = await res.json()

      if (res.ok) {
        const nodeTag = data.node || '—'
        if (data.node) flashNode(data.node)
        pushLog({
          op,
          detail:
            op === 'SET' ? `${key} = ${value}` :
            op === 'GET' ? `${key} → ${data.value}` :
            `${key} removed`,
          node: nodeTag,
          err: false,
        })
      } else {
        pushLog({ op, detail: data.detail || 'error', node: '—', err: true })
      }
    } catch {
      pushLog({ op, detail: 'gateway unreachable', node: '—', err: true })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1><span className="prompt">$</span> kv-store / cluster console</h1>
        <div className="subtitle">gateway :: {GATEWAY_URL.replace('http://', '')}</div>
      </div>

      <div className="layout">
        <div className="panel">
          <p className="panel-title"><span className="dot" />command</p>

          <form className="command-row" onSubmit={submit}>
            <select value={op} onChange={(e) => setOp(e.target.value)}>
              <option>GET</option>
              <option>SET</option>
              <option>DEL</option>
            </select>
            <input
              placeholder="key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            {op === 'SET' && (
              <input
                placeholder="value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
            <button type="submit" disabled={loading || !key}>run</button>
          </form>

          <div className="log">
            {log.length === 0 && <div className="log-empty">no commands run yet</div>}
            {log.map((entry, i) => (
              <div className={`log-line ${entry.err ? 'err' : ''}`} key={i}>
                <span className="op">{entry.op}</span>
                <span className="detail">{entry.detail}</span>
                <span className="node-tag">{entry.node}</span>
              </div>
            ))}
          </div>

          <p className="hint">
            Talks to the FastAPI gateway at <code>{GATEWAY_URL}</code>, which
            routes each key to the C++ node that owns it and relays the raw
            TCP response back as JSON.
          </p>
        </div>

        <div className="panel">
          <p className="panel-title"><span className="dot" />cluster nodes</p>
          <div className="nodes-list">
            {nodes.length === 0 && <div className="log-empty">no nodes reachable</div>}
            {nodes.map((n) => (
              <div className="node-card" key={n.node}>
                <div className={`ping ${pinged === n.node ? 'active' : ''}`} />
                <span className="addr">{n.node}</span>
                <span className={`status ${n.status}`}>{n.status}</span>
              </div>
            ))}
          </div>
          <p className="hint">
            Single node today — add entries to <code>NODES</code> in
            gateway.py once you stand up more <code>kv_node</code> instances,
            and requests will start distributing across them.
          </p>
        </div>
      </div>
    </div>
  )
}
