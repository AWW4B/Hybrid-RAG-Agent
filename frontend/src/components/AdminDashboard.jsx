// =============================================================================
// src/components/AdminDashboard.jsx
// Admin dashboard: live sessions, compaction health, benchmark runner, user table.
// Only rendered when the JWT has admin:true.
// =============================================================================
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Database, Zap, Users, RefreshCw, Play,
  Unlock, ChevronRight, X, AlertTriangle, BarChart2,
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function adminFetch(path, options = {}) {
  const token = sessionStorage.getItem('auth_token')
  const res = await fetch(API_BASE + '/admin' + path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Admin request failed')
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function StatCard({ icon: Icon, label, value, color = '#F57224', sub }) {
  return (
    <div className="bg-[#1e1005]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-6 flex items-center gap-5 glass-shadow">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"
        style={{ background: `${color}15`, border: `1px solid ${color}30` }}>
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <p className="text-3xl font-bold text-[#f5ede2] tracking-tighter">{value ?? '—'}</p>
        <p className="text-[10px] font-bold text-[#c4a882] uppercase tracking-widest">{label}</p>
        {sub && <p className="text-[10px] text-[#c4a882]/40 font-mono mt-1">{sub}</p>}
      </div>
    </div>
  )
}

function SectionHeader({ title, onRefresh, refreshing }) {
  return (
    <div className="flex items-center justify-between mb-4 mt-2">
      <h2 className="text-[10px] font-bold text-[#c4a882] uppercase tracking-[0.3em] font-mono">{title}</h2>
      {onRefresh && (
        <button onClick={onRefresh} disabled={refreshing}
          className="flex items-center gap-2 text-[10px] font-bold text-[#F57224] hover:text-[#ff8c42] transition disabled:opacity-50 uppercase tracking-widest">
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} /> {refreshing ? 'Refreshing...' : 'Refresh Ledger'}
        </button>
      )}
    </div>
  )
}

function LogConsole({ logs, onClear }) {
  const scrollRef = useRef(null)
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [logs])

  return (
    <div className="bg-[#0e0800] rounded-2xl overflow-hidden mb-8 border border-white/5 glass-shadow">
      <div className="bg-[#1e1005] px-5 py-3 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
          </div>
          <span className="text-[10px] text-[#c4a882] font-mono uppercase tracking-[0.2em] ml-2">Engine Output Console</span>
        </div>
        {onClear && (
          <button onClick={onClear} className="text-[10px] text-[#c4a882]/40 hover:text-[#f5ede2] transition uppercase font-bold tracking-widest">Clear</button>
        )}
      </div>
      <div ref={scrollRef} className="p-6 h-56 overflow-y-auto font-mono text-[11px] leading-relaxed custom-scrollbar bg-[#0e0800]/50">
        {logs.map((L, i) => (
          <div key={i} className="mb-1.5 flex gap-4">
            <span className="text-[#c4a882]/30 shrink-0">[{new Date(L.time).toLocaleTimeString()}]</span>
            <span className={L.level === 'error' ? 'text-red-400' : L.level === 'warn' ? 'text-yellow-400' : 'text-[#c4a882]'}>
              {L.message}
            </span>
          </div>
        ))}
        {logs.length === 0 && <p className="text-[#c4a882]/20 italic py-4 text-center">No active signals from the engine...</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sessions panel
// ---------------------------------------------------------------------------
function SessionsPanel() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await adminFetch('/sessions')) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section>
      <SectionHeader title="Active Consultation Ledgers" onRefresh={load} refreshing={loading} />
      {!data ? (
        <div className="h-40 flex items-center justify-center text-[#c4a882]/40 animate-pulse text-xs uppercase tracking-widest">Loading records...</div>
      ) : (
        <div className="overflow-x-auto rounded-[2rem] border border-white/5 bg-[#1e1005]/40 backdrop-blur-md px-4 py-2">
          <table className="admin-table text-[11px] font-mono">
            <thead className="text-[#c4a882]/40 uppercase tracking-widest">
              <tr>
                {['Session ID', 'Identity', 'Turns', 'Tokens', 'Context Bloom', 'State'].map(h => (
                  <th key={h} className="px-4 py-4 text-left font-bold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-[#f5ede2]">
              {data.sessions.map((s) => (
                <tr key={s.session_id}>
                  <td className="font-bold text-[#F57224]">{s.session_id.slice(0, 12)}...</td>
                  <td className="text-[#c4a882]">{s.user_id?.slice(0, 8) ?? 'ANONYM'}</td>
                  <td>{s.turns}</td>
                  <td>{s.token_estimate} <span className="opacity-30">tk</span></td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full bg-[#F57224]" style={{ width: `${s.context_pct}%` }} />
                      </div>
                      <span className={`text-[10px] font-bold ${s.near_limit ? 'text-red-400' : 'text-[#c4a882]'}`}>
                        {s.context_pct}%
                      </span>
                    </div>
                  </td>
                  <td className="capitalize">
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-tighter ${s.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-white/5 text-[#c4a882]'}`}>
                       {s.status}
                    </span>
                  </td>
                </tr>
              ))}
              {data.sessions.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-12 text-center text-[#c4a882]/30 italic uppercase tracking-widest">No active bargaining records found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Compaction health panel
// ---------------------------------------------------------------------------
function CompactionPanel() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setStats(await adminFetch('/compaction/stats')) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section>
      <SectionHeader title="Memory Bloom Resilience (24h)" onRefresh={load} refreshing={loading} />
      {!stats ? (
        <div className="h-40 flex items-center justify-center text-[#c4a882]/40 animate-pulse text-xs uppercase tracking-widest">Recalling artifacts...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {['auto', 'micro', 'extraction'].map((type) => {
            const s = stats.stats?.[type]
            return (
              <div key={type} className="bg-[#1e1005]/60 backdrop-blur-xl rounded-2xl border border-white/5 p-6 glass-shadow">
                <p className="text-[10px] font-bold text-[#c4a882] uppercase tracking-[0.2em] mb-4">{type} refinement</p>
                {s ? (
                  <>
                    <p className="text-4xl font-bold text-[#F57224] tracking-tighter">{s.count}</p>
                    <p className="text-[10px] font-bold text-[#c4a882]/40 uppercase tracking-widest mt-1">successful cycles</p>
                    {s.avg_before && (
                      <div className="mt-4 pt-4 border-t border-white/5">
                        <p className="text-[10px] text-[#f5ede2] font-mono leading-relaxed">
                          <span className="text-[#c4a882]">REDUCTION:</span><br/>
                          {Math.round(s.avg_before)} <span className="opacity-30">→</span> {Math.round(s.avg_after)} <span className="opacity-30 text-[9px]">TOKENS AVG</span>
                        </p>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm font-bold text-[#c4a882]/20 uppercase tracking-widest mt-4">Zero Events</p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Benchmark runner
// ---------------------------------------------------------------------------
function BenchmarkPanel() {
  const [results, setResults]   = useState([])
  const [logs, setLogs]         = useState([])
  const [running, setRunning]   = useState(false)
  const [done, setDone]         = useState(false)
  const [concurrency, setConcurrency] = useState(null)
  const [testingConcurrency, setTestingConcurrency] = useState(false)

  const addLog = (msg, level = 'info') => {
    setLogs(prev => [...prev.slice(-49), { message: msg, level, time: Date.now() }])
  }

  const runBenchmark = async () => {
    setResults([])
    setRunning(true)
    setDone(false)
    try {
      const token = sessionStorage.getItem('auth_token')
      const res = await fetch(API_BASE + '/admin/benchmark/run', {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        }
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done: d, value } = await reader.read()
        if (d) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const json = JSON.parse(line.slice(6))
          if (json.done) { setDone(true); addLog("🏁 Benchmark session finished.") }
          else if (json.type === 'log') { addLog(json.message, json.level) }
          else { setResults(prev => [...prev, json]) }
        }
      }
    } catch (e) { console.error(e) }
    finally { setRunning(false) }
  }

  const runConcurrency = async () => {
    setConcurrency({ per_user: [], status: 'simulating' })
    setTestingConcurrency(true)
    try {
      const token = sessionStorage.getItem('auth_token')
      const res = await fetch(API_BASE + '/admin/benchmark/concurrency', {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        }
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      
      while (true) {
        const { done: d, value } = await reader.read()
        if (d) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const json = JSON.parse(line.slice(6))
          if (json.done) {
            setConcurrency(json)
            addLog("🏁 Concurrency test finished.")
          } else if (json.type === 'log') {
            addLog(json.message, json.level)
          } else if (json.individual_result) {
            setConcurrency(prev => ({
              ...prev,
              per_user: [...(prev?.per_user || []), json.individual_result]
            }))
          }
        }
      }
    } catch (e) { console.error(e) }
    finally { setTestingConcurrency(false) }
  }

  return (
    <section className="space-y-6">
      <LogConsole logs={logs} onClear={() => setLogs([])} />
      <div>
        <SectionHeader title="Functional Benchmarks" />
        <div className="flex gap-3 mb-4">
          <motion.button onClick={runBenchmark} disabled={running}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
                       bg-[#F57224] text-white shadow-sm disabled:opacity-50 transition">
            {running ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
            {running ? 'Running Tests…' : 'Run Quality Benchmark'}
          </motion.button>
          
          <motion.button onClick={runConcurrency} disabled={testingConcurrency}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
                       bg-blue-600 text-white shadow-sm disabled:opacity-50 transition">
            {testingConcurrency ? <RefreshCw size={15} className="animate-spin" /> : <Users size={15} />}
            {testingConcurrency ? 'Simulating…' : 'Run Concurrency Test (5 Users)'}
          </motion.button>
        </div>

        {concurrency && (
          <div className="mb-6 space-y-4">
            {/* Summary cards */}
            <div className="p-4 bg-blue-50 rounded-xl border border-blue-100 grid grid-cols-2 sm:grid-cols-5 gap-4">
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-500">Total Time</p>
                <p className="text-lg font-bold text-blue-900">{concurrency.total_time_ms ?? '—'}ms</p>
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-500">Avg Latency</p>
                <p className="text-lg font-bold text-blue-900">{concurrency.avg_latency_ms ?? '—'}ms</p>
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-500">P95 Latency</p>
                <p className="text-lg font-bold text-blue-900">{concurrency.p95_latency_ms ?? '—'}ms</p>
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-500">Concurrent Users</p>
                <p className="text-lg font-bold text-blue-900">{concurrency.n_users ?? '—'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-500">Status</p>
                <p className={`text-lg font-bold capitalize ${
                  concurrency.status === 'success' ? 'text-green-700' : 
                  concurrency.status === 'simulating' ? 'text-blue-600 animate-pulse' : 'text-red-600'
                }`}>{concurrency.status}</p>
              </div>
            </div>

            {/* Per-user breakdown */}
            {concurrency.per_user?.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-blue-100">
                <table className="w-full text-xs">
                  <thead className="bg-blue-50 text-blue-500 uppercase">
                    <tr>
                      {['User', 'Session', 'Latency', 'Status', 'Preview'].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-blue-50">
                    {concurrency.per_user.map((u) => (
                      <tr key={u.user_index} className="hover:bg-blue-50/50">
                        <td className="px-3 py-2 font-bold text-blue-800">#{u.user_index}</td>
                        <td className="px-3 py-2 font-mono text-gray-500">{u.session_id}</td>
                        <td className="px-3 py-2 text-gray-700">
                          {u.latency_ms != null ? `${u.latency_ms}ms` : '—'}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                            u.status === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
                          }`}>{u.status.toUpperCase()}</span>
                        </td>
                        <td className="px-3 py-2 text-gray-400 italic max-w-[200px] truncate">
                          {u.response_preview}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {results.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-gray-100">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500 uppercase">
                <tr>
                  {['Query', 'Type', 'Latency', 'Result', 'Preview'].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {results.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-700 font-medium">{r.query}</td>
                    <td className="px-3 py-2">
                      <span className="px-2 py-0.5 rounded-md bg-gray-100 text-gray-600 font-mono text-[10px] uppercase">
                        {r.type}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-500">{r.latency_ms}ms</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full font-bold
                        ${r.passed ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                        {r.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-400 italic max-w-[200px] truncate">
                      {r.response_preview}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {done && <p className="text-xs text-green-600 px-3 py-2 font-semibold">✅ Quality Benchmark complete</p>}
          </div>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Users panel
// ---------------------------------------------------------------------------
function UsersPanel() {
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [selected, setSelected] = useState(null)
  const [crm, setCrm]           = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await adminFetch('/users')) }
    catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const selectUser = async (user) => {
    setSelected(user)
    setCrm(null)
    try { setCrm(await adminFetch(`/users/${user.id}/crm`)) }
    catch { setCrm({ error: 'No CRM profile.' }) }
  }

  const unlock = async (userId) => {
    try {
      await adminFetch(`/users/${userId}/unlock`, { method: 'POST' })
      load()
    } catch (e) { alert(e.message) }
  }

  return (
    <section className="relative">
      <SectionHeader title="Registered Users" onRefresh={load} refreshing={loading} />
      {!data ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase">
              <tr>
                {['Username', 'Email', 'Registered', 'Last Login', 'Admin', 'Locked', 'Actions'].map(h => (
                  <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 cursor-pointer transition"
                  onClick={() => selectUser(u)}>
                  <td className="px-3 py-2 font-medium text-gray-800">{u.username}</td>
                  <td className="px-3 py-2 text-gray-500">{u.email}</td>
                  <td className="px-3 py-2 text-gray-400">{u.created_at?.slice(0, 10)}</td>
                  <td className="px-3 py-2 text-gray-400">{u.last_login?.slice(0, 10) ?? '—'}</td>
                  <td className="px-3 py-2">
                    {u.is_admin ? <span className="text-[#F57224] font-bold">Yes</span> : '—'}
                  </td>
                  <td className="px-3 py-2">
                    {u.locked_until ? (
                      <span className="text-red-500 font-semibold">🔒 Locked</span>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    {u.locked_until && (
                      <button onClick={() => unlock(u.id)}
                        className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-50 text-green-700
                                   text-xs font-semibold hover:bg-green-100 transition">
                        <Unlock size={11} /> Unlock
                      </button>
                    )}
                    <ChevronRight size={14} className="text-gray-400" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CRM side panel */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            className="absolute top-0 right-0 w-72 bg-white rounded-2xl shadow-2xl border border-gray-100 p-5 z-10"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-700">CRM — {selected.username}</h3>
              <button onClick={() => setSelected(null)}
                className="p-1 text-gray-400 hover:text-gray-600"><X size={14} /></button>
            </div>
            {!crm ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : crm.error ? (
              <p className="text-xs text-gray-400">{crm.error}</p>
            ) : (
              <dl className="space-y-2 text-xs">
                {Object.entries(crm).filter(([k]) => k !== 'user_id').map(([k, v]) => (
                  v ? (
                    <div key={k}>
                      <dt className="font-semibold text-gray-500 capitalize">{k.replace(/_/g, ' ')}</dt>
                      <dd className="text-gray-700 ml-1">{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
                    </div>
                  ) : null
                ))}
              </dl>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------
const TABS = [
  { id: 'sessions',    label: 'Sessions',    icon: Activity  },
  { id: 'memory',      label: 'Memory',      icon: Database  },
  { id: 'benchmark',   label: 'Benchmark',   icon: Zap       },
  { id: 'users',       label: 'Users',       icon: Users     },
]

export default function AdminDashboard({ onClose }) {
  const [tab, setTab] = useState('sessions')

  return (
    <div className="min-h-screen bg-[#0e0800] text-[#f5ede2]">
      {/* Decorative background glow */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#F57224]/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[#ff8c42]/5 blur-[100px] rounded-full" />
      </div>

      {/* Header */}
      <header className="bg-[#1e1005]/80 backdrop-blur-xl border-b border-white/5 sticky top-0 z-30 shadow-2xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center gap-5">
          <div className="w-10 h-10 rounded-xl bg-[#F57224] flex items-center justify-center shadow-lg shadow-orange-900/20">
            <BarChart2 size={22} className="text-[#1a0f00]" />
          </div>
          <div>
            <h1 className="font-serif italic text-xl font-bold tracking-tight">Merchant Control</h1>
            <p className="text-[9px] font-bold text-[#c4a882] uppercase tracking-[0.3em] font-mono leading-none mt-1">Administrative Sanctum</p>
          </div>
          <div className="flex-1" />
          {onClose && (
            <motion.button 
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={onClose}
              className="flex items-center gap-2 px-4 py-2 text-[10px] font-bold text-[#c4a882] hover:text-[#f5ede2]
                         rounded-full bg-white/5 border border-white/10 transition uppercase tracking-widest">
              <X size={14} /> Leave Sanctum
            </motion.button>
          )}
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-10 relative z-10">
        {/* Tab bar */}
        <div className="flex gap-1 bg-[#1e1005]/60 backdrop-blur-xl rounded-full p-1 border border-white/5 mb-12 w-fit shadow-2xl">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-full text-[10px] font-bold uppercase tracking-widest transition-all
                ${tab === id ? 'bg-[#F57224] text-[#1a0f00] shadow-xl' : 'text-[#c4a882] hover:text-[#f5ede2] hover:bg-white/5'}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {/* Panel */}
        <AnimatePresence mode="wait">
          <motion.div key={tab}
            initial={{ opacity: 0, scale: 0.98, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98, y: -10 }}
            transition={{ duration: 0.3 }}>
            {tab === 'sessions'  && <SessionsPanel />}
            {tab === 'memory'    && <CompactionPanel />}
            {tab === 'benchmark' && <BenchmarkPanel />}
            {tab === 'users'     && <UsersPanel />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
