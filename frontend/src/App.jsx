import React, { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import {
  Cpu,
  ShieldCheck,
  Smartphone,
  Plus,
  Trash2,
  Send,
  Layers,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Film,
  Code2,
  Terminal,
  Download,
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  Loader2,
  Sliders,
  HardDrive,
  Zap,
  PanelLeft,
  PanelRight,
  ExternalLink,
  RefreshCw,
  X,
  ArrowUpRight,
  Eye,
  Database,
} from 'lucide-react'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const STUDIO_BLUEPRINTS = [
  {
    id: 'excel_saas',
    label: 'SaaS Financial Model (.xlsx)',
    category: 'spreadsheet',
    icon: FileSpreadsheet,
    description: 'Multi-quarter revenue, burn rate & live =SUM() formulas',
    tool_name: 'create_excel_spreadsheet',
    arguments: {
      title: 'SaaS Operating Model 2026',
      sheets: [
        {
          name: 'P&L Forecast',
          headers: ['Line Item', 'Q1 2026', 'Q2 2026', 'Q3 2026', 'Q4 2026', 'FY26 Total'],
          rows: [
            ['ARR Subscription Revenue', 145000, 178000, 219000, 268000, '=SUM(B2:E2)'],
            ['Enterprise Services', 32000, 38500, 44000, 52000, '=SUM(B3:E3)'],
            ['Gross Revenue', '=SUM(B2:B3)', '=SUM(C2:C3)', '=SUM(D2:D3)', '=SUM(E2:E3)', '=SUM(F2:F3)'],
            ['Cloud & GPU Infrastructure', -24500, -27800, -31200, -35900, '=SUM(B5:E5)'],
            ['R&D Engineering Payroll', -68000, -72000, -78000, -84000, '=SUM(B6:E6)'],
            ['G&A and Operations', -19500, -21000, -22500, -24000, '=SUM(B7:E7)'],
            ['Total Operating Expenses', '=SUM(B5:B7)', '=SUM(C5:C7)', '=SUM(D5:D7)', '=SUM(E5:E7)', '=SUM(F5:F7)'],
            ['Net Operating EBITDA', '=B4+B8', '=C4+C8', '=D4+D8', '=E4+E8', '=F4+F8'],
          ],
        },
        {
          name: 'Unit Economics',
          headers: ['Metric', 'Q1', 'Q2', 'Q3', 'Q4', 'Average'],
          rows: [
            ['Customer Acquisition Cost (CAC)', 1180, 1120, 1050, 990, '=AVERAGE(B2:E2)'],
            ['Lifetime Value (LTV)', 6400, 6850, 7300, 7900, '=AVERAGE(B3:E3)'],
            ['Net Dollar Retention (%)', 114, 118, 121, 125, '=AVERAGE(B4:E4)'],
          ],
        },
      ],
    },
  },
  {
    id: 'interactive_app',
    label: 'Compound ROI Simulator App',
    category: 'webapp',
    icon: Code2,
    description: 'Interactive HTML/JS wealth & hardware TCO calculator',
    tool_name: 'build_interactive_app',
    arguments: {
      title: 'Capital & AI Infrastructure ROI Simulator',
      html_code: `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Capital & AI Infrastructure Simulator</title>
<style>
  * { box-sizing: border-box; font-family: Inter, -apple-system, sans-serif; }
  body { margin: 0; padding: 24px; background: #0B0D12; color: #F3F4F6; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 20px; }
  .card { background: #131720; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 16px; }
  .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #94A3B8; margin-bottom: 6px; }
  .val { font-size: 24px; font-weight: 700; color: #F9FAFB; font-variant-numeric: tabular-nums; }
  .accent { color: #D97757; }
  .emerald { color: #10B981; }
  .control { margin-bottom: 14px; }
  .control label { display: flex; justify-content: space-between; font-size: 13px; color: #CBD5E1; margin-bottom: 6px; }
  input[type=range] { width: 100%; accent-color: #D97757; cursor: pointer; }
  table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; font-variant-numeric: tabular-nums; }
  th, td { border-bottom: 1px solid rgba(255,255,255,0.07); padding: 9px 10px; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { color: #94A3B8; font-weight: 500; font-size: 11px; text-transform: uppercase; }
</style>
</head>
<body>
  <h2 style="margin:0 0 4px 0;font-size:18px;letter-spacing:-0.02em">Local AI vs Cloud API Cost & Investment Simulator</h2>
  <p style="margin:0 0 18px 0;font-size:13px;color:#94A3B8">Interactive model generated locally by Antigravity Studio</p>
  <div class="grid">
    <div class="card"><div class="label">5-Year Cloud API Spend</div><div id="cloudTotal" class="val accent">$14,400</div></div>
    <div class="card"><div class="label">Local Hardware Electricity</div><div id="localTotal" class="val">$1,080</div></div>
    <div class="card"><div class="label">Net 5-Year Savings (Invested)</div><div id="netSavings" class="val emerald">$16,942</div></div>
  </div>
  <div class="card">
    <div class="control">
      <label><span>Monthly Cloud API / Subscription Equivalent ($)</span><strong id="mCloudLbl">$240 / mo</strong></label>
      <input id="mCloud" type="range" min="40" max="1000" step="20" value="240" oninput="calc()" />
    </div>
    <div class="control">
      <label><span>Local GPU Power Draw & Compute Cost ($/mo)</span><strong id="mLocalLbl">$18 / mo</strong></label>
      <input id="mLocal" type="range" min="5" max="120" step="1" value="18" oninput="calc()" />
    </div>
    <div class="control">
      <label><span>Annual Compound Return on Saved Capital (%)</span><strong id="rateLbl">9.0%</strong></label>
      <input id="rate" type="range" min="2" max="18" step="0.5" value="9" oninput="calc()" />
    </div>
    <table>
      <thead><tr><th>Year</th><th>Cumulative Cloud Cost</th><th>Cumulative Local Cost</th><th>Compounded Savings</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    function fmt(n) { return '$' + Math.round(n).toLocaleString(); }
    function calc() {
      const c = +document.getElementById('mCloud').value;
      const l = +document.getElementById('mLocal').value;
      const r = (+document.getElementById('rate').value) / 100;
      document.getElementById('mCloudLbl').textContent = '$' + c + ' / mo';
      document.getElementById('mLocalLbl').textContent = '$' + l + ' / mo';
      document.getElementById('rateLbl').textContent = (r * 100).toFixed(1) + '%';
      let tbody = '', invested = 0;
      const monthlyDiff = c - l;
      for (let yr = 1; yr <= 5; yr++) {
        for (let m = 0; m < 12; m++) {
          invested = (invested + monthlyDiff) * (1 + r / 12);
        }
        tbody += '<tr><td>Year ' + yr + '</td><td>' + fmt(c * 12 * yr) + '</td><td>' + fmt(l * 12 * yr) + '</td><td style="color:#10B981;font-weight:600">' + fmt(invested) + '</td></tr>';
      }
      document.getElementById('rows').innerHTML = tbody;
      document.getElementById('cloudTotal').textContent = fmt(c * 60);
      document.getElementById('localTotal').textContent = fmt(l * 60);
      document.getElementById('netSavings').textContent = fmt(invested);
    }
    calc();
  </script>
</body>
</html>`,
    },
  },
  {
    id: 'pdf_brief',
    label: 'Executive Architecture Brief (.pdf)',
    category: 'document',
    icon: FileText,
    description: 'Formatted PDF specification for Desktop & Lunar Lake AI',
    tool_name: 'create_document',
    arguments: {
      title: 'Universal Local AI Topology Specification',
      doc_format: 'pdf',
      sections: [
        {
          heading: '1. Executive Summary',
          body: 'This architecture brief documents our zero-telemetry, hardware-adaptive Local AI Studio deployment across discrete CUDA workstations and unified-memory Intel Lunar Lake laptops.',
          bullets: [
            '100% on-device data residency with SQLite persistence and LAN Air-Gap enforcement.',
            'Dynamic hardware detection adapting context windows and VRAM hand-off policies.',
          ],
        },
        {
          heading: '2. Dual-Hardware Optimization Matrix',
          body: 'The runtime profiler dynamically switches optimization strategies based on detected silicon:',
          bullets: [
            'Desktop Profile (NVIDIA RTX 4070 SUPER 12GB GDDR6X + 64GB RAM): Runs dense 7B-14B models in high-bandwidth VRAM with automatic keep_alive:0 VRAM eviction prior to diffusion.',
            'Laptop Profile (Intel Core Ultra 258V + Arc 140V + 47 TOPS NPU + 32GB Unified LPDDR5X): Prioritizes Mixture-of-Experts (Qwen3 30B-A3B) and compact 7B dense models across the ~17.6GB shared iGPU memory pool.',
          ],
        },
      ],
    },
  },
  {
    id: 'chart_bench',
    label: 'Hardware Throughput Chart (.png)',
    category: 'image',
    icon: ImageIcon,
    description: 'High-DPI benchmark visualization across local models',
    tool_name: 'generate_visual_media',
    arguments: {
      prompt: 'Local Inference Throughput (Tokens/Sec) — RTX 4070S vs Core Ultra 258V',
      media_type: 'chart',
      chart_data: {
        type: 'bar',
        labels: ['Llama 3.2 3B', 'Qwen 2.5 Coder 7B', 'Llama 3.1 8B', 'Qwen 2.5 Coder 14B', 'Qwen3 30B-A3B MoE'],
        values: [115, 76, 71, 44, 38],
      },
    },
  },
  {
    id: 'motion_clip',
    label: 'Orbital Harmonic Motion (.gif)',
    category: 'video',
    icon: Film,
    description: '24-frame procedural motion synthesis clip',
    tool_name: 'generate_visual_media',
    arguments: {
      prompt: 'Orbital Silicon Telemetry Waveforms',
      media_type: 'video',
    },
  },
]

export default function App() {
  const [systemStatus, setSystemStatus] = useState(null)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [artifacts, setArtifacts] = useState([])
  const [selectedArtifact, setSelectedArtifact] = useState(null)
  const [artifactFilter, setArtifactFilter] = useState('all')
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)
  const [appViewMode, setAppViewMode] = useState('preview')

  const [selectedModel, setSelectedModel] = useState('qwen2.5-coder:7b')
  const [agentMode, setAgentMode] = useState('agent')
  const [promptInput, setPromptInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')

  // Modals & Drawers
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(true)
  const [rightWorkbenchOpen, setRightWorkbenchOpen] = useState(true)
  const [hwModalOpen, setHwModalOpen] = useState(false)
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [mobileModalOpen, setMobileModalOpen] = useState(false)

  // Model pull state
  const [pullingModel, setPullingModel] = useState(null)
  const [pullProgress, setPullProgress] = useState(null)
  const [customModelName, setCustomModelName] = useState('')

  const chatEndRef = useRef(null)

  const fetchSystemStatus = async () => {
    try {
      const r = await fetch('/api/system/status')
      if (r.ok) {
        const data = await r.json()
        setSystemStatus(data)
        if (data.installed_models?.length > 0) {
          const installedIds = data.installed_models.map((m) => m.id)
          if (!installedIds.includes(selectedModel)) {
            setSelectedModel(installedIds[0])
          }
        }
      }
    } catch (e) {
      console.error('Status check failed:', e)
    }
  }

  const fetchConversations = async () => {
    try {
      const r = await fetch('/api/conversations')
      if (r.ok) {
        const data = await r.json()
        setConversations(data.conversations || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchArtifacts = async () => {
    try {
      const r = await fetch('/api/artifacts')
      if (r.ok) {
        const data = await r.json()
        const list = data.artifacts || []
        setArtifacts(list)
        if (!selectedArtifact && list.length > 0) {
          setSelectedArtifact(list[0])
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchSystemStatus()
    fetchConversations()
    fetchArtifacts()
    const interval = setInterval(fetchSystemStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamStatus])

  const loadConversation = async (convId) => {
    try {
      const r = await fetch(`/api/conversations/${convId}`)
      if (r.ok) {
        const data = await r.json()
        setActiveConvId(data.id)
        setMessages(data.messages || [])
        if (data.model) setSelectedModel(data.model)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const startNewSession = () => {
    setActiveConvId(null)
    setMessages([])
    setPromptInput('')
  }

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation()
    await fetch(`/api/conversations/${convId}`, { method: 'DELETE' })
    if (activeConvId === convId) {
      startNewSession()
    }
    fetchConversations()
  }

  const handleUpdateSetting = async (updates) => {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (r.ok) {
      await fetchSystemStatus()
    }
  }

  const handlePullModel = async (modelId) => {
    if (!modelId || pullingModel) return
    setPullingModel(modelId)
    setPullProgress({ status: 'Starting download...', percent: 0 })

    try {
      const r = await fetch('/api/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId }),
      })
      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const chunk of parts) {
          if (chunk.startsWith('data: ')) {
            try {
              const ev = JSON.parse(chunk.slice(6))
              setPullProgress(ev)
            } catch {}
          }
        }
      }
      await fetchSystemStatus()
      setSelectedModel(modelId)
    } catch (e) {
      console.error(e)
    } finally {
      setPullingModel(null)
      setPullProgress(null)
    }
  }

  const handleUnloadModel = async (modelId) => {
    await fetch('/api/models/unload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelId }),
    })
    await fetchSystemStatus()
  }

  const runDirectBlueprint = async (bp) => {
    setStreamStatus(`Running Studio Tool: ${bp.label}...`)
    try {
      const r = await fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_name: bp.tool_name,
          arguments: bp.arguments,
          conversation_id: activeConvId,
        }),
      })
      if (r.ok) {
        const data = await r.json()
        await fetchArtifacts()
        if (data.artifact) {
          setSelectedArtifact(data.artifact)
          setActiveSheetIdx(0)
          setRightWorkbenchOpen(true)
        }
      }
    } finally {
      setStreamStatus('')
    }
  }

  const handleSendPrompt = async (overrideText) => {
    const text = (overrideText ?? promptInput).trim()
    if (!text || isStreaming) return
    if (!overrideText) setPromptInput('')

    setIsStreaming(true)
    setStreamStatus('Connecting to local engine...')

    const tempAssistantId = 'stream_' + Date.now()
    const optimisticUser = {
      id: 'u_' + Date.now(),
      role: 'user',
      content: text,
      created_at: Date.now() / 1000,
    }
    const optimisticAssistant = {
      id: tempAssistantId,
      role: 'assistant',
      content: '',
      thinking: '',
      tool_calls: [],
      artifacts: [],
      model: selectedModel,
      tokens_per_sec: 0,
      created_at: Date.now() / 1000,
    }

    setMessages((prev) => [...prev, optimisticUser, optimisticAssistant])

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeConvId,
          prompt: text,
          model: selectedModel,
          mode: agentMode,
        }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const rawEv of events) {
          if (!rawEv.startsWith('data: ')) continue
          let ev
          try {
            ev = JSON.parse(rawEv.slice(6))
          } catch {
            continue
          }

          if (ev.type === 'session') {
            setActiveConvId(ev.conversation_id)
          } else if (ev.type === 'status') {
            setStreamStatus(ev.message)
          } else if (ev.type === 'tool_start') {
            setStreamStatus(`Executing tool: ${ev.tool.name}...`)
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? { ...m, tool_calls: [...(m.tool_calls || []), ev.tool] }
                  : m
              )
            )
          } else if (ev.type === 'tool_end') {
            setStreamStatus('Synthesizing response...')
            const newArts = ev.artifacts || []
            if (newArts.length > 0) {
              setSelectedArtifact(newArts[0])
              setActiveSheetIdx(0)
              setRightWorkbenchOpen(true)
              fetchArtifacts()
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      tool_calls: (m.tool_calls || []).map((tc) =>
                        tc.id === ev.tool.id ? ev.tool : tc
                      ),
                      artifacts: [...(m.artifacts || []), ...newArts],
                    }
                  : m
              )
            )
          } else if (ev.type === 'thinking') {
            setStreamStatus('Reasoning...')
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? { ...m, thinking: (m.thinking || '') + ev.delta }
                  : m
              )
            )
          } else if (ev.type === 'token') {
            setStreamStatus('')
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? { ...m, content: (m.content || '') + ev.delta }
                  : m
              )
            )
          } else if (ev.type === 'done') {
            setStreamStatus('')
            setMessages((prev) =>
              prev.map((m) => (m.id === tempAssistantId ? ev.message : m))
            )
            fetchConversations()
            fetchArtifacts()
            fetchSystemStatus()
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
    } finally {
      setIsStreaming(false)
      setStreamStatus('')
    }
  }

  const hw = systemStatus?.hardware
  const settings = systemStatus?.settings
  const installedModels = systemStatus?.installed_models || []
  const runningModels = systemStatus?.running_models || []
  const network = systemStatus?.network

  const filteredArtifacts = artifacts.filter(
    (a) => artifactFilter === 'all' || a.category === artifactFilter
  )

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0A0B0E] text-[#F3F4F6] select-none overflow-hidden">
      {/* TOP INSTRUMENT HEADER BAR */}
      <header className="h-14 shrink-0 border-b border-white/[0.075] bg-[#0D0F14]/90 backdrop-blur-md px-3 lg:px-4 flex items-center justify-between gap-2 z-30">
        {/* Left Brand & Drawer Toggle */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setLeftDrawerOpen((v) => !v)}
            aria-label="Toggle Sessions Sidebar"
            className="h-9 w-9 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] flex items-center justify-center text-slate-300 transition"
          >
            <PanelLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5 pr-2">
            <div className="h-7 w-7 rounded-md bg-[#D97757]/15 border border-[#D97757]/40 flex items-center justify-center">
              <div className="h-2.5 w-2.5 rounded-sm bg-[#D97757]" />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-2">
                <span className="font-semibold tracking-tight text-sm text-white">
                  LOCAL AI STUDIO
                </span>
                <span className="text-[10px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-300 border border-white/[0.07]">
                  v1.0
                </span>
              </div>
            </div>
          </div>

          {/* Model Selector + Hub Trigger */}
          <div className="flex items-center gap-1.5">
            <div className="relative">
              <select
                aria-label="Select Active Local LLM"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="h-9 pl-3 pr-8 rounded-lg bg-[#14171F] hover:bg-[#191D27] border border-white/[0.09] text-xs font-mono text-slate-100 appearance-none cursor-pointer transition"
              >
                {installedModels.length === 0 ? (
                  <option value="qwen2.5-coder:7b">qwen2.5-coder:7b (pulling...)</option>
                ) : (
                  installedModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.size_gb} GB)
                    </option>
                  ))
                )}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            <button
              onClick={() => setModelModalOpen(true)}
              className="h-9 px-2.5 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
              title="Open Model Hub & Benchmark Manager"
            >
              <Database className="w-3.5 h-3.5 text-[#D97757]" />
              <span className="hidden md:inline">Models</span>
            </button>
          </div>

          {/* Agent vs Direct Chat Mode Switcher */}
          <div className="hidden md:flex items-center p-0.5 rounded-lg bg-[#12151C] border border-white/[0.07]">
            <button
              onClick={() => setAgentMode('agent')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${
                agentMode === 'agent'
                  ? 'bg-[#D97757] text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3 h-3" />
              <span>Antigravity Agent</span>
            </button>
            <button
              onClick={() => setAgentMode('chat')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                agentMode === 'chat'
                  ? 'bg-white/[0.12] text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Direct Chat
            </button>
          </div>
        </div>

        {/* Right Telemetry, Privacy Air-Gap & Mobile LAN Connect */}
        <div className="flex items-center gap-2">
          {/* Universal Hardware Telemetry Pill */}
          <button
            onClick={() => setHwModalOpen(true)}
            className="h-9 px-3 rounded-lg border border-white/[0.08] bg-[#13161E] hover:bg-[#191D28] flex items-center gap-2 text-xs transition"
            title="Inspect Hardware Topology & Auto-Tuner (Desktop RTX 4070S / Laptop Core Ultra 258V)"
          >
            <Cpu className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="font-mono text-[11px] text-slate-200 tabular-nums hidden xl:inline">
              {hw ? hw.short_badge : 'Profiling Silicon...'}
            </span>
            {hw?.is_simulated && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-amber-500/20 text-amber-300 rounded">
                SIM
              </span>
            )}
          </button>

          {/* Strict Air-Gap Privacy Shield */}
          <button
            onClick={() =>
              handleUpdateSetting({ air_gap_mode: !settings?.air_gap_mode })
            }
            className={`h-9 px-2.5 rounded-lg border text-xs font-mono flex items-center gap-1.5 transition ${
              settings?.air_gap_mode !== false
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
            }`}
            title="Toggle Strict Local Air-Gap Mode (Zero External Network Calls)"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span className="hidden lg:inline text-[11px]">
              {settings?.air_gap_mode !== false ? 'AIR-GAP ON' : 'LAN + WEB'}
            </span>
          </button>

          {/* Mobile Phone Wi-Fi Connect Trigger */}
          <button
            onClick={() => setMobileModalOpen(true)}
            className="h-9 px-2.5 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-slate-200 flex items-center gap-1.5 text-xs transition"
            title="Connect from your Phone over Local Wi-Fi"
          >
            <Smartphone className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden sm:inline font-mono text-[11px] tabular-nums">
              {network?.lan_ip || 'LAN'}
            </span>
          </button>

          {/* Toggle Right Studio Workbench */}
          <button
            onClick={() => setRightWorkbenchOpen((v) => !v)}
            aria-label="Toggle Studio Workbench"
            className={`h-9 px-2.5 rounded-lg border flex items-center gap-1.5 text-xs transition ${
              rightWorkbenchOpen
                ? 'border-[#D97757]/40 bg-[#D97757]/15 text-white'
                : 'border-white/[0.08] bg-[#14171F] text-slate-300 hover:bg-[#1B1F2A]'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden sm:inline font-medium">Workbench</span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-slate-300 tabular-nums">
              {artifacts.length}
            </span>
          </button>
        </div>
      </header>

      {/* MAIN THREE-COLUMN WORKSPACE */}
      <div className="flex-1 flex min-h-0 relative overflow-hidden">
        {/* LEFT RAIL: SESSIONS & ONE-CLICK STUDIO BLUEPRINTS */}
        {leftDrawerOpen && (
          <aside className="w-72 shrink-0 border-r border-white/[0.075] bg-[#0D0F14] flex flex-col justify-between z-20 select-none">
            <div className="p-3 space-y-4 overflow-y-auto flex-1">
              {/* New Session Button */}
              <button
                onClick={startNewSession}
                className="w-full h-10 px-3 rounded-lg bg-[#D97757] hover:bg-[#E4886A] text-white font-medium text-xs flex items-center justify-between shadow-sm transition"
              >
                <span className="flex items-center gap-2">
                  <Plus className="w-4 h-4" />
                  <span>New Studio Session</span>
                </span>
                <span className="font-mono text-[10px] opacity-80">CTRL+N</span>
              </button>

              {/* One-Click Antigravity Studio Generators */}
              <div>
                <div className="px-1.5 mb-2 flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    Instant Studio Generators
                  </span>
                  <span className="text-[10px] font-mono text-[#D97757]">1-Click</span>
                </div>
                <div className="space-y-1">
                  {STUDIO_BLUEPRINTS.map((bp) => {
                    const Icon = bp.icon
                    return (
                      <button
                        key={bp.id}
                        onClick={() => runDirectBlueprint(bp)}
                        className="w-full text-left p-2 rounded-lg border border-transparent hover:border-white/[0.08] hover:bg-[#151922] group transition flex items-start gap-2.5"
                      >
                        <div className="h-7 w-7 rounded-md bg-white/[0.04] border border-white/[0.07] flex items-center justify-center shrink-0 mt-0.5 group-hover:border-[#D97757]/40 group-hover:text-[#D97757] text-slate-300">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium text-slate-200 truncate group-hover:text-white">
                            {bp.label}
                          </div>
                          <div className="text-[11px] text-slate-400 truncate">
                            {bp.description}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Conversation History */}
              <div>
                <div className="px-1.5 mb-2 flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    Local Session History
                  </span>
                  <span className="text-[10px] font-mono text-slate-500 tabular-nums">
                    {conversations.length}
                  </span>
                </div>

                {conversations.length === 0 ? (
                  <div className="px-2 py-4 text-xs text-slate-500 border border-dashed border-white/[0.06] rounded-lg text-center">
                    No saved sessions yet. All chats stay 100% on your local NVMe drive.
                  </div>
                ) : (
                  <div className="space-y-1">
                    {conversations.map((c) => (
                      <div
                        key={c.id}
                        onClick={() => loadConversation(c.id)}
                        className={`group px-2.5 py-2 rounded-lg text-xs cursor-pointer flex items-center justify-between gap-2 transition ${
                          activeConvId === c.id
                            ? 'bg-white/[0.09] text-white font-medium border border-white/[0.1]'
                            : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                        }`}
                      >
                        <span className="truncate">{c.title}</span>
                        <button
                          onClick={(e) => handleDeleteConversation(e, c.id)}
                          aria-label="Delete session"
                          className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-400 p-1 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Silicon Telemetry Footer */}
            {hw && (
              <div
                onClick={() => setHwModalOpen(true)}
                className="p-3 border-t border-white/[0.075] bg-[#0B0D12] hover:bg-[#11141C] cursor-pointer transition"
              >
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-300 mb-1">
                  <span className="truncate">{hw.gpu?.name}</span>
                  <span className="text-[#10B981] shrink-0">ACTIVE</span>
                </div>
                <div className="w-full h-1.5 bg-white/[0.07] rounded-full overflow-hidden mb-1.5">
                  <div
                    className="h-full bg-[#D97757] rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          14,
                          Math.round(
                            ((hw.gpu.vram_total_gb - hw.gpu.vram_free_gb) /
                              Math.max(1, hw.gpu.vram_total_gb)) *
                              100
                          )
                        )
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 tabular-nums">
                  <span>
                    {hw.gpu.vram_free_gb}GB free / {hw.gpu.vram_total_gb}GB
                  </span>
                  <span>{hw.tuning?.recommended_num_ctx?.toLocaleString()} ctx</span>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* CENTER STAGE: EDITORIAL CONVERSATION & AGENT TRACE STREAM */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#0A0B0E] select-text">
          <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-10 py-6">
            {messages.length === 0 ? (
              <div className="max-w-3xl mx-auto py-6 sm:py-10 space-y-8">
                {/* Editorial Hero Header */}
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] text-[11px] font-mono text-slate-300">
                    <span className="h-2 w-2 rounded-full bg-[#10B981]" />
                    <span>
                      100% ON-DEVICE WORKSTATION •{' '}
                      {hw?.profile_label || 'LOCAL SILICON'}
                    </span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
                    What shall we build, analyze, or synthesize locally?
                  </h1>
                  <p className="text-sm text-slate-400 leading-relaxed max-w-2xl">
                    Ask general questions, switch between local LLMs on the fly, or let the{' '}
                    <span className="text-slate-200 font-medium">Antigravity Agent</span>{' '}
                    write and execute Python code to build formatted Excel workbooks, PDF/Word
                    reports, charts, visual media, and interactive web applications.
                  </p>
                </div>

                {/* 4 Tactile Starter Prompt Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    {
                      title: 'Custom Excel Budget & Forecast',
                      subtitle: 'Multi-tab .xlsx with live =SUM() & =AVERAGE() formulas',
                      icon: FileSpreadsheet,
                      prompt:
                        'Create an Excel spreadsheet for a 2026 Personal & Business Cashflow Tracker with columns for Category, Q1, Q2, Q3, Q4, and Annual Total using =SUM formulas.',
                    },
                    {
                      title: 'Build an Interactive Web App',
                      subtitle: 'Self-contained HTML/JS tool rendered live in Workbench',
                      icon: Code2,
                      prompt:
                        'Build an interactive Pomodoro & Deep Work Task Timer web app with dark mode styling, task list, and session analytics.',
                    },
                    {
                      title: 'Generate Executive PDF Report',
                      subtitle: 'Structured multi-section document ready to share',
                      icon: FileText,
                      prompt:
                        'Create a PDF document titled "Private Local AI Deployment Strategy" with sections on Security, Hardware Sizing (RTX 4070 SUPER & Intel Core Ultra 258V), and ROI.',
                    },
                    {
                      title: 'Synthesize Chart or Visual Media',
                      subtitle: 'High-DPI data charts, artwork & motion clips',
                      icon: ImageIcon,
                      prompt:
                        'Generate a chart comparing local LLM inference speeds across 3B, 7B, 14B, and 30B-A3B MoE models.',
                    },
                  ].map((card, i) => {
                    const Icon = card.icon
                    return (
                      <button
                        key={i}
                        onClick={() => handleSendPrompt(card.prompt)}
                        className="text-left p-4 rounded-xl bg-[#10131A] hover:bg-[#151922] border border-white/[0.075] hover:border-[#D97757]/40 transition group flex flex-col justify-between gap-3"
                      >
                        <div className="flex items-center justify-between">
                          <div className="h-8 w-8 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-[#D97757]">
                            <Icon className="w-4 h-4" />
                          </div>
                          <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-[#D97757] transition" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-slate-100 group-hover:text-white">
                            {card.title}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5">
                            {card.subtitle}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>

                {/* Hardware Auto-Tuning Summary Strip */}
                {hw && (
                  <div className="p-4 rounded-xl bg-[#0E1016] border border-white/[0.07] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="text-xs font-mono uppercase tracking-wider text-[#D97757] flex items-center gap-2">
                        <Sliders className="w-3.5 h-3.5" />
                        <span>Universal Hardware Auto-Tuner Active</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {hw.tuning?.explanation}
                      </p>
                    </div>
                    <button
                      onClick={() => setHwModalOpen(true)}
                      className="shrink-0 h-9 px-3 rounded-lg border border-white/[0.1] bg-[#151922] hover:bg-[#1B202C] text-xs font-medium text-slate-200 transition"
                    >
                      Switch / Test Laptop 258V Profile
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="max-w-3xl mx-auto space-y-6">
                {messages.map((msg) => (
                  <MessageRow
                    key={msg.id}
                    msg={msg}
                    onSelectArtifact={(art) => {
                      setSelectedArtifact(art)
                      setActiveSheetIdx(0)
                      setRightWorkbenchOpen(true)
                    }}
                  />
                ))}

                {streamStatus && (
                  <div className="flex items-center gap-2.5 text-xs font-mono text-slate-400 py-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-[#D97757]" />
                    <span>{streamStatus}</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          {/* BOTTOM COMPOSER BAR */}
          <div className="p-3 sm:p-4 border-t border-white/[0.075] bg-[#0B0D12]">
            <div className="max-w-3xl mx-auto">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSendPrompt()
                }}
                className="relative rounded-xl bg-[#12151E] border border-white/[0.09] focus-within:border-[#D97757]/60 transition p-2 flex items-end gap-2"
              >
                <textarea
                  rows={2}
                  value={promptInput}
                  onChange={(e) => setPromptInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendPrompt()
                    }
                  }}
                  placeholder={
                    agentMode === 'agent'
                      ? 'Ask anything, or instruct Antigravity Agent to build an Excel sheet, PDF report, chart, image, or web app...'
                      : 'Ask a question in Direct Chat mode...'
                  }
                  className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none px-2 py-1"
                />
                <button
                  type="submit"
                  disabled={isStreaming || !promptInput.trim()}
                  aria-label="Send message"
                  className="h-10 px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white font-medium text-xs flex items-center gap-1.5 shrink-0 transition"
                >
                  {isStreaming ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Run</span>
                      <Send className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </form>
              <div className="mt-2 px-1 flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>
                  Model: <strong className="text-slate-300">{selectedModel}</strong> • Mode:{' '}
                  <strong className="text-slate-300 uppercase">{agentMode}</strong>
                </span>
                <span>100% Local Execution • Enter to send</span>
              </div>
            </div>
          </div>
        </main>

        {/* RIGHT SPLIT PANE: THE STUDIO WORKBENCH (ARTIFACTS & LIVE PREVIEW) */}
        {rightWorkbenchOpen && (
          <aside className="w-full sm:w-[440px] xl:w-[520px] shrink-0 border-l border-white/[0.075] bg-[#0D0F14] flex flex-col z-20">
            {/* Workbench Header & Category Tabs */}
            <div className="p-3 border-b border-white/[0.075] flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#D97757]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                  Studio Workbench
                </span>
              </div>
              <div className="flex items-center gap-1">
                {[
                  { id: 'all', label: 'All' },
                  { id: 'spreadsheet', label: 'Excel' },
                  { id: 'webapp', label: 'Apps' },
                  { id: 'document', label: 'Docs' },
                  { id: 'image', label: 'Media' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setArtifactFilter(tab.id)}
                    className={`px-2 py-1 rounded text-[11px] font-mono transition ${
                      artifactFilter === tab.id
                        ? 'bg-white/[0.12] text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Active Artifact Inspector Canvas */}
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              {selectedArtifact ? (
                <div className="flex-1 flex flex-col min-h-0">
                  {/* Artifact Toolbar */}
                  <div className="px-3.5 py-2.5 bg-[#12151D] border-b border-white/[0.07] flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-white truncate">
                        {selectedArtifact.title}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 truncate tabular-nums">
                        {selectedArtifact.filename} •{' '}
                        {(selectedArtifact.size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {selectedArtifact.category === 'webapp' && (
                        <button
                          onClick={() =>
                            setAppViewMode((m) => (m === 'preview' ? 'code' : 'preview'))
                          }
                          className="h-8 px-2.5 rounded-md border border-white/[0.1] bg-[#181C26] text-xs font-mono text-slate-200 hover:bg-[#202634]"
                        >
                          {appViewMode === 'preview' ? 'View Code' : 'Live App'}
                        </button>
                      )}
                      <a
                        href={`${selectedArtifact.url}?download=true`}
                        download={selectedArtifact.filename}
                        className="h-8 px-3 rounded-md bg-[#D97757] hover:bg-[#E4886A] text-white text-xs font-medium flex items-center gap-1.5 transition"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download</span>
                      </a>
                    </div>
                  </div>

                  {/* Dynamic Artifact Body */}
                  <div className="flex-1 overflow-auto p-3.5 bg-[#0A0B0E]">
                    {selectedArtifact.category === 'spreadsheet' && (
                      <SpreadsheetPreview
                        artifact={selectedArtifact}
                        activeSheetIdx={activeSheetIdx}
                        setActiveSheetIdx={setActiveSheetIdx}
                      />
                    )}

                    {selectedArtifact.category === 'webapp' &&
                      (appViewMode === 'preview' ? (
                        <div className="h-full w-full rounded-lg overflow-hidden border border-white/[0.09] bg-[#0B0D12] flex flex-col">
                          <div className="px-3 py-1.5 bg-[#14171F] border-b border-white/[0.07] flex items-center justify-between text-[11px] font-mono text-slate-400">
                            <span>SANDBOXED INTERACTIVE APP PREVIEW</span>
                            <a
                              href={selectedArtifact.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#D97757] hover:underline flex items-center gap-1"
                            >
                              <span>Open Full Tab</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                          <iframe
                            title={selectedArtifact.title}
                            src={selectedArtifact.url}
                            className="w-full flex-1 border-0 bg-[#0B0D12]"
                            sandbox="allow-scripts allow-forms"
                          />
                        </div>
                      ) : (
                        <pre className="p-3 rounded-lg bg-[#10131A] border border-white/[0.08] text-xs font-mono text-slate-200 overflow-x-auto">
                          {selectedArtifact.preview_data?.code_snippet ||
                            'HTML Application Source'}
                        </pre>
                      ))}

                    {selectedArtifact.category === 'document' && (
                      <div className="space-y-3 h-full flex flex-col">
                        {selectedArtifact.filename.endsWith('.pdf') ? (
                          <iframe
                            title={selectedArtifact.title}
                            src={selectedArtifact.url}
                            className="w-full flex-1 min-h-[360px] rounded-lg border border-white/[0.08] bg-white"
                          />
                        ) : null}
                        {selectedArtifact.preview_data?.markdown && (
                          <div
                            className="p-4 rounded-lg bg-[#11141C] border border-white/[0.08] prose-studio"
                            dangerouslySetInnerHTML={{
                              __html: marked.parse(selectedArtifact.preview_data.markdown),
                            }}
                          />
                        )}
                      </div>
                    )}

                    {(selectedArtifact.category === 'image' ||
                      selectedArtifact.category === 'video') && (
                      <div className="space-y-3">
                        <div className="rounded-lg overflow-hidden border border-white/[0.09] bg-[#10131A] flex items-center justify-center p-2">
                          <img
                            src={selectedArtifact.url}
                            alt={selectedArtifact.title}
                            className="max-w-full rounded"
                          />
                        </div>
                        <div className="p-3 rounded-lg bg-[#11141C] border border-white/[0.07] text-xs font-mono text-slate-400 space-y-1">
                          <div>
                            Engine:{' '}
                            <span className="text-slate-200">
                              {selectedArtifact.preview_data?.engine || 'Local Studio'}
                            </span>
                          </div>
                          {selectedArtifact.preview_data?.prompt && (
                            <div>
                              Prompt:{' '}
                              <span className="text-slate-300">
                                {selectedArtifact.preview_data.prompt}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
                  <Layers className="w-8 h-8 mb-2 text-slate-600" />
                  <p className="text-xs">
                    Generated Excel spreadsheets, PDF/Word documents, interactive apps, and
                    visual media will appear here for inspection.
                  </p>
                </div>
              )}

              {/* Bottom Artifact Gallery Strip */}
              <div className="h-44 shrink-0 border-t border-white/[0.075] bg-[#0B0D12] p-2.5 overflow-y-auto">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-1 mb-2">
                  Generated Artifacts ({filteredArtifacts.length})
                </div>
                <div className="space-y-1">
                  {filteredArtifacts.map((art) => (
                    <button
                      key={art.id}
                      onClick={() => {
                        setSelectedArtifact(art)
                        setActiveSheetIdx(0)
                      }}
                      className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between gap-2 transition ${
                        selectedArtifact?.id === art.id
                          ? 'bg-[#D97757]/15 border border-[#D97757]/40 text-white'
                          : 'hover:bg-white/[0.04] text-slate-300 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <ArtifactTypeBadge category={art.category} />
                        <span className="truncate font-medium">{art.title}</span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 shrink-0 tabular-nums">
                        {(art.size_bytes / 1024).toFixed(1)} KB
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* UNIVERSAL HARDWARE PROFILER & AUTO-TUNER MODAL */}
      {hwModalOpen && hw && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Cpu className="w-5 h-5 text-[#D97757]" />
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    Universal Hardware Profiler & Runtime Auto-Tuner
                  </h2>
                  <p className="text-xs text-slate-400">
                    Automatically adapts context window, VRAM hand-off, and model selection across Desktop & Laptop
                  </p>
                </div>
              </div>
              <button
                onClick={() => setHwModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-5 max-h-[80vh] overflow-y-auto">
              {/* Profile Switcher (Auto vs Desktop RTX 4070S vs Laptop Intel Core Ultra 258V) */}
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2">
                  Active Hardware Profile Mode
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {[
                    {
                      id: 'auto',
                      title: 'Auto-Detect Silicon',
                      desc: 'Live WMI + NVIDIA/Intel Arc + NPU probe',
                    },
                    {
                      id: 'desktop_rtx4070s',
                      title: 'Desktop: RTX 4070 SUPER',
                      desc: '12GB GDDR6X VRAM + 64GB System RAM',
                    },
                    {
                      id: 'laptop_ultra_258v',
                      title: 'Laptop: Core Ultra 258V',
                      desc: 'Intel Arc 140V + 47 TOPS NPU + 32GB Unified',
                    },
                  ].map((p) => {
                    const active =
                      (settings?.hardware_profile_override || 'auto') === p.id
                    return (
                      <button
                        key={p.id}
                        onClick={() =>
                          handleUpdateSetting({ hardware_profile_override: p.id })
                        }
                        className={`p-3 rounded-xl border text-left transition ${
                          active
                            ? 'border-[#D97757] bg-[#D97757]/15 text-white'
                            : 'border-white/[0.08] bg-[#141821] text-slate-300 hover:border-white/[0.15]'
                        }`}
                      >
                        <div className="text-xs font-semibold">{p.title}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">{p.desc}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Silicon Topology Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    GPU / Compute Engine
                  </div>
                  <div className="text-xs font-semibold text-white mt-1">
                    {hw.gpu.name}
                  </div>
                  <div className="text-[11px] font-mono text-[#D97757] mt-1 tabular-nums">
                    {hw.gpu.vram_free_gb} GB Free / {hw.gpu.vram_total_gb} GB
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {hw.gpu.memory_type}
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    NPU & Neural Accelerator
                  </div>
                  <div className="text-xs font-semibold text-white mt-1">
                    {hw.npu.name}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">{hw.npu.role}</div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    CPU & System Memory
                  </div>
                  <div className="text-xs font-semibold text-white mt-1 truncate">
                    {hw.cpu.name}
                  </div>
                  <div className="text-[11px] font-mono text-emerald-400 mt-1 tabular-nums">
                    {hw.memory.ram_total_gb} GB Total ({hw.memory.ram_free_gb} GB Free)
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {hw.memory.unified_memory
                      ? 'Unified On-Package LPDDR5X'
                      : 'Discrete PCIe + System DDR'}
                  </div>
                </div>
              </div>

              {/* Runtime Auto-Tuning Policy Box */}
              <div className="p-4 rounded-xl bg-[#0D0F14] border border-white/[0.08] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">
                    Computed Runtime Parameters
                  </span>
                  <span className="text-[11px] font-mono text-[#10B981]">
                    {hw.gpu.backend}
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {hw.tuning.explanation}
                </p>
                <div className="pt-2 flex flex-wrap gap-2 text-[11px] font-mono">
                  <span className="px-2 py-1 rounded bg-white/[0.05] text-slate-200 tabular-nums">
                    num_ctx: {hw.tuning.recommended_num_ctx}
                  </span>
                  <span className="px-2 py-1 rounded bg-white/[0.05] text-slate-200">
                    keep_alive: {hw.tuning.keep_alive}
                  </span>
                  <span className="px-2 py-1 rounded bg-white/[0.05] text-slate-200">
                    vram_handoff: {String(hw.tuning.vram_handoff_before_media)}
                  </span>
                  <span className="px-2 py-1 rounded bg-white/[0.05] text-slate-200">
                    kv_cache: {hw.tuning.kv_cache_quant}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODEL HUB & BENCHMARK MANAGER MODAL */}
      {modelModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Local Model Hub & Hardware-Matched Roster
                </h2>
                <p className="text-xs text-slate-400">
                  Switch models immediately or pull new Ollama models tuned for{' '}
                  {hw?.profile_label}
                </p>
              </div>
              <button
                onClick={() => setModelModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-5 max-h-[80vh] overflow-y-auto">
              {pullingModel && pullProgress && (
                <div className="p-3.5 rounded-xl bg-[#D97757]/15 border border-[#D97757]/40 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-white">
                      Pulling <strong>{pullingModel}</strong>: {pullProgress.status}
                    </span>
                    <span className="text-[#D97757] tabular-nums">
                      {pullProgress.percent || 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-black/40 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#D97757] transition-all"
                      style={{ width: `${pullProgress.percent || 5}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Currently Loaded in VRAM */}
              {runningModels.length > 0 && (
                <div>
                  <div className="text-[11px] font-mono uppercase tracking-wider text-emerald-400 mb-2">
                    Currently Loaded in GPU Memory (/api/ps)
                  </div>
                  <div className="space-y-1.5">
                    {runningModels.map((rm) => (
                      <div
                        key={rm.name}
                        className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between text-xs"
                      >
                        <div>
                          <span className="font-mono font-semibold text-white">
                            {rm.name}
                          </span>
                          <span className="ml-2 font-mono text-emerald-300 tabular-nums">
                            {rm.vram_gb} GB VRAM ({rm.vram_pct}% GPU)
                          </span>
                        </div>
                        <button
                          onClick={() => handleUnloadModel(rm.name)}
                          className="px-2.5 py-1 rounded bg-black/40 hover:bg-black/60 text-slate-200 font-mono text-[11px]"
                        >
                          Free VRAM
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Curated Recommendations for Active Hardware Profile */}
              <div>
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2">
                  Recommended for {hw?.profile_label}
                </div>
                <div className="space-y-2">
                  {(hw?.recommended_models || []).map((rec) => {
                    const isInstalled = installedModels.some(
                      (m) => m.id === rec.id || m.id.startsWith(rec.id)
                    )
                    return (
                      <div
                        key={rec.id}
                        className="p-3 rounded-xl bg-[#141821] border border-white/[0.07] flex items-center justify-between gap-3"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-white font-mono">
                              {rec.id}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#D97757]/20 text-[#D97757]">
                              {rec.badge}
                            </span>
                            <span className="text-[11px] font-mono text-slate-400 tabular-nums">
                              ~{rec.size_gb} GB
                            </span>
                          </div>
                          <div className="text-xs text-slate-300 mt-0.5">{rec.role}</div>
                          <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                            Fit: {rec.fit}
                          </div>
                        </div>

                        <div className="shrink-0">
                          {isInstalled ? (
                            <button
                              onClick={() => {
                                setSelectedModel(rec.id)
                                setModelModalOpen(false)
                              }}
                              className={`h-8 px-3 rounded-lg text-xs font-medium transition ${
                                selectedModel === rec.id
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  : 'bg-white/[0.08] hover:bg-white/[0.14] text-white'
                              }`}
                            >
                              {selectedModel === rec.id ? 'Active' : 'Use Model'}
                            </button>
                          ) : (
                            <button
                              disabled={Boolean(pullingModel)}
                              onClick={() => handlePullModel(rec.id)}
                              className="h-8 px-3 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white text-xs font-medium transition"
                            >
                              Pull ({rec.size_gb}GB)
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Pull Custom Ollama Model Tag */}
              <div className="pt-2 border-t border-white/[0.08]">
                <label className="block text-[11px] font-mono uppercase text-slate-400 mb-1.5">
                  Pull Any Model from Ollama Library (e.g. gemma2:9b, phi4:14b, mistral-nemo:12b)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customModelName}
                    onChange={(e) => setCustomModelName(e.target.value)}
                    placeholder="Enter model tag (e.g. phi4:14b)..."
                    className="flex-1 h-9 px-3 rounded-lg bg-[#0D0F14] border border-white/[0.1] text-xs font-mono text-white"
                  />
                  <button
                    disabled={!customModelName.trim() || Boolean(pullingModel)}
                    onClick={() => handlePullModel(customModelName.trim())}
                    className="h-9 px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white text-xs font-medium"
                  >
                    Pull Model
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MOBILE PHONE WI-FI ACCESS QR MODAL */}
      {mobileModalOpen && network && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-[#D97757]" />
                <h2 className="text-sm font-semibold text-white">
                  Access on Your Phone (Local Home Wi-Fi)
                </h2>
              </div>
              <button
                onClick={() => setMobileModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 text-center space-y-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                Connect your phone to the same Wi-Fi network and scan this QR code or
                enter the local LAN address below. Zero cloud servers involved.
              </p>
              {network.qr_code && (
                <div className="inline-block p-3 rounded-xl bg-[#111317] border border-white/[0.1]">
                  <img
                    src={network.qr_code}
                    alt="LAN QR Code"
                    className="w-44 h-44 mx-auto"
                  />
                </div>
              )}
              <div className="p-3 rounded-lg bg-[#0B0D12] border border-white/[0.08] font-mono text-sm text-[#D97757] select-all tabular-nums">
                {network.lan_url}
              </div>
              <p className="text-[11px] text-slate-400">
                Tip: In iOS Safari or Android Chrome, tap <strong>Add to Home Screen</strong>{' '}
                to install Local AI Studio as a full-screen mobile app.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MessageRow({ msg, onSelectArtifact }) {
  const [thinkOpen, setThinkOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const isUser = msg.role === 'user'

  return (
    <div
      className={`rounded-xl p-4 transition ${
        isUser
          ? 'bg-[#131722] border border-white/[0.08]'
          : 'bg-[#0E1017] border border-white/[0.06]'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded ${
              isUser
                ? 'bg-white/[0.08] text-slate-200'
                : 'bg-[#D97757]/15 text-[#D97757] border border-[#D97757]/30'
            }`}
          >
            {isUser ? 'You' : msg.model || 'Antigravity Studio'}
          </span>
        </div>
        {!isUser && msg.tokens_per_sec > 0 && (
          <span className="text-[11px] font-mono text-slate-400 tabular-nums">
            {msg.tokens_per_sec} tok/s
          </span>
        )}
      </div>

      {/* Collapsible Thinking / Reasoning Trace */}
      {msg.thinking && (
        <div className="mb-3">
          <button
            onClick={() => setThinkOpen((v) => !v)}
            className="text-xs font-mono text-slate-400 hover:text-slate-200 flex items-center gap-1.5 py-1"
          >
            {thinkOpen ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            <span>Reasoning Chain ({msg.thinking.length} chars)</span>
          </button>
          {thinkOpen && (
            <div className="mt-1.5 p-3 rounded-lg bg-[#090B0E] border border-white/[0.06] text-xs font-mono text-slate-400 whitespace-pre-wrap">
              {msg.thinking}
            </div>
          )}
        </div>
      )}

      {/* Collapsible Antigravity Tool Execution Traces */}
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {msg.tool_calls.map((tc) => (
            <div
              key={tc.id}
              className="rounded-lg bg-[#121620] border border-white/[0.08] px-3 py-2 text-xs font-mono"
            >
              <div
                onClick={() => setToolsOpen((v) => !v)}
                className="flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  {tc.status === 'running' ? (
                    <Loader2 className="w-3.5 h-3.5 text-[#D97757] animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />
                  )}
                  <span className="text-slate-200 font-semibold">{tc.name}</span>
                  <span className="text-slate-400 truncate max-w-xs">
                    {tc.summary || ''}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 tabular-nums">
                  {tc.duration_ms ? `${tc.duration_ms}ms` : ' running'}
                </span>
              </div>
              {toolsOpen && (
                <pre className="mt-2 pt-2 border-t border-white/[0.06] text-[11px] text-slate-400 overflow-x-auto">
                  {JSON.stringify(tc.arguments, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Message Prose Content */}
      {msg.content && (
        <div
          className="prose-studio"
          dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }}
        />
      )}

      {/* Inline Generated Artifact Cards */}
      {msg.artifacts && msg.artifacts.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/[0.07] grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {msg.artifacts.map((art) => (
            <div
              key={art.id}
              onClick={() => onSelectArtifact(art)}
              className="p-3 rounded-lg bg-[#141822] hover:bg-[#1A202E] border border-[#D97757]/35 cursor-pointer flex items-center justify-between gap-3 transition"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <ArtifactTypeBadge category={art.category} />
                  <span className="text-xs font-semibold text-white truncate">
                    {art.title}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-slate-400 truncate mt-0.5 tabular-nums">
                  {art.filename} • {(art.size_bytes / 1024).toFixed(1)} KB
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[11px] font-mono text-[#D97757] flex items-center gap-1">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Inspect</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ArtifactTypeBadge({ category }) {
  const map = {
    spreadsheet: { label: 'XLSX', cls: 'bg-emerald-500/20 text-emerald-300' },
    document: { label: 'DOC', cls: 'bg-sky-500/20 text-sky-300' },
    webapp: { label: 'APP', cls: 'bg-[#D97757]/20 text-[#D97757]' },
    image: { label: 'IMG', cls: 'bg-amber-500/20 text-amber-300' },
    video: { label: 'MOTION', cls: 'bg-rose-500/20 text-rose-300' },
  }
  const b = map[category] || { label: 'FILE', cls: 'bg-white/10 text-slate-300' }
  return (
    <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${b.cls}`}>
      {b.label}
    </span>
  )
}

function SpreadsheetPreview({ artifact, activeSheetIdx, setActiveSheetIdx }) {
  const sheets = artifact.preview_data?.sheets || []
  if (sheets.length === 0) {
    return (
      <div className="p-4 text-xs text-slate-400">
        Excel file ready. Click <strong>Download</strong> above to open in Microsoft Excel.
      </div>
    )
  }
  const currentSheet = sheets[activeSheetIdx] || sheets[0]

  return (
    <div className="space-y-2.5">
      {/* Worksheet Tabs */}
      <div className="flex items-center gap-1.5 border-b border-white/[0.08] pb-2">
        {sheets.map((s, idx) => (
          <button
            key={s.name}
            onClick={() => setActiveSheetIdx(idx)}
            className={`px-2.5 py-1 rounded-md text-xs font-mono transition ${
              idx === activeSheetIdx
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold'
                : 'bg-[#14171F] text-slate-400 hover:text-slate-200'
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* Live Grid Table */}
      <div className="overflow-x-auto rounded-lg border border-white/[0.09] bg-[#0E1117]">
        <table className="w-full border-collapse text-xs font-mono tabular-nums">
          <thead>
            <tr className="bg-[#161A24] text-slate-400">
              <th className="border border-white/[0.07] px-2 py-1.5 text-center w-8">#</th>
              {(currentSheet.columns || []).map((col) => (
                <th
                  key={col}
                  className="border border-white/[0.07] px-2.5 py-1.5 text-center font-semibold"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(currentSheet.rows || []).map((row, rIdx) => (
              <tr
                key={rIdx}
                className={
                  rIdx === 0
                    ? 'bg-[#1B202C] text-white font-semibold'
                    : rIdx % 2 === 1
                    ? 'bg-[#10131B] text-slate-200'
                    : 'bg-[#0C0E14] text-slate-200'
                }
              >
                <td className="border border-white/[0.06] px-2 py-1.5 text-center text-slate-500">
                  {rIdx + 1}
                </td>
                {row.map((cell, cIdx) => {
                  const isFormula = typeof cell === 'string' && cell.startsWith('=')
                  return (
                    <td
                      key={cIdx}
                      className={`border border-white/[0.06] px-2.5 py-1.5 ${
                        cIdx > 0 ? 'text-right' : 'text-left'
                      } ${isFormula ? 'text-emerald-400 font-semibold' : ''}`}
                    >
                      {cell}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
