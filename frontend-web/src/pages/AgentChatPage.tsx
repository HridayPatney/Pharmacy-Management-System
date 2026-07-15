import { useState, type FormEvent } from 'react'
import { askAgent } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { AgentQueryResponse } from '../types/api'

type ChatTurn = {
  id: number
  role: 'user' | 'assistant'
  text: string
  meta?: AgentQueryResponse | null
}

const SUGGESTIONS = [
  "What's low stock?",
  'Which medicines are expired?',
  "What's expiring this month?",
  'Give an inventory overview',
  "What's our sales revenue today?",
]

export function AgentChatPage() {
  const { token } = useAuth()
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([
    {
      id: 0,
      role: 'assistant',
      text: 'Ask about stock levels, expiry, medicine search, or sales totals. I only read data — I never change inventory.',
    },
  ])

  async function ask(question: string) {
    if (!token || !question.trim() || busy) return
    const q = question.trim()
    setBusy(true)
    setError(null)
    setInput('')
    setTurns((prev) => [...prev, { id: Date.now(), role: 'user', text: q }])
    try {
      const res = await askAgent(token, q)
      setTurns((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          text: res.answer,
          meta: res,
        },
      ])
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Agent request failed'
      setError(message)
      setTurns((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', text: `Sorry — ${message}` },
      ])
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void ask(input)
  }

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Inventory chat</h1>
          <p className="muted">
            Natural-language questions over live inventory and sales (read-only tools — not freeform SQL).
          </p>
        </div>

        <div className="chip-row">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="ghost"
              disabled={busy}
              onClick={() => void ask(s)}
            >
              {s}
            </button>
          ))}
        </div>

        {error ? <div className="error-box">{error}</div> : null}

        <div className="chat-log" aria-live="polite">
          {turns.map((t) => (
            <div key={t.id} className={t.role === 'user' ? 'chat-bubble user' : 'chat-bubble bot'}>
              <div className="chat-role">{t.role === 'user' ? 'You' : 'Agent'}</div>
              <pre className="chat-text">{t.text}</pre>
              {t.meta?.tool ? (
                <div className="muted chat-meta">
                  mode: {t.meta.mode || 'tool'} · tool: {t.meta.tool}
                  {t.meta.row_count ? ` · ${t.meta.row_count} row(s)` : ''}
                </div>
              ) : null}
              {t.meta?.sql ? (
                <pre className="chat-sql" title="Generated SQL (read-only, validated)">
                  {t.meta.sql}
                </pre>
              ) : null}
              {t.meta && t.meta.rows.length > 0 && t.meta.tool !== 'help' ? (
                <div className="table-wrap chat-table">
                  <table>
                    <thead>
                      <tr>
                        {Object.keys(t.meta.rows[0]).map((k) => (
                          <th key={k}>{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {t.meta.rows.slice(0, 15).map((row, idx) => (
                        <tr key={idx}>
                          {Object.keys(t.meta!.rows[0]).map((k) => (
                            <td key={k}>{String(row[k] ?? '—')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ))}
        </div>

        <form className="row chat-form" onSubmit={onSubmit}>
          <label className="grow">
            Question
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. What's low stock?"
              disabled={busy}
              autoComplete="off"
            />
          </label>
          <button type="submit" className="primary" disabled={busy || !input.trim()}>
            {busy ? 'Thinking…' : 'Ask'}
          </button>
        </form>
      </section>
    </div>
  )
}
