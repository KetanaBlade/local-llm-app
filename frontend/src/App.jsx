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
  BookOpen,
  Moon,
  Power,
  Square,
  Gamepad2,
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
  const [chatContext, setChatContext] = useState('')
  const [contextExpanded, setContextExpanded] = useState(false)
  const [contextSavedBadge, setContextSavedBadge] = useState(false)

  const [artifacts, setArtifacts] = useState([])
  const [selectedArtifact, setSelectedArtifact] = useState(null)
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)
  const [appViewMode, setAppViewMode] = useState('preview')

  // Default to conversational model (llama3.2:3b) rather than a coding model
  const [selectedModel, setSelectedModel] = useState('llama3.2:3b')
  const [promptInput, setPromptInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')

  // Start left sidebar closed on mobile screens (< 1024px) so mobile layout is clean
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(
    typeof window !== 'undefined' ? window.innerWidth >= 1024 : true
  )
  const [filePanelOpen, setFilePanelOpen] = useState(false)
  const [hwModalOpen, setHwModalOpen] = useState(false)
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [mobileModalOpen, setMobileModalOpen] = useState(false)

  // Model download & VRAM flush state
  const [pullingModel, setPullingModel] = useState(null)
  const [pullProgress, setPullProgress] = useState(null)
  const [customModelName, setCustomModelName] = useState('')
  const [flushingVram, setFlushingVram] = useState(false)

  // Sleep mode (0 MB VRAM) & graceful shutdown state
  const [isSleeping, setIsSleeping] = useState(false)
  const [sleepingLoading, setSleepingLoading] = useState(false)
  const [shutdownModalOpen, setShutdownModalOpen] = useState(false)
  const [isShutdown, setIsShutdown] = useState(false)

  const toggleSleepMode = async () => {
    setSleepingLoading(true)
    try {
      const res = await fetch('/api/system/sleep', { method: 'POST' })
      if (res.ok) {
        setIsSleeping(true)
        await fetchSystemStatus()
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSleepingLoading(false)
    }
  }

  const handleShutdown = async () => {
    try {
      await fetch('/api/system/shutdown', { method: 'POST' })
    } catch (e) {
      // Expected as backend stops
    }
    setIsShutdown(true)
    setShutdownModalOpen(false)
  }

  const chatScrollContainerRef = useRef(null)
  const latestUserMsgRef = useRef(null)
  const abortControllerRef = useRef(null)

  const handleStopResponse = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
    setStreamStatus('Response stopped.')
    try {
      await fetch('/api/chat/stop', { method: 'POST' })
      await fetchSystemStatus()
    } catch (e) {
      console.error('Stop request failed:', e)
    }
  }

  const fetchSystemStatus = async () => {
    try {
      const r = await fetch('/api/system/status')
      if (r.ok) {
        const data = await r.json()
        setSystemStatus(data)
        if (data.installed_models?.length > 0) {
          const installedIds = data.installed_models.map((m) => m.id)
          if (!installedIds.includes(selectedModel)) {
            // Prefer conversational model first
            const convModel =
              installedIds.find((id) => !id.toLowerCase().includes('coder')) ||
              installedIds[0]
            setSelectedModel(convModel)
          }
        }
      }
    } catch (e) {
      console.error('Status check failed:', e)
    }
  }

  const handleFlushVram = async (exceptModel = null) => {
    setFlushingVram(true)
    try {
      const r = await fetch('/api/models/flush', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ except_model: exceptModel }),
      })
      if (r.ok) {
        const data = await r.json()
        setSystemStatus((prev) =>
          prev
            ? {
                ...prev,
                hardware: data.hardware || prev.hardware,
                running_models: data.running_models || [],
              }
            : prev
        )
      }
    } catch (e) {
      console.error('VRAM flush failed:', e)
    } finally {
      setFlushingVram(false)
    }
  }

  const handleSwitchModel = async (newModel) => {
    setSelectedModel(newModel)
    await handleFlushVram(newModel)
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

  const loadConversation = async (convId) => {
    try {
      const r = await fetch(`/api/conversations/${convId}`)
      if (r.ok) {
        const data = await r.json()
        setActiveConvId(data.id)
        setMessages(data.messages || [])
        setChatContext(data.context || '')
        setContextExpanded(Boolean(data.context))
        if (typeof window !== 'undefined' && window.innerWidth < 1024) {
          setLeftSidebarOpen(false)
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  const startNewChat = () => {
    setActiveConvId(null)
    setMessages([])
    setChatContext('')
    setContextExpanded(true)
    setPromptInput('')
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      setLeftSidebarOpen(false)
    }
    // Automatically flush GPU VRAM cache whenever starting a new chat
    handleFlushVram(null)
  }

  const handleSaveContextOnActiveChat = async (newCtx) => {
    setChatContext(newCtx)
    if (activeConvId) {
      await fetch(`/api/conversations/${activeConvId}/context`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: newCtx }),
      })
      setContextSavedBadge(true)
      setTimeout(() => setContextSavedBadge(false), 1800)
    }
  }

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation()
    await fetch(`/api/conversations/${convId}`, { method: 'DELETE' })
    if (activeConvId === convId) {
      startNewChat()
    } else {
      await fetchSystemStatus()
    }
    await fetchConversations()
    await fetchArtifacts()
  }

  const handleDeleteArtifact = async (e, artId) => {
    if (e) e.stopPropagation()
    await fetch(`/api/artifacts/${artId}`, { method: 'DELETE' })
    if (selectedArtifact?.id === artId) {
      setSelectedArtifact(null)
    }
    // Also remove the deleted artifact from any currently displayed message cards in state
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        artifacts: (m.artifacts || []).filter((a) => a.id !== artId),
      }))
    )
    await fetchArtifacts()
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

  const handleSendPrompt = async (overrideText) => {
    const text = (overrideText ?? promptInput).trim()
    if (!text || isStreaming) return
    if (!overrideText) setPromptInput('')

    if (isSleeping) {
      setIsSleeping(false)
    }

    const abortController = new AbortController()
    abortControllerRef.current = abortController

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

    // Scroll ONCE to bring the newly submitted prompt to the top of view—never yank scroll downward during streaming!
    setTimeout(() => {
      latestUserMsgRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 60)

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify({
          conversation_id: activeConvId,
          prompt: text,
          model: selectedModel,
          mode: 'agent',
          context: chatContext,
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
            const toolEngine = ev.tool?.engine_label;
            const toolSummary = ev.tool?.summary;
            let statusText = `Running tool: ${ev.tool.name}...`;
            if (ev.tool.name === 'generate_visual_media') {
              if (toolEngine) {
                statusText = `Rendering image on local GPU (${toolEngine.split('(')[0].trim()})...`;
              } else if (toolSummary) {
                statusText = toolSummary;
              } else {
                const p = (ev.tool?.arguments?.prompt || '').toLowerCase();
                const st = (ev.tool?.arguments?.style || '').toLowerCase();
                const isPhoto = /photo|realistic|dslr|cyberrealistic/i.test(p) || st === 'photorealistic';
                const isAnime = /anime|manga|waifu|meina/i.test(p) || st === 'anime';
                const eng = isPhoto ? 'CyberRealistic V8' : isAnime ? 'MeinaMix V11' : 'DreamShaper 8';
                statusText = `Rendering image on local GPU (${eng})...`;
              }
            } else if (toolSummary) {
              statusText = toolSummary;
            }
            setStreamStatus(statusText);
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
      if (err.name === 'AbortError') {
        console.log('Chat generation stopped by user.')
      } else {
        console.error('Stream error:', err)
      }
    } finally {
      abortControllerRef.current = null
      setIsStreaming(false)
      setStreamStatus('')
    }
  }

  const hw = systemStatus?.hardware
  const settings = systemStatus?.settings
  const installedModels = systemStatus?.installed_models || []
  const network = systemStatus?.network
  const isOfflineOnly = settings?.air_gap_mode !== false

  if (isShutdown) {
    return (
      <div className="fixed inset-0 h-[100dvh] w-full flex flex-col items-center justify-center bg-[#0A0B0E] text-[#F3F4F6] p-6 text-center select-none">
        <div className="h-16 w-16 rounded-2xl bg-red-500/10 border border-red-500/25 flex items-center justify-center mb-5 text-red-400">
          <Power className="w-8 h-8" />
        </div>
        <h1 className="text-xl sm:text-2xl font-semibold text-white tracking-tight mb-2">
          Local AI Studio is Offline
        </h1>
        <p className="text-sm text-slate-400 max-w-md leading-relaxed mb-6">
          The local server has stopped and all VRAM and memory have been completely released.
          You can safely close this window, or launch the desktop shortcut anytime to start it back up.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] text-xs font-medium text-slate-200 transition"
        >
          Check if Server Restarted
        </button>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 h-[100dvh] w-full flex flex-col bg-[#0A0B0E] text-[#F3F4F6] select-none overflow-hidden">
      {/* PINNED TOP HEADER BAR (Never scrolls out of view on mobile) */}
      <header className="h-13 sm:h-14 shrink-0 border-b border-white/[0.075] bg-[#0D0F14] px-3 lg:px-5 flex items-center justify-between gap-2 z-30">
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            onClick={() => setLeftSidebarOpen((v) => !v)}
            aria-label="Toggle Chat History Sidebar"
            className="h-9 w-9 shrink-0 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] flex items-center justify-center text-slate-300 transition"
            title="Show/Hide Chat History"
          >
            <PanelLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2 min-w-0">
            <div className="h-6 w-6 shrink-0 rounded-md bg-[#D97757]/15 border border-[#D97757]/40 flex items-center justify-center">
              <div className="h-2 w-2 rounded-sm bg-[#D97757]" />
            </div>
            <span className="font-semibold tracking-tight text-sm text-white truncate">
              Local AI Studio
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <button
            onClick={() => setHwModalOpen(true)}
            className="h-9 px-2.5 sm:px-3 rounded-lg border border-white/[0.08] bg-[#13161E] hover:bg-[#191D28] flex items-center gap-1.5 text-xs transition"
            title="View PC / Laptop Hardware Settings"
          >
            <Cpu className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="font-mono text-[11px] text-slate-200 tabular-nums hidden md:inline">
              {hw ? hw.short_badge : 'Hardware'}
            </span>
          </button>

          <button
            onClick={() => setMobileModalOpen(true)}
            className="h-9 px-2.5 sm:px-3 rounded-lg border border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-slate-200 flex items-center gap-1.5 text-xs transition"
            title="Open on your Phone over Home Wi-Fi"
          >
            <Smartphone className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden md:inline font-medium">Phone Link</span>
          </button>

          <button
            onClick={() => {
              if (!selectedArtifact && artifacts.length > 0) {
                setSelectedArtifact(artifacts[0])
              }
              setFilePanelOpen((v) => !v)
            }}
            className={`h-9 px-2.5 sm:px-3 rounded-lg border flex items-center gap-1.5 text-xs transition ${
              filePanelOpen
                ? 'border-[#D97757]/50 bg-[#D97757]/15 text-white'
                : 'border-white/[0.08] bg-[#14171F] text-slate-300 hover:bg-[#1B1F2A]'
            }`}
            title="View, Download, or Delete Created Files"
          >
            <FolderOpen className="w-3.5 h-3.5 text-[#D97757]" />
            <span className="hidden sm:inline font-medium">Files</span>
            {artifacts.length > 0 && (
              <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-black/40 text-slate-200 tabular-nums">
                {artifacts.length}
              </span>
            )}
          </button>

          {/* GAMING MODE / 0 GPU VRAM TOGGLE */}
          <button
            onClick={() => handleUpdateSetting({ gaming_mode: !settings?.gaming_mode })}
            className={`h-9 px-2.5 sm:px-3 rounded-lg border flex items-center gap-1.5 text-xs transition ${
              settings?.gaming_mode
                ? 'border-amber-500/50 bg-amber-500/15 text-amber-200'
                : 'border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-slate-300'
            }`}
            title="Gaming Mode: Offloads LLM models 100% to your 64GB System RAM so your RTX 4070 SUPER GPU retains 100% VRAM and 0% FPS drops for games."
          >
            <Gamepad2 className={`w-3.5 h-3.5 ${settings?.gaming_mode ? 'text-amber-400' : 'text-slate-400'}`} />
            <span className="hidden xl:inline font-medium">
              {settings?.gaming_mode ? 'Gaming: 0 VRAM' : 'Gaming Mode'}
            </span>
          </button>

          {/* SLEEP MODE / 0 MB VRAM BUTTON */}
          <button
            onClick={toggleSleepMode}
            disabled={sleepingLoading}
            className={`h-9 px-2.5 sm:px-3 rounded-lg border flex items-center gap-1.5 text-xs transition ${
              isSleeping
                ? 'border-cyan-500/50 bg-cyan-500/15 text-cyan-200'
                : 'border-white/[0.08] bg-[#14171F] hover:bg-[#1B1F2A] text-slate-300'
            }`}
            title="Sleep Mode: Evict 100% of VRAM so your GPU is totally free for games or other apps. Wakes automatically on your next prompt."
          >
            {sleepingLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
            ) : (
              <Moon className={`w-3.5 h-3.5 ${isSleeping ? 'text-cyan-400 fill-cyan-400' : 'text-slate-400'}`} />
            )}
            <span className="hidden xl:inline font-medium">
              {isSleeping ? '0 MB VRAM (Asleep)' : 'Sleep (0 VRAM)'}
            </span>
          </button>

          {/* POWER OFF / QUIT SERVER BUTTON */}
          <button
            onClick={() => setShutdownModalOpen(true)}
            className="h-9 w-9 rounded-lg border border-red-500/20 bg-red-500/10 hover:bg-red-500/25 text-red-400 flex items-center justify-center transition shrink-0"
            title="Close Server: Cleanly terminates the backend process and releases all system resources."
          >
            <Power className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* MAIN WORKSPACE AREA */}
      <div className="flex-1 flex min-h-0 relative overflow-hidden">
        {/* Mobile Backdrop for Left Sidebar */}
        {leftSidebarOpen && (
          <div
            onClick={() => setLeftSidebarOpen(false)}
            className="fixed inset-0 bg-black/60 z-30 lg:hidden"
          />
        )}

        {/* LEFT SIDEBAR: YOUR CHATS */}
        {leftSidebarOpen && (
          <aside className="fixed lg:static inset-y-0 left-0 w-64 shrink-0 border-r border-white/[0.075] bg-[#0D0F14] flex flex-col justify-between z-40 select-none">
            <div className="p-3 space-y-4 overflow-y-auto flex-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={startNewChat}
                  className="flex-1 h-10 px-3 rounded-lg bg-[#D97757] hover:bg-[#E4886A] text-white font-medium text-xs flex items-center gap-2 shadow-sm transition"
                >
                  <Plus className="w-4 h-4" />
                  <span>New Chat</span>
                </button>
                <button
                  onClick={() => setLeftSidebarOpen(false)}
                  className="lg:hidden h-10 w-10 rounded-lg border border-white/[0.08] bg-[#14171F] flex items-center justify-center text-slate-300"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

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
                    Your chat history is saved privately on your computer. Deleting a chat
                    permanently wipes it and its files from disk.
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
                          aria-label="Permanently obliterate chat"
                          title="Permanently delete chat & its files from database and disk"
                          className="text-slate-500 hover:text-rose-400 p-1 transition shrink-0"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {hw && (
              <div className="p-3 border-t border-white/[0.075] bg-[#0B0D12] space-y-2">
                <div
                  onClick={() => setHwModalOpen(true)}
                  className="cursor-pointer hover:opacity-90 transition"
                >
                  <div className="flex items-center justify-between text-[11px] text-slate-300 mb-0.5">
                    <span className="truncate font-medium">{hw.gpu?.name}</span>
                    <span className="text-[10px] font-mono text-[#10B981]">LOCAL GPU</span>
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 tabular-nums">
                    {hw.gpu.vram_free_gb} GB free of {hw.gpu.vram_total_gb} GB memory
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2 pt-1 border-t border-white/[0.06]">
                  <span className="text-[10px] font-mono text-slate-500 truncate">
                    {systemStatus?.running_models?.length > 0
                      ? `Loaded: ${systemStatus.running_models.map((m) => m.name).join(', ')}`
                      : 'VRAM cache idle'}
                  </span>
                  <button
                    type="button"
                    disabled={flushingVram}
                    onClick={() => handleFlushVram(null)}
                    className="px-2 py-1 rounded bg-white/[0.06] hover:bg-[#D97757]/20 hover:text-[#D97757] text-[10px] font-mono text-slate-300 border border-white/[0.08] shrink-0 transition"
                    title="Unload all models from GPU VRAM immediately"
                  >
                    {flushingVram ? 'Clearing...' : 'Clear VRAM'}
                  </button>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* CENTER STAGE: BACKGROUND CONTEXT + CHAT STREAM + COMPOSER */}
        <main className="flex-1 flex flex-col min-w-0 min-h-0 bg-[#0A0B0E] select-text">
          <div
            ref={chatScrollContainerRef}
            className="flex-1 overflow-y-auto px-3 sm:px-6 lg:px-10 py-4 sm:py-6"
          >
            <div className="max-w-3xl mx-auto space-y-5">
              {/* BACKGROUND CONTEXT BOX AT THE START OF EVERY CHAT */}
              <div className="rounded-xl bg-[#10131B] border border-white/[0.08] overflow-hidden">
                <div
                  onClick={() => setContextExpanded((v) => !v)}
                  className="px-3.5 py-2.5 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <BookOpen className="w-4 h-4 text-[#D97757] shrink-0" />
                    <span className="text-xs font-semibold text-slate-200 truncate">
                      Background Context & Instructions
                    </span>
                    {chatContext.trim() && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shrink-0">
                        Active
                      </span>
                    )}
                    {contextSavedBadge && (
                      <span className="text-[10px] font-mono text-[#10B981] shrink-0">
                        ✓ Saved
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-slate-400 shrink-0">
                    <span>{contextExpanded ? 'Hide' : 'Add / Edit'}</span>
                    {contextExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5" />
                    )}
                  </div>
                </div>

                {contextExpanded && (
                  <div className="px-3.5 pb-3.5 pt-1.5 border-t border-white/[0.06] space-y-2">
                    <p className="text-xs text-slate-400">
                      Input background context, project details, or rules for this conversation:
                    </p>
                    <textarea
                      rows={3}
                      value={chatContext}
                      onChange={(e) => handleSaveContextOnActiveChat(e.target.value)}
                      placeholder="Example: I am planning a kitchen remodel with a $25,000 budget. Keep answers practical and itemized..."
                      className="w-full rounded-lg bg-[#0B0D12] border border-white/[0.09] focus:border-[#D97757]/60 focus:outline-none p-2.5 text-xs text-slate-100 placeholder-slate-500 resize-y"
                    />
                  </div>
                )}
              </div>

              {messages.length === 0 ? (
                <div className="py-2 sm:py-4 space-y-5">
                  <div className="space-y-2">
                    <h1 className="text-xl sm:text-3xl font-semibold tracking-tight text-white">
                      Ask a question or ask me to create a file or image.
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                      Chat naturally with <strong className="text-slate-200">{selectedModel}</strong>,
                      generate real <strong className="text-slate-200">AI pictures (Photorealism, Anime & DreamShaper)</strong>,{' '}
                      <strong className="text-slate-200">Excel spreadsheets (.xlsx)</strong>,{' '}
                      <strong className="text-slate-200">PDF / Word documents</strong>, or{' '}
                      <strong className="text-slate-200">interactive mini-apps</strong>.
                    </p>
                  </div>

                  {/* 4 Clear Starter Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3">
                    {[
                      {
                        title: 'Generate a Real AI Image',
                        subtitle: 'Renders on your GPU with Photorealism, Anime, or DreamShaper',
                        icon: ImageIcon,
                        prompt:
                          'Generate a photorealistic portrait of an astronaut exploring a bioluminescent crystal cavern on an alien planet.',
                      },
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
                        subtitle: 'Writes a working calculator you can use right here',
                        icon: Code2,
                        prompt:
                          'Build an interactive Loan & Monthly Payment Calculator web app with sliders for loan amount, interest rate, and term.',
                      },
                    ].map((card, i) => {
                      const Icon = card.icon
                      return (
                        <button
                          key={i}
                          onClick={() => handleSendPrompt(card.prompt)}
                          className="text-left p-3.5 sm:p-4 rounded-xl bg-[#10131A] hover:bg-[#151922] border border-white/[0.075] hover:border-[#D97757]/40 transition group flex flex-col justify-between gap-2.5"
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
                <div className="space-y-5 pb-4">
                  {messages.map((msg, idx) => {
                    const isLatestUser =
                      msg.role === 'user' && idx >= messages.length - 2
                    return (
                      <div
                        key={msg.id}
                        ref={isLatestUser ? latestUserMsgRef : null}
                      >
                        <MessageRow
                          msg={msg}
                          onSelectArtifact={(art) => {
                            setSelectedArtifact(art)
                            setActiveSheetIdx(0)
                            setFilePanelOpen(true)
                          }}
                          onDeleteArtifact={handleDeleteArtifact}
                        />
                      </div>
                    )
                  })}

                  {streamStatus && (
                    <div className="flex items-center justify-between gap-2.5 text-xs font-mono text-slate-400 py-2 px-3 rounded-lg bg-white/[0.03] border border-white/[0.05]">
                      <div className="flex items-center gap-2 min-w-0">
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#D97757] shrink-0" />
                        <span className="truncate">{streamStatus}</span>
                      </div>
                      {isStreaming && (
                        <button
                          type="button"
                          onClick={handleStopResponse}
                          className="px-2.5 py-1 rounded-md bg-red-500/15 hover:bg-red-500/25 border border-red-500/35 text-red-300 font-sans text-xs font-medium flex items-center gap-1 shrink-0 transition"
                          title="Stop response"
                        >
                          <Square className="w-2.5 h-2.5 fill-current text-red-400" />
                          <span>Stop</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* BOTTOM COMPOSER BAR (Safe-area padded & compact so it never clips on mobile) */}
          <div className="shrink-0 px-2.5 sm:px-4 pt-2 pb-3 safe-bottom border-t border-white/[0.075] bg-[#0B0D12] z-20">
            <div className="max-w-3xl mx-auto">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSendPrompt()
                }}
                className="rounded-xl bg-[#12151E] border border-white/[0.1] focus-within:border-[#D97757]/60 transition p-2 sm:p-2.5 space-y-2"
              >
                {isSleeping && (
                  <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-xs text-cyan-300">
                    <Moon className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400 shrink-0" />
                    <span>Sleep Mode active (0 MB VRAM in use). Type any message or press Enter to wake up.</span>
                  </div>
                )}

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
                  placeholder="Ask a question, or ask to generate an image, Excel sheet, PDF, or app..."
                  className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none px-1.5 py-0.5"
                />

                <div className="flex items-center justify-between gap-1.5 pt-1.5 border-t border-white/[0.06]">
                  <div className="flex items-center gap-1.5 min-w-0 overflow-x-auto">
                    {/* Single Model Picker */}
                    <div className="relative shrink-0">
                      <select
                        aria-label="Choose AI Model"
                        value={selectedModel}
                        onChange={(e) => handleSwitchModel(e.target.value)}
                        className="h-8 pl-2 pr-6 rounded-lg bg-[#191D28] hover:bg-[#1F2432] border border-white/[0.1] text-[11px] sm:text-xs font-mono text-slate-100 appearance-none cursor-pointer transition"
                      >
                        {installedModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name} ({m.size_gb}GB)
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="w-3 h-3 text-slate-400 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    </div>

                    <button
                      type="button"
                      onClick={() => setModelModalOpen(true)}
                      className="h-8 px-2 rounded-lg border border-white/[0.08] bg-[#161A24] hover:bg-[#1D2230] text-[11px] sm:text-xs text-slate-300 flex items-center gap-1 shrink-0 transition"
                      title="Download or switch models"
                    >
                      <Sparkles className="w-3 h-3 text-[#D97757]" />
                      <span className="hidden sm:inline">+ Models</span>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        handleUpdateSetting({ air_gap_mode: !isOfflineOnly })
                      }
                      className={`h-8 px-2 rounded-lg border text-[11px] sm:text-xs flex items-center gap-1 shrink-0 transition ${
                        isOfflineOnly
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                          : 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                      }`}
                    >
                      {isOfflineOnly ? (
                        <>
                          <Lock className="w-3 h-3" />
                          <span>Offline</span>
                        </>
                      ) : (
                        <>
                          <Globe className="w-3 h-3" />
                          <span>Web On</span>
                        </>
                      )}
                    </button>
                  </div>

                  {isStreaming ? (
                    <button
                      type="button"
                      onClick={handleStopResponse}
                      className="h-8 px-3.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-300 font-medium text-xs flex items-center gap-1.5 shrink-0 transition cursor-pointer"
                      title="Stop generating response immediately"
                    >
                      <Square className="w-3 h-3 fill-current text-red-400" />
                      <span>Stop</span>
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={!promptInput.trim()}
                      className="h-8 px-3.5 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white font-medium text-xs flex items-center gap-1.5 shrink-0 transition"
                    >
                      <span>Send</span>
                      <Send className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </form>
            </div>
          </div>
        </main>

        {/* RIGHT PANEL: CREATED FILES PREVIEW, DOWNLOAD & DELETE */}
        {filePanelOpen && (
          <aside className="fixed lg:static inset-y-0 right-0 w-full sm:w-[440px] xl:w-[520px] shrink-0 border-l border-white/[0.075] bg-[#0D0F14] flex flex-col z-40">
            <div className="px-4 py-3 border-b border-white/[0.075] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-[#D97757]" />
                <span className="text-xs font-semibold text-white">
                  File Preview & Downloads
                </span>
              </div>
              <button
                onClick={() => setFilePanelOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
                title="Close File Preview"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              {selectedArtifact ? (
                <div className="flex-1 flex flex-col min-h-0">
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
                          {appViewMode === 'preview' ? 'Code' : 'App'}
                        </button>
                      )}
                      <a
                        href={`${selectedArtifact.url}?download=true`}
                        download={selectedArtifact.filename}
                        className="h-8 px-2.5 rounded-md bg-[#D97757] hover:bg-[#E4886A] text-white text-xs font-medium flex items-center gap-1 transition"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download</span>
                      </a>
                      <button
                        onClick={(e) => handleDeleteArtifact(e, selectedArtifact.id)}
                        className="h-8 px-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-medium flex items-center gap-1 transition"
                        title="Permanently delete this file from disk and database"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Delete</span>
                      </button>
                    </div>
                  </div>

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
                      <div className="space-y-3">
                        <div className="rounded-lg overflow-hidden border border-white/[0.09] bg-[#10131A] flex items-center justify-center p-2">
                          <img
                            src={selectedArtifact.url}
                            alt={selectedArtifact.title}
                            className="max-w-full rounded"
                          />
                        </div>
                        {selectedArtifact.preview_data?.engine && (
                          <div className="p-2.5 rounded-lg bg-[#11141C] border border-white/[0.07] text-[11px] font-mono text-slate-400">
                            Engine: <span className="text-slate-200">{selectedArtifact.preview_data.engine}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
                  <FolderOpen className="w-8 h-8 mb-2 text-slate-600" />
                  <p className="text-xs leading-relaxed">
                    No files selected. Ask the AI in chat to generate an image, Excel
                    spreadsheet, PDF report, or web app!
                  </p>
                </div>
              )}

              {artifacts.length > 0 && (
                <div className="h-44 shrink-0 border-t border-white/[0.075] bg-[#0B0D12] p-3 overflow-y-auto">
                  <div className="text-[11px] font-medium text-slate-400 mb-2">
                    All Created Files ({artifacts.length})
                  </div>
                  <div className="space-y-1.5">
                    {artifacts.map((art) => (
                      <div
                        key={art.id}
                        onClick={() => {
                          setSelectedArtifact(art)
                          setActiveSheetIdx(0)
                        }}
                        className={`w-full text-left px-2.5 py-2 rounded-lg text-xs flex items-center justify-between gap-2 cursor-pointer transition ${
                          selectedArtifact?.id === art.id
                            ? 'bg-[#D97757]/15 border border-[#D97757]/40 text-white'
                            : 'bg-[#12151E] hover:bg-white/[0.06] text-slate-300 border border-white/[0.05]'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <ArtifactTypeBadge category={art.category} />
                          <span className="truncate font-medium">{art.title}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] font-mono text-slate-400 tabular-nums">
                            {(art.size_bytes / 1024).toFixed(1)} KB
                          </span>
                          <button
                            onClick={(e) => handleDeleteArtifact(e, art.id)}
                            title="Delete file permanently"
                            className="text-slate-400 hover:text-rose-400 p-1 rounded hover:bg-rose-500/10 transition"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
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
                    Adapts automatically between your RTX 4070 SUPER Desktop and Intel Core Ultra 258V Laptop
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

              <div className="p-4 rounded-xl bg-[#141821] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-white">
                    GPU VRAM Cache Management (Auto-Clears on New Chat & 3m Idle)
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    {systemStatus?.running_models?.length > 0
                      ? `Currently in VRAM: ${systemStatus.running_models
                          .map((m) => `${m.name} (${m.vram_gb} GB)`)
                          .join(', ')}`
                      : 'No AI models currently held in VRAM cache.'}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={flushingVram}
                  onClick={() => handleFlushVram(null)}
                  className="h-9 px-3.5 rounded-lg bg-[#D97757] hover:bg-[#E4886A] disabled:opacity-40 text-white text-xs font-medium shrink-0 transition"
                >
                  {flushingVram ? 'Clearing VRAM...' : 'Clear GPU VRAM Now'}
                </button>
              </div>

              {/* ZERO-VRAM GAMING MODE */}
              <div className="p-4 rounded-xl bg-[#141821] border border-amber-500/25 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Gamepad2 className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-semibold text-white">
                      Zero-VRAM Gaming Mode
                    </span>
                    {settings?.gaming_mode && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 font-mono">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Offloads 100% of LLM execution to your 64GB System RAM so games have full access to your GPU VRAM with zero FPS drops.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleUpdateSetting({ gaming_mode: !settings?.gaming_mode })}
                  className={`h-9 px-3.5 rounded-lg text-xs font-medium shrink-0 transition ${
                    settings?.gaming_mode
                      ? 'bg-amber-500 text-black font-semibold'
                      : 'bg-white/[0.08] hover:bg-white/[0.14] text-white border border-white/[0.1]'
                  }`}
                >
                  {settings?.gaming_mode ? 'Disable Gaming Mode' : 'Enable Gaming Mode'}
                </button>
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

      {/* MODEL HUB MODAL */}
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
                  Recommended LLM Models for {hw?.profile_label}
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
                                handleSwitchModel(rec.id)
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
                  Or Download Any Model from Ollama (e.g.{' '}
                  <code className="text-slate-200">gemma2:9b</code>,{' '}
                  <code className="text-slate-200">phi4:14b</code>)
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

      {/* SHUTDOWN / POWER OFF CONFIRMATION MODAL */}
      {shutdownModalOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-sm rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl p-5 space-y-4">
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center shrink-0 text-red-400">
                <Power className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-white">Stop Local AI Studio?</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  This will shut down the local server process and completely release all GPU VRAM and system memory.
                  You can restart it anytime using your desktop shortcut.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.06]">
              <button
                onClick={() => setShutdownModalOpen(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:bg-white/[0.06] transition"
              >
                Cancel
              </button>
              <button
                onClick={handleShutdown}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-medium text-white transition flex items-center gap-1.5 shadow-sm"
              >
                <Power className="w-3.5 h-3.5" />
                <span>Shutdown Studio</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MessageRow({ msg, onSelectArtifact, onDeleteArtifact }) {
  const [thinkOpen, setThinkOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const isUser = msg.role === 'user'

  return (
    <div
      className={`rounded-xl p-3.5 sm:p-4 transition ${
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

      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {msg.tool_calls.map((tc) => (
            <div
              key={tc.id}
              className="rounded-lg bg-[#121620] border border-white/[0.08] px-3 py-2 text-xs font-mono"
            >
              <div
                onClick={() => setToolsOpen((v) => !v)}
                className="flex items-center justify-between cursor-pointer gap-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {tc.status === 'running' ? (
                    <Loader2 className="w-3.5 h-3.5 text-[#D97757] animate-spin shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
                  )}
                  <span className="text-slate-200 font-semibold truncate">{tc.name}</span>
                  <span className="text-slate-400 truncate hidden sm:inline">
                    {tc.summary || ''}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 tabular-nums shrink-0">
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

      {msg.content && (
        <div
          className="prose-studio"
          dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }}
        />
      )}

      {/* Inline File Cards with Direct Preview AND Direct Delete Button */}
      {msg.artifacts && msg.artifacts.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/[0.07] grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {msg.artifacts.map((art) => (
            <div
              key={art.id}
              onClick={() => onSelectArtifact(art)}
              className="p-3 rounded-lg bg-[#141822] hover:bg-[#1A202E] border border-[#D97757]/35 cursor-pointer flex items-center justify-between gap-2 transition"
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
                <span className="text-[11px] font-medium text-[#D97757] flex items-center gap-1 px-2 py-1 rounded bg-[#D97757]/10">
                  <Eye className="w-3.5 h-3.5" />
                  <span>Open</span>
                </span>
                <button
                  type="button"
                  onClick={(e) => onDeleteArtifact(e, art.id)}
                  title="Permanently delete this file"
                  className="p-1.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/25 transition"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
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
        Excel file ready. Click <strong>Download</strong> above to open in Excel.
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
