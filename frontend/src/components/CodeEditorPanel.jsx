import React, { useState, useEffect, useRef } from 'react'
import {
  Save,
  RotateCcw,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
  X,
  Code2,
  ArrowLeft,
} from 'lucide-react'

export default function CodeEditorPanel({ file, workspaceId, onSave, onClose, onDelete }) {
  const [content, setContent] = useState('')
  const [originalContent, setOriginalContent] = useState('')
  const [isDirty, setIsDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState('idle') // 'idle' | 'saving' | 'saved' | 'error'
  const [statusMessage, setStatusMessage] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (file) {
      const initial = typeof file.content === 'string' ? file.content : ''
      setContent(initial)
      setOriginalContent(initial)
      setIsDirty(false)
      setSaveStatus('idle')
    }
  }, [file])

  const handleTextChange = (e) => {
    const val = e.target.value
    setContent(val)
    setIsDirty(val !== originalContent)
    if (saveStatus === 'saved') setSaveStatus('idle')
  }

  const handleKeyDown = (e) => {
    // Escape to close editor if not dirty or confirmed
    if (e.key === 'Escape' && onClose) {
      e.preventDefault()
      onClose()
      return
    }

    // Ctrl+S or Cmd+S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      triggerSave()
      return
    }

    // Tab key inserts 2 spaces
    if (e.key === 'Tab') {
      e.preventDefault()
      const { selectionStart, selectionEnd } = e.target
      const current = typeof content === 'string' ? content : ''
      const newContent = current.substring(0, selectionStart) + '  ' + current.substring(selectionEnd)
      setContent(newContent)
      setIsDirty(newContent !== originalContent)
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = selectionStart + 2
        }
      }, 0)
    }
  }

  const triggerSave = async () => {
    if (!file || saveStatus === 'saving') return
    setSaveStatus('saving')
    try {
      const success = await onSave(file.relative_path, content)
      if (success) {
        setOriginalContent(content)
        setIsDirty(false)
        setSaveStatus('saved')
        setStatusMessage('Saved & backup created')
        setTimeout(() => setSaveStatus('idle'), 2500)
      } else {
        setSaveStatus('error')
        setStatusMessage('Save failed')
      }
    } catch (err) {
      setSaveStatus('error')
      setStatusMessage(err.message || 'Error saving file')
    }
  }

  const handleReset = () => {
    setContent(originalContent)
    setIsDirty(false)
    setSaveStatus('idle')
  }

  if (!file) return null

  const lineCount = (typeof content === 'string' ? content : '').split('\n').length

  return (
    <div className="h-full flex flex-col bg-[#0A0B0E] border-t border-white/[0.06]">
      {/* Editor Header Bar */}
      <div className="px-3 py-2 bg-[#12151E] border-b border-white/[0.08] flex items-center justify-between gap-2 flex-wrap text-xs">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="h-7 px-2 rounded-md bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 hover:text-white flex items-center gap-1 transition cursor-pointer shrink-0"
              title="Back to Project Files list"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-[11px]">Files</span>
            </button>
          )}

          <Code2 className="w-4 h-4 text-sky-400 shrink-0" />
          <span className="font-semibold text-white truncate font-mono text-[11px]" title={file.relative_path}>
            {file.relative_path || file.name}
          </span>

          {isDirty && (
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40">
              Modified *
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 flex items-center gap-1 font-semibold border border-emerald-500/30">
              <Check className="w-3 h-3" />
              <span>{statusMessage || 'Saved'}</span>
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 flex items-center gap-1 border border-rose-500/30">
              <AlertCircle className="w-3 h-3" />
              <span>{statusMessage}</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {isDirty && (
            <button
              type="button"
              onClick={handleReset}
              className="h-7 px-2 rounded bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 text-[11px] font-medium flex items-center gap-1 transition cursor-pointer"
              title="Discard unsaved changes"
            >
              <RotateCcw className="w-3 h-3 text-slate-400" />
              <span>Reset</span>
            </button>
          )}

          <button
            type="button"
            onClick={triggerSave}
            disabled={saveStatus === 'saving' || !isDirty}
            className={`h-7 px-2.5 rounded text-[11px] font-medium flex items-center gap-1.5 transition cursor-pointer ${
              isDirty
                ? 'bg-[#D97757] hover:bg-[#E4886A] text-white shadow-sm'
                : 'bg-white/[0.06] text-slate-400 opacity-60 cursor-not-allowed'
            }`}
            title="Save changes (Ctrl+S)"
          >
            {saveStatus === 'saving' ? (
              <Loader2 className="w-3 h-3 animate-spin text-white" />
            ) : (
              <Save className="w-3 h-3" />
            )}
            <span>Save</span>
          </button>

          <button
            type="button"
            onClick={() => onDelete(file.relative_path || file.name)}
            className="h-7 w-7 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center justify-center transition cursor-pointer"
            title="Permanently delete file"
          >
            <Trash2 className="w-3 h-3" />
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="h-7 w-7 rounded bg-white/[0.06] hover:bg-white/[0.1] text-slate-400 hover:text-white flex items-center justify-center transition cursor-pointer"
              title="Close editor and return to file list"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Editor Body */}
      <div className="flex-1 relative flex min-h-0 bg-[#080A0F]">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          className="flex-1 w-full h-full p-3 font-mono text-xs text-slate-200 bg-transparent resize-none focus:outline-none leading-relaxed select-text"
          placeholder="File is empty. Type code or content here..."
        />
      </div>

      {/* Footer bar */}
      <div className="px-3 py-1.5 bg-[#0D1017] border-t border-white/[0.06] flex items-center justify-between text-[10px] font-mono text-slate-400">
        <span>{lineCount} lines • {(typeof content === 'string' ? content : '').length} characters</span>
        <span>UTF-8 • Auto-Backup on Save</span>
      </div>
    </div>
  )
}
