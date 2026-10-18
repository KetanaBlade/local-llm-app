import React from 'react'
import { FileSpreadsheet, FileText, Code2, Image as ImageIcon, File } from 'lucide-react'

export default function AtMentionDropdown({ files, query, selectedIndex, onSelect }) {
  const filtered = (files || []).filter((f) =>
    (f.name || '').toLowerCase().includes((query || '').toLowerCase())
  ).slice(0, 8)

  if (filtered.length === 0) return null

  const getIcon = (category) => {
    switch (category) {
      case 'spreadsheet':
        return <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
      case 'code':
        return <Code2 className="w-3.5 h-3.5 text-sky-400 shrink-0" />
      case 'image':
        return <ImageIcon className="w-3.5 h-3.5 text-purple-400 shrink-0" />
      default:
        return <FileText className="w-3.5 h-3.5 text-amber-400 shrink-0" />
    }
  }

  return (
    <div className="absolute bottom-full mb-1.5 left-2 w-72 sm:w-80 max-h-56 overflow-y-auto rounded-xl bg-[#121622] border border-white/[0.12] shadow-2xl z-50 p-1.5 space-y-0.5">
      <div className="px-2 py-1 text-[10px] font-mono text-slate-400 flex items-center justify-between border-b border-white/[0.06] mb-1">
        <span>ATTACH PROJECT FILE (@)</span>
        <span className="text-slate-500">↑↓ to navigate, Enter to select</span>
      </div>
      {filtered.map((file, idx) => (
        <button
          key={file.relative_path || file.name}
          type="button"
          onMouseDown={(e) => {
            e.preventDefault()
            onSelect(file)
          }}
          className={`w-full text-left px-2 py-1.5 rounded-lg flex items-center gap-2 text-xs transition cursor-pointer ${
            idx === selectedIndex
              ? 'bg-[#D97757]/20 text-white border border-[#D97757]/40'
              : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
          }`}
        >
          {getIcon(file.category)}
          <span className="truncate flex-1 font-medium">{file.name}</span>
          <span className="text-[10px] font-mono text-slate-500 tabular-nums">
            {((file.size_bytes || 0) / 1024).toFixed(0)}KB
          </span>
        </button>
      ))}
    </div>
  )
}
