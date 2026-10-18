import React, { useState, useEffect } from 'react'
import { Folder, FolderPlus, ExternalLink, X, Loader2, Sparkles, AlertCircle } from 'lucide-react'

export default function ProjectModal({
  isOpen,
  onClose,
  mode = 'create', // 'create' | 'edit'
  project = null,
  workspace = null,
  onSave,
  onPickFolder,
}) {
  const activeProj = project || workspace
  const [name, setName] = useState('')
  const [isExternal, setIsExternal] = useState(false)
  const [path, setPath] = useState('')
  const [instructions, setInstructions] = useState('')
  const [isPicking, setIsPicking] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isOpen) {
      setError('')
      setIsSaving(false)
      setIsPicking(false)
      if (mode === 'edit' && activeProj) {
        setName(activeProj.name || '')
        setIsExternal(Boolean(activeProj.is_external))
        setPath(activeProj.path || '')
        setInstructions(activeProj.instructions || '')
      } else {
        setName('')
        setIsExternal(false)
        setPath('')
        setInstructions('')
      }
    }
  }, [isOpen, mode, activeProj])

  if (!isOpen) return null

  const handlePickFolder = async () => {
    setIsPicking(true)
    setError('')
    try {
      const selected = await onPickFolder()
      if (selected) {
        setPath(selected)
        setIsExternal(true)
        if (!name.trim()) {
          // Extract base folder name as default project name
          const folderName = selected.split(/[/\\]/).filter(Boolean).pop() || 'My Project'
          setName(folderName)
        }
      }
    } catch (err) {
      setError('Could not open folder picker. You can type the absolute path manually.')
    } finally {
      setIsPicking(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Please provide a name for this project.')
      return
    }
    if (isExternal && !path.trim()) {
      setError('Please provide or browse for an external folder path.')
      return
    }

    setIsSaving(true)
    setError('')
    try {
      await onSave({
        name: name.trim(),
        is_external: isExternal,
        path: isExternal ? path.trim() : null,
        instructions: instructions.trim(),
      })
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to save project.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl bg-[#10131A] border border-white/[0.1] shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-[#D97757]/15 border border-[#D97757]/30 flex items-center justify-center text-[#D97757]">
              {mode === 'create' ? <FolderPlus className="w-4 h-4" /> : <Folder className="w-4 h-4" />}
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                {mode === 'create' ? 'Create New Project' : `Edit "${activeProj?.name}"`}
              </h2>
              <p className="text-xs text-slate-400">
                {mode === 'create'
                  ? 'Organize your chats, files, and AI agent instructions in a dedicated project'
                  : 'Update project settings and instructions'}
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto flex-1">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Mode Switcher: Managed vs External (only when creating) */}
          {mode === 'create' && (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Project Storage Location
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setIsExternal(false)}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                    !isExternal
                      ? 'border-[#D97757]/60 bg-[#D97757]/15 text-white'
                      : 'border-white/[0.08] bg-[#141822] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <div className="text-xs font-semibold">Managed Project</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Isolated inside Local AI Studio's projects directory
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setIsExternal(true)}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                    isExternal
                      ? 'border-sky-500/60 bg-sky-500/15 text-white'
                      : 'border-white/[0.08] bg-[#141822] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <div className="text-xs font-semibold flex items-center gap-1">
                    <span>Link PC Folder</span>
                    <ExternalLink className="w-3 h-3 text-sky-400" />
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Connect an existing folder or codebase on your computer
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Project Name */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Project Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Weather Dashboard, 2026 Budget, Robotics Pilot..."
              className="w-full h-9 px-3 rounded-lg bg-[#0C0E14] border border-white/[0.1] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#D97757]"
              required
            />
          </div>

          {/* External Folder Path Picker */}
          {isExternal && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-slate-300">
                  Folder Path on Your PC
                </label>
                <button
                  type="button"
                  disabled={isPicking}
                  onClick={handlePickFolder}
                  className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1 cursor-pointer disabled:opacity-50"
                >
                  {isPicking ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Folder className="w-3.5 h-3.5" />
                  )}
                  <span>Browse Folder...</span>
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  placeholder="e.g. C:\Users\Username\Projects\my-app"
                  className="flex-1 h-9 px-3 rounded-lg bg-[#0C0E14] border border-white/[0.1] text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                  required={isExternal}
                />
                <button
                  type="button"
                  disabled={isPicking}
                  onClick={handlePickFolder}
                  className="h-9 px-3 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 border border-sky-500/40 text-xs font-medium text-sky-200 flex items-center gap-1.5 transition cursor-pointer shrink-0"
                  title="Open native Windows Folder Picker"
                >
                  {isPicking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Folder className="w-3.5 h-3.5" />}
                  <span>Browse</span>
                </button>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                The AI will be able to inspect, search, and edit files in this folder.
              </p>
            </div>
          )}

          {/* Project Instructions / Custom System Prompt */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-slate-300">
                Project Instructions & Rules
              </label>
              <span className="text-[10px] font-mono text-slate-500">Optional</span>
            </div>
            <textarea
              rows={4}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Follow Tailwind CSS conventions. All unit tests must be written with pytest. Never delete production databases..."
              className="w-full p-2.5 rounded-lg bg-[#0C0E14] border border-white/[0.1] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#D97757] resize-y"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              These instructions are automatically injected into the agent system prompt for every chat in this project. If an <code className="text-slate-300">AI_GUIDELINES.md</code> file exists in the project root, its contents are also automatically read.
            </p>
          </div>

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/[0.08]">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-white/[0.06] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="min-h-[38px] px-4 rounded-lg bg-[#D97757] hover:bg-[#E4886A] text-white text-xs font-medium flex items-center gap-1.5 transition shadow-sm disabled:opacity-50 cursor-pointer"
            >
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              <span>{mode === 'create' ? 'Create Project' : 'Save Changes'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
