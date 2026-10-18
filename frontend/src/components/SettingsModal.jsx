import React, { useState, useEffect } from 'react'
import {
  ShieldCheck,
  ShieldAlert,
  Cpu,
  Globe,
  Smartphone,
  Lock,
  Gamepad2,
  Key,
  Eye,
  EyeOff,
  Check,
  X,
  Sliders,
  Terminal,
  Zap,
  FileCode,
  AlertTriangle,
} from 'lucide-react'

export default function SettingsModal({
  isOpen,
  onClose,
  settings,
  hardware,
  network,
  onUpdateSetting,
  activeTab = 'permissions',
  setActiveTab,
}) {
  const [braveKey, setBraveKey] = useState('')
  const [showBraveKey, setShowBraveKey] = useState(false)
  const [braveKeySaved, setBraveKeySaved] = useState(false)

  useEffect(() => {
    if (settings?.brave_search_api_key !== undefined) {
      setBraveKey(settings.brave_search_api_key || '')
    }
  }, [settings?.brave_search_api_key])

  if (!isOpen) return null

  const handleSaveBraveKey = async () => {
    await onUpdateSetting({ brave_search_api_key: braveKey.trim() })
    setBraveKeySaved(true)
    setTimeout(() => setBraveKeySaved(false), 2000)
  }

  const currentToolPerms = settings?.tool_permissions || {}

  const updateToolPermission = async (toolName, perm) => {
    const updated = { ...currentToolPerms, [toolName]: perm }
    await onUpdateSetting({ tool_permissions: updated })
  }

  const toolDefinitions = [
    { id: 'read_file', name: 'read_file', desc: 'Inspect content of files in workspace or codebase', category: 'Read' },
    { id: 'list_directory', name: 'list_directory', desc: 'Explore directory structure and list folders/files', category: 'Read' },
    { id: 'search_web', name: 'search_web', desc: 'Query Brave Search for live internet results and documentation', category: 'Read' },
    { id: 'edit_file_content', name: 'edit_file_content', desc: 'Create, modify, and refactor source code files', category: 'Write' },
    { id: 'run_shell_command', name: 'run_shell_command', desc: 'Execute terminal commands in shell (PowerShell)', category: 'Exec' },
    { id: 'execute_python', name: 'execute_python', desc: 'Execute Python analysis and data transformation scripts', category: 'Exec' },
    { id: 'create_excel_spreadsheet', name: 'create_excel_spreadsheet', desc: 'Generate real .xlsx workbooks with formulas', category: 'Write' },
    { id: 'create_document', name: 'create_document', desc: 'Build formatted Word (.docx) and PDF reports', category: 'Write' },
    { id: 'build_interactive_app', name: 'build_interactive_app', desc: 'Create standalone HTML/JS interactive mini-apps', category: 'Write' },
    { id: 'generate_visual_media', name: 'generate_visual_media', desc: 'Render images with local SDXL neural diffusion', category: 'GPU' },
  ]

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-[#D97757]/15 border border-[#D97757]/30 flex items-center justify-center text-[#D97757]">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Studio Settings</h2>
              <p className="text-xs text-slate-400">
                Agent permissions, hardware profiles, privacy, and mobile access
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Bar */}
        <div className="flex border-b border-white/[0.08] px-5 bg-[#0D0F14] shrink-0 overflow-x-auto">
          {[
            { id: 'permissions', label: 'Agent & Permissions', icon: ShieldCheck },
            { id: 'hardware', label: 'Hardware & Gaming', icon: Cpu },
            { id: 'web_privacy', label: 'Web & Privacy', icon: Globe },
            { id: 'phone_link', label: 'Phone Link', icon: Smartphone },
          ].map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`py-3 px-3 sm:px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition shrink-0 cursor-pointer ${
                  active
                    ? 'border-[#D97757] text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-[#D97757]' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>

        {/* Tab Content */}
        <div className="p-5 space-y-5 overflow-y-auto flex-1">
          {/* TAB 1: AGENT & PERMISSIONS */}
          {activeTab === 'permissions' && (
            <div className="space-y-5">
              {/* Autonomy Level */}
              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  Agent Autonomy Level
                </label>
                <p className="text-xs text-slate-400 mb-2.5">
                  Control when the agent requires your explicit confirmation before executing tools.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {[
                    {
                      id: 'ask',
                      title: '🛡️ Ask on Write/Exec',
                      badge: 'Default / Recommended',
                      desc: 'Autonomous reading and web search. Prompts for approval before writing files or running commands.',
                    },
                    {
                      id: 'autonomous',
                      title: '⚡ Autonomous (Allow All)',
                      badge: 'Antigravity / Cursor Mode',
                      desc: 'Runs file edits, shell commands, and builds automatically without pausing for confirmation.',
                    },
                    {
                      id: 'plan',
                      title: '📋 Plan Only',
                      badge: 'Read-Only Planning',
                      desc: 'AI explores codebase and formulates plans, but will never write files or execute commands.',
                    },
                  ].map((lvl) => {
                    const active = (settings?.permission_mode || 'ask') === lvl.id
                    return (
                      <button
                        key={lvl.id}
                        type="button"
                        onClick={() => onUpdateSetting({ permission_mode: lvl.id })}
                        className={`p-3 rounded-xl border text-left transition cursor-pointer flex flex-col justify-between gap-2 ${
                          active
                            ? 'border-[#D97757]/60 bg-[#D97757]/15 text-white'
                            : 'border-white/[0.08] bg-[#141822] text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <div>
                          <div className="text-xs font-semibold text-white">{lvl.title}</div>
                          <div className="text-[10px] font-mono text-[#D97757] mt-0.5">{lvl.badge}</div>
                        </div>
                        <div className="text-[11px] text-slate-400 leading-relaxed">{lvl.desc}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* External Path Policy */}
              <div className="pt-3 border-t border-white/[0.06]">
                <label className="block text-xs font-semibold text-white mb-1">
                  External Filesystem Boundary Policy
                </label>
                <p className="text-xs text-slate-400 mb-2">
                  What happens when an agent tool attempts to modify files located outside the active workspace directory:
                </p>
                <select
                  aria-label="External Path Policy"
                  value={settings?.external_path_policy || 'ask'}
                  onChange={(e) => onUpdateSetting({ external_path_policy: e.target.value })}
                  className="w-full h-9 px-3 rounded-lg bg-[#0C0E14] border border-white/[0.1] text-xs text-white cursor-pointer"
                >
                  <option value="ask">⚠️ Prompt before modifying files outside workspace (Recommended)</option>
                  <option value="deny">🚫 Strictly block all file modifications outside workspace</option>
                  <option value="allow">⚡ Allow external modifications according to standard tool permissions</option>
                </select>
              </div>

              {/* Per-Tool Permissions Table */}
              <div className="pt-3 border-t border-white/[0.06]">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold text-white">
                    Individual Tool Permission Matrix
                  </label>
                  <span className="text-[11px] font-mono text-slate-500">
                    Granular Overrides
                  </span>
                </div>
                <div className="rounded-xl border border-white/[0.08] bg-[#0C0E14] divide-y divide-white/[0.05] overflow-hidden">
                  {toolDefinitions.map((t) => {
                    const current = currentToolPerms[t.id] || (t.category === 'Read' ? 'allow' : 'ask')
                    return (
                      <div key={t.id} className="p-2.5 sm:px-3 sm:py-2 flex items-center justify-between gap-3 text-xs">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-slate-200 font-medium">{t.name}</span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                              t.category === 'Read' ? 'bg-sky-500/20 text-sky-300' :
                              t.category === 'Write' ? 'bg-emerald-500/20 text-emerald-300' :
                              t.category === 'Exec' ? 'bg-amber-500/20 text-amber-300' :
                              'bg-purple-500/20 text-purple-300'
                            }`}>
                              {t.category}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5 truncate hidden sm:block">
                            {t.desc}
                          </div>
                        </div>

                        <select
                          aria-label={`Permission for ${t.name}`}
                          value={current}
                          onChange={(e) => updateToolPermission(t.id, e.target.value)}
                          className={`h-7 px-2 rounded-md border text-xs font-mono cursor-pointer ${
                            current === 'allow'
                              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                              : current === 'deny'
                              ? 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                              : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                          }`}
                        >
                          <option value="allow" className="bg-[#10131A] text-emerald-300">Allow</option>
                          <option value="ask" className="bg-[#10131A] text-amber-300">Ask</option>
                          <option value="deny" className="bg-[#10131A] text-rose-300">Deny</option>
                        </select>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: HARDWARE & GAMING MODE */}
          {activeTab === 'hardware' && (
            <div className="space-y-5">
              {/* Profile Mode */}
              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  Hardware Profile Mode
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {[
                    { id: 'auto', title: 'Auto-Detect (Recommended)', desc: 'Automatically tunes for whichever PC or laptop you are on' },
                    { id: 'desktop_rtx4070s', title: 'Desktop: RTX 4070 SUPER', desc: '12GB VRAM + 64GB RAM' },
                    { id: 'laptop_ultra_258v', title: 'Laptop: Core Ultra 258V', desc: 'Arc 140V + NPU + 32GB Shared Memory' },
                  ].map((p) => {
                    const active = (settings?.hardware_profile_override || 'auto') === p.id
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => onUpdateSetting({ hardware_profile_override: p.id })}
                        className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                          active
                            ? 'border-[#D97757]/60 bg-[#D97757]/15 text-white'
                            : 'border-white/[0.08] bg-[#141822] text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <div className="text-xs font-semibold text-white">{p.title}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">{p.desc}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Gaming Mode Toggle */}
              <div className="p-3.5 rounded-xl bg-[#141822] border border-white/[0.08] flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Gamepad2 className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-semibold text-white">Gaming Mode (0 GPU VRAM)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Offloads LLM inference 100% to your 64GB System RAM so your GPU retains 100% VRAM with zero FPS drops.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onUpdateSetting({ gaming_mode: !settings?.gaming_mode })}
                  className={`min-h-[36px] px-3.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    settings?.gaming_mode
                      ? 'bg-amber-500 text-black shadow-sm'
                      : 'bg-white/[0.08] hover:bg-white/[0.12] text-slate-300'
                  }`}
                >
                  {settings?.gaming_mode ? 'Enabled' : 'Disabled'}
                </button>
              </div>

              {/* Hardware Telemetry Info */}
              {hardware && (
                <div className="p-3.5 rounded-xl bg-[#0C0E14] border border-white/[0.08] space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between text-slate-300">
                    <span>GPU:</span>
                    <span className="text-white font-semibold">{hardware.gpu?.name}</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>VRAM:</span>
                    <span className="text-emerald-400 font-semibold">{hardware.gpu?.vram_free_gb} GB Free / {hardware.gpu?.vram_total_gb} GB Total</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Active Profile:</span>
                    <span className="text-[#D97757] font-semibold">{hardware.profile_label}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: WEB SEARCH & PRIVACY */}
          {activeTab === 'web_privacy' && (
            <div className="space-y-5">
              {/* Strict Air-Gap Mode */}
              <div className="p-3.5 rounded-xl bg-[#141822] border border-white/[0.08] flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-semibold text-white">Strict Air-Gap Mode</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    When active, all outbound internet traffic is blocked. The studio operates 100% locally and offline.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onUpdateSetting({ air_gap_mode: !settings?.air_gap_mode })}
                  className={`min-h-[36px] px-3.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    settings?.air_gap_mode
                      ? 'bg-emerald-500 text-black shadow-sm'
                      : 'bg-white/[0.08] hover:bg-white/[0.12] text-slate-300'
                  }`}
                >
                  {settings?.air_gap_mode ? 'Enabled' : 'Disabled'}
                </button>
              </div>

              {/* Brave Search API Key */}
              <div>
                <label className="block text-xs font-semibold text-white mb-1">
                  Brave Search API Key
                </label>
                <p className="text-xs text-slate-400 mb-2">
                  Used by the <code className="text-slate-300">search_web</code> tool to fetch live search results. Free tier gives 2,000 queries/month.
                </p>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      type={showBraveKey ? 'text' : 'password'}
                      value={braveKey}
                      onChange={(e) => setBraveKey(e.target.value)}
                      placeholder="BSA..."
                      className="w-full h-9 pl-3 pr-9 rounded-lg bg-[#0C0E14] border border-white/[0.1] text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-[#D97757]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowBraveKey((v) => !v)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                      title={showBraveKey ? 'Hide API key' : 'Show API key'}
                    >
                      {showBraveKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={handleSaveBraveKey}
                    className="h-9 px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] text-white text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                  >
                    {braveKeySaved ? <Check className="w-3.5 h-3.5" /> : <Key className="w-3.5 h-3.5" />}
                    <span>{braveKeySaved ? 'Saved' : 'Save Key'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: PHONE LINK */}
          {activeTab === 'phone_link' && network && (
            <div className="text-center space-y-4 py-2">
              <p className="text-xs text-slate-300 leading-relaxed max-w-md mx-auto">
                Scan this QR code with your phone camera while connected to your home Wi-Fi to use Local AI Studio on your phone:
              </p>
              {network.qr_code && (
                <div className="inline-block p-3 rounded-2xl bg-[#111317] border border-white/[0.1] shadow-lg">
                  <img src={network.qr_code} alt="LAN QR Code" className="w-48 h-48 mx-auto rounded" />
                </div>
              )}
              <div className="p-3 rounded-lg bg-[#0B0D12] border border-white/[0.08] font-mono text-sm text-[#D97757] select-all max-w-sm mx-auto">
                {network.lan_url}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
