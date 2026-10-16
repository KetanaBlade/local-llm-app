import React, { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import {
  Cpu,
  Lock,
  Globe,
  Smartphone,
  Plus,
  Trash2,
  Send,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Code2,
  Download,
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  Loader2,
  PanelLeft,
  ExternalLink,
  X,
  ArrowUpRight,
  Eye,
  FolderOpen,
  Sparkles,
} from 'lucide-react'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export default function App() {
  const [systemStatus, setSystemStatus] = useState(null)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [artifacts, setArtifacts] = useState([])
  const [selectedArtifact, setSelectedArtifact] = useState(null)
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)
  const [appViewMode, setAppViewMode] = useState('preview')

  const [selectedModel, setSelectedModel] = useState('qwen2.5-coder:7b')
  const [promptInput, setPromptInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')

  // Panels & Modals (File Preview Panel stays closed until a file is created or clicked!)
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true)
  const [filePanelOpen, setFilePanelOpen] = useState(false)
  const [hwModalOpen, setHwModalOpen] = useState(false)
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [mobileModalOpen, setMobileModalOpen] = useState(false)

  // Model download state
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
        setArtifacts(data.artifacts || [])
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
      }
    } catch (e) {
      console.error(e)
    }
  }

  const startNewChat = () => {
    setActiveConvId(null)
    setMessages([])
    setPromptInput('')
  }

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation()
    await fetch(`/api/conversations/${convId}`, { method: 'DELETE' })
    if (activeConvId === convId) {
      startNewChat()
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

  const handleSendPrompt = async (overrideText) => {
    const text = (overrideText ?? promptInput).trim()
    if (!text || isStreaming) return
    if (!overrideText) setPromptInput('')

    setIsStreaming(true)
    setStreamStatus(`Running on ${selectedModel}...`)

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
          mode: 'agent',
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
            setStreamStatus(`Running tool: ${ev.tool.name}...`)
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? { ...m, tool_calls: [...(m.tool_calls || []), ev.tool] }
                  : m
              )
            )
          } else if (ev.type === 'tool_end') {
            setStreamStatus('Writing response...')
            const newArts = ev.artifacts || []
            if (newArts.length > 0) {
              setSelectedArtifact(newArts[0])
              setActiveSheetIdx(0)
              setFilePanelOpen(true)
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
            setStreamStatus('Thinking...')
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
  const isOfflineOnly = settings?.air_gap_mode !== false

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0A0B0E] text-[#F3F4F6] select-none overflow-hidden">
      {/* SIMPLIFIED, CLEAN TOP HEADER BAR */}
      <header className="h-14 shrink-0 border-b border-white/[0.075] bg-[#0D0F14] px-3 lg:px-5 flex items-center justify-between gap-3 z-30">
        {/* Left: Sidebar Toggle & Brand */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setLeftSidebarOpen((v) => !v)}
            aria-label="Toggle Chat History Sidebar"
            className="h-9 w-9 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] flex items-center justify-center text-slate-300 transition"
            title="Show/Hide Chat History"
          >
            <PanelLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-md bg-[#D97757]/15 border border-[#D97757]/40 flex items-center justify-center">
              <div className="h-2.5 w-2.5 rounded-sm bg-[#D97757]" />
            </div>
            <span className="font-semibold tracking-tight text-sm text-white">
              Local AI Studio
            </span>
          </div>
        </div>

        {/* Right: Hardware Info, Phone Wi-Fi Link & Created Files Drawer */}
        <div className="flex items-center gap-2">
          {/* Hardware Status Button */}
          <button
            onClick={() => setHwModalOpen(true)}
            className="h-9 px-3 rounded-lg border border-white/[0.08] bg-[#13161E] hover:bg-[#191D28] flex items-center gap-2 text-xs transition"
            title="View PC / Laptop Hardware Settings"
          >
            <Cpu className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="font-mono text-[11px] text-slate-200 tabular-nums hidden sm:inline">
              {hw ? hw.short_badge : 'Checking Hardware...'}
            </span>
          </button>

          {/* Phone Wi-Fi Connect Button */}
          <button
            onClick={() => setMobileModalOpen(true)}
            className="h-9 px-3 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-slate-200 flex items-center gap-1.5 text-xs transition"
            title="Open on your Phone over Home Wi-Fi"
          >
            <Smartphone className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden md:inline font-medium">Use on Phone</span>
          </button>

          {/* Created Files Drawer Button (Only highlights when files exist) */}
          <button
            onClick={() => {
              if (!selectedArtifact && artifacts.length > 0) {
                setSelectedArtifact(artifacts[0])
              }
              setFilePanelOpen((v) => !v)
            }}
            className={`h-9 px-3 rounded-lg border flex items-center gap-2 text-xs transition ${
              filePanelOpen
                ? 'border-[#D97757]/50 bg-[#D97757]/15 text-white'
                : 'border-white/[0.08] bg-[#14171F] text-slate-300 hover:bg-[#1B1F2A]'
            }`}
            title="View & Download Files Created by the AI"
          >
            <FolderOpen className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden sm:inline font-medium">Created Files</span>
            {artifacts.length > 0 && (
              <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-black/40 text-slate-200 tabular-nums">
                {artifacts.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <div className="flex-1 flex min-h-0 relative overflow-hidden">
        {/* LEFT SIDEBAR: PURELY YOUR CHATS */}
        {leftSidebarOpen && (
          <aside className="w-64 shrink-0 border-r border-white/[0.075] bg-[#0D0F14] flex flex-col justify-between z-20 select-none">
            <div className="p-3 space-y-4 overflow-y-auto flex-1">
              <button
                onClick={startNewChat}
                className="w-full h-10 px-3 rounded-lg bg-[#D97757] hover:bg-[#E4886A] text-white font-medium text-xs flex items-center gap-2 shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                <span>New Chat</span>
              </button>

              <div>
                <div className="px-1.5 mb-2 flex items-center justify-between">
                  <span className="text-[11px] font-medium text-slate-400">
                    Your Conversations
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 tabular-nums">
                    {conversations.length}
                  </span>
                </div>

                {conversations.length === 0 ? (
                  <div className="px-3 py-5 text-xs text-slate-500 border border-dashed border-white/[0.06] rounded-lg text-center leading-relaxed">
                    Your chat history is saved privately on your computer.
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
                          aria-label="Delete chat"
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

            {/* Simple Bottom Hardware Status Bar */}
            {hw && (
              <div
                onClick={() => setHwModalOpen(true)}
                className="p-3 border-t border-white/[0.075] bg-[#0B0D12] hover:bg-[#11141C] cursor-pointer transition"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-300 mb-1">
                  <span className="truncate font-medium">{hw.gpu?.name}</span>
                  <span className="text-[10px] font-mono text-[#10B981]">LOCAL GPU</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400 tabular-nums">
                  {hw.gpu.vram_free_gb} GB free of {hw.gpu.vram_total_gb} GB memory
                </div>
              </div>
            )}
          </aside>
        )}

        {/* CENTER STAGE: CHAT & UNIFIED INPUT BOX */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#0A0B0E] select-text">
          <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-10 py-6">
            {messages.length === 0 ? (
              <div className="max-w-2xl mx-auto py-8 sm:py-12 space-y-8">
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs text-slate-300">
                    <span className="h-2 w-2 rounded-full bg-[#10B981]" />
                    <span>Running privately on your {hw?.gpu?.name || 'computer'}</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
                    Ask a question or ask me to create a file.
                  </h1>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Chat normally like Gemini, switch between local AI models anytime in the
                    box below, or ask me to create real{' '}
                    <strong className="text-slate-200">Excel spreadsheets (.xlsx)</strong>,{' '}
                    <strong className="text-slate-200">PDF / Word documents</strong>,{' '}
                    <strong className="text-slate-200">charts & pictures</strong>, or{' '}
                    <strong className="text-slate-200">interactive mini-apps</strong>.
                  </p>
                </div>

                {/* 4 Clear Example Prompts */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    {
                      title: 'Make a Custom Excel Spreadsheet',
                      subtitle: 'Creates a real .xlsx file with =SUM() formulas',
                      icon: FileSpreadsheet,
                      prompt:
                        'Create an Excel spreadsheet for a 2026 Monthly Budget with columns for Category, Q1, Q2, Q3, Q4, and Annual Total using =SUM formulas.',
                    },
                    {
                      title: 'Create a PDF or Word Document',
                      subtitle: 'Writes and formats a downloadable report',
                      icon: FileText,
                      prompt:
                        'Create a PDF document titled "Home Office & Local AI Setup Guide" with 3 structured sections and bullet points.',
                    },
                    {
                      title: 'Build an Interactive Mini-App',
                      subtitle: 'Writes a working calculator or tool you can use right here',
                      icon: Code2,
                      prompt:
                        'Build an interactive Loan & Monthly Payment Calculator web app with sliders for loan amount, interest rate, and term.',
                    },
                    {
                      title: 'Create a Chart or Visual Graphic',
                      subtitle: 'Generates a high-resolution chart or animation',
                      icon: ImageIcon,
                      prompt:
                        'Generate a bar chart comparing monthly expenses: Housing $1800, Food $650, Utilities $240, Savings $900.',
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
                      setFilePanelOpen(true)
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

          {/* UNIFIED CHAT COMPOSER (Single Place for Model Picker + Privacy Toggle!) */}
          <div className="p-3 sm:p-4 border-t border-white/[0.075] bg-[#0B0D12]">
            <div className="max-w-3xl mx-auto">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSendPrompt()
                }}
                className="rounded-xl bg-[#12151E] border border-white/[0.1] focus-within:border-[#D97757]/60 transition p-2.5 space-y-2"
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
                  placeholder="Ask any question, or ask me to make an Excel sheet, PDF, Word doc, chart, picture, or app..."
                  className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none px-1.5 py-1"
                />

                {/* Bottom Controls Bar Inside Composer: Model Picker + Download Models + Offline/Web Toggle + Send */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1.5 border-t border-white/[0.06]">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* THE SINGLE MODEL SELECTOR */}
                    <div className="relative">
                      <select
                        aria-label="Choose AI Model"
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                        className="h-8 pl-2.5 pr-7 rounded-lg bg-[#191D28] hover:bg-[#1F2432] border border-white/[0.1] text-xs font-mono text-slate-100 appearance-none cursor-pointer transition"
                        title="Switch AI model anytime (even mid-conversation!)"
                      >
                        {installedModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            Model: {m.name} ({m.size_gb} GB)
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
                    </div>

                    {/* Button to Download / Try More Local Models */}
                    <button
                      type="button"
                      onClick={() => setModelModalOpen(true)}
                      className="h-8 px-2.5 rounded-lg border border-white/[0.08] bg-[#161A24] hover:bg-[#1D2230] text-xs text-slate-300 flex items-center gap-1.5 transition"
                      title="Download or compare other local AI models"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-[#D97757]" />
                      <span>+ More Models</span>
                    </button>

                    {/* Plain-English Privacy / Internet Switch */}
                    <button
                      type="button"
                      onClick={() =>
                        handleUpdateSetting({ air_gap_mode: !isOfflineOnly })
                      }
                      className={`h-8 px-2.5 rounded-lg border text-xs flex items-center gap-1.5 transition ${
                        isOfflineOnly
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                          : 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                      }`}
                      title={
                        isOfflineOnly
                          ? '100% Offline: The AI cannot touch the internet. Click to allow DuckDuckGo web search.'
                          : 'Web Search On: The AI runs on your PC but can search DuckDuckGo when needed. Click to lock Offline.'
                      }
                    >
                      {isOfflineOnly ? (
                        <>
                          <Lock className="w-3.5 h-3.5" />
                          <span>Offline Only (Private)</span>
                        </>
                      ) : (
                        <>
                          <Globe className="w-3.5 h-3.5" />
                          <span>Web Search Allowed</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Send Button */}
                  <button
                    type="submit"
                    disabled={isStreaming || !promptInput.trim()}
                    className="h-8 px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white font-medium text-xs flex items-center gap-1.5 transition"
                  >
                    {isStreaming ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        <span>Send</span>
                        <Send className="w-3 h-3" />
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </main>

        {/* RIGHT PANEL: CREATED FILES PREVIEW & DOWNLOADS (Only open when viewing a file!) */}
        {filePanelOpen && (
          <aside className="w-full sm:w-[440px] xl:w-[520px] shrink-0 border-l border-white/[0.075] bg-[#0D0F14] flex flex-col z-20">
            <div className="px-4 py-3 border-b border-white/[0.075] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-[#D97757]" />
                <span className="text-xs font-semibold text-white">
                  File Preview & Downloads
                </span>
              </div>
              <button
                onClick={() => setFilePanelOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
                title="Close File Preview"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              {selectedArtifact ? (
                <div className="flex-1 flex flex-col min-h-0">
                  {/* File Action Bar */}
                  <div className="px-4 py-2.5 bg-[#12151D] border-b border-white/[0.07] flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-white truncate">
                        {selectedArtifact.title}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 truncate tabular-nums">
                        {selectedArtifact.filename} ({(selectedArtifact.size_bytes / 1024).toFixed(1)} KB)
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {selectedArtifact.category === 'webapp' && (
                        <button
                          onClick={() =>
                            setAppViewMode((m) => (m === 'preview' ? 'code' : 'preview'))
                          }
                          className="h-8 px-2.5 rounded-md border border-white/[0.1] bg-[#181C26] text-xs text-slate-200 hover:bg-[#202634]"
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
                        <span>Download File</span>
                      </a>
                    </div>
                  </div>

                  {/* Live File Preview */}
                  <div className="flex-1 overflow-auto p-4 bg-[#0A0B0E]">
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
                          <div className="px-3 py-1.5 bg-[#14171F] border-b border-white/[0.07] flex items-center justify-between text-[11px] text-slate-400">
                            <span>Interactive App Preview</span>
                            <a
                              href={selectedArtifact.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#D97757] hover:underline flex items-center gap-1"
                            >
                              <span>Open in Full Browser Tab</span>
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
                          {selectedArtifact.preview_data?.code_snippet || 'HTML Source'}
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
                      <div className="rounded-lg overflow-hidden border border-white/[0.09] bg-[#10131A] flex items-center justify-center p-2">
                        <img
                          src={selectedArtifact.url}
                          alt={selectedArtifact.title}
                          className="max-w-full rounded"
                        />
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
                  <FolderOpen className="w-8 h-8 mb-2 text-slate-600" />
                  <p className="text-xs leading-relaxed">
                    No files created yet. Ask the AI in chat to make an Excel spreadsheet,
                    PDF report, chart, or web app and it will open here automatically!
                  </p>
                </div>
              )}

              {/* List of Created Files */}
              {artifacts.length > 0 && (
                <div className="h-40 shrink-0 border-t border-white/[0.075] bg-[#0B0D12] p-3 overflow-y-auto">
                  <div className="text-[11px] font-medium text-slate-400 mb-2">
                    All Created Files ({artifacts.length})
                  </div>
                  <div className="space-y-1">
                    {artifacts.map((art) => (
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
              )}
            </div>
          </aside>
        )}
      </div>

      {/* HARDWARE SETTINGS MODAL */}
      {hwModalOpen && hw && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Cpu className="w-5 h-5 text-[#D97757]" />
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    Hardware Auto-Tuner (Desktop & Laptop Portability)
                  </h2>
                  <p className="text-xs text-slate-400">
                    Automatically detects whether you are on your RTX 4070 SUPER Desktop or Intel Core Ultra 258V Laptop
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
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-2">
                  Hardware Profile Mode
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {[
                    {
                      id: 'auto',
                      title: 'Auto-Detect (Recommended)',
                      desc: 'Automatically configures for whichever PC/Laptop is running',
                    },
                    {
                      id: 'desktop_rtx4070s',
                      title: 'Desktop: RTX 4070 SUPER',
                      desc: '12GB Dedicated VRAM + 64GB RAM',
                    },
                    {
                      id: 'laptop_ultra_258v',
                      title: 'Laptop: Core Ultra 258V',
                      desc: 'Intel Arc 140V + NPU + 32GB Shared RAM',
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

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[11px] text-slate-400">Graphics / GPU</div>
                  <div className="text-xs font-semibold text-white mt-1">
                    {hw.gpu.name}
                  </div>
                  <div className="text-[11px] font-mono text-[#D97757] mt-1 tabular-nums">
                    {hw.gpu.vram_free_gb} GB Free / {hw.gpu.vram_total_gb} GB
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[11px] text-slate-400">NPU Accelerator</div>
                  <div className="text-xs font-semibold text-white mt-1">
                    {hw.npu.name}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">{hw.npu.role}</div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#141821] border border-white/[0.07]">
                  <div className="text-[11px] text-slate-400">Processor & System RAM</div>
                  <div className="text-xs font-semibold text-white mt-1 truncate">
                    {hw.cpu.name}
                  </div>
                  <div className="text-[11px] font-mono text-emerald-400 mt-1 tabular-nums">
                    {hw.memory.ram_total_gb} GB Total RAM
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[#0D0F14] border border-white/[0.08] space-y-2">
                <div className="text-xs font-semibold text-white">
                  How the App Is Tuned for This Machine
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {hw.tuning.explanation}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODEL HUB MODAL (Download & Switch Local Models) */}
      {modelModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Download & Switch Local AI Models
                </h2>
                <p className="text-xs text-slate-400">
                  Switch models anytime—even in the middle of a conversation.
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
                      Downloading <strong>{pullingModel}</strong>: {pullProgress.status}
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

              <div>
                <div className="text-xs font-medium text-slate-300 mb-2">
                  Recommended Models for {hw?.profile_label}
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
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            Speed & Memory Fit: {rec.fit}
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
                              {selectedModel === rec.id ? 'Selected' : 'Switch to This'}
                            </button>
                          ) : (
                            <button
                              disabled={Boolean(pullingModel)}
                              onClick={() => handlePullModel(rec.id)}
                              className="h-8 px-3 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white text-xs font-medium transition"
                            >
                              Download ({rec.size_gb} GB)
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="pt-3 border-t border-white/[0.08]">
                <label className="block text-xs text-slate-300 mb-1.5">
                  Or Download Any Model from Ollama (e.g. <code className="text-slate-200">gemma2:9b</code>, <code className="text-slate-200">phi4:14b</code>)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customModelName}
                    onChange={(e) => setCustomModelName(e.target.value)}
                    placeholder="Enter model name (e.g. gemma2:9b)..."
                    className="flex-1 h-9 px-3 rounded-lg bg-[#0D0F14] border border-white/[0.1] text-xs font-mono text-white"
                  />
                  <button
                    disabled={!customModelName.trim() || Boolean(pullingModel)}
                    onClick={() => handlePullModel(customModelName.trim())}
                    className="h-9 px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white text-xs font-medium"
                  >
                    Download
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MOBILE PHONE WI-FI ACCESS MODAL */}
      {mobileModalOpen && network && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-[#D97757]" />
                <h2 className="text-sm font-semibold text-white">
                  Use on Your Phone (Home Wi-Fi)
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
                Make sure your phone is connected to your home Wi-Fi, then scan this QR
                code with your phone camera (or type the address below into Safari/Chrome):
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
            className={`text-[11px] font-mono px-2 py-0.5 rounded ${
              isUser
                ? 'bg-white/[0.08] text-slate-200'
                : 'bg-[#D97757]/15 text-[#D97757] border border-[#D97757]/30'
            }`}
          >
            {isUser ? 'You' : `Model: ${msg.model || 'Local AI'}`}
          </span>
        </div>
        {!isUser && msg.tokens_per_sec > 0 && (
          <span className="text-[11px] font-mono text-slate-400 tabular-nums">
            {msg.tokens_per_sec} tokens/sec
          </span>
        )}
      </div>

      {/* Collapsible Reasoning Trace */}
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
            <span>Show AI Thinking Process</span>
          </button>
          {thinkOpen && (
            <div className="mt-1.5 p-3 rounded-lg bg-[#090B0E] border border-white/[0.06] text-xs font-mono text-slate-400 whitespace-pre-wrap">
              {msg.thinking}
            </div>
          )}
        </div>
      )}

      {/* Collapsible Action / Tool Steps */}
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
                  {tc.duration_ms ? `${tc.duration_ms}ms` : 'running...'}
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

      {/* Message Text */}
      {msg.content && (
        <div
          className="prose-studio"
          dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }}
        />
      )}

      {/* Inline File Cards (Click to Preview or Download) */}
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
                  {art.filename} ({(art.size_bytes / 1024).toFixed(1)} KB)
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[11px] font-medium text-[#D97757] flex items-center gap-1">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Preview / Download</span>
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
    spreadsheet: { label: 'EXCEL', cls: 'bg-emerald-500/20 text-emerald-300' },
    document: { label: 'DOC', cls: 'bg-sky-500/20 text-sky-300' },
    webapp: { label: 'APP', cls: 'bg-[#D97757]/20 text-[#D97757]' },
    image: { label: 'IMAGE', cls: 'bg-amber-500/20 text-amber-300' },
    video: { label: 'VIDEO', cls: 'bg-rose-500/20 text-rose-300' },
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
        Excel file ready. Click <strong>Download File</strong> above to open in Excel.
      </div>
    )
  }
  const currentSheet = sheets[activeSheetIdx] || sheets[0]

  return (
    <div className="space-y-2.5">
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
