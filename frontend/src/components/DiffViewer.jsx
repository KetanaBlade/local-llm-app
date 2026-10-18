import React, { useState } from 'react'
import { ChevronDown, ChevronRight, RotateCcw, ShieldCheck, Loader2 } from 'lucide-react'

export default function DiffViewer({ diff, filepath, backupPath, onRevert, isReverting }) {
  const [isExpanded, setIsExpanded] = useState(true)

  if (!diff) return null

  const lines = diff.split('\n')
  const additions = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length
  const deletions = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length

  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#0A0C11] overflow-hidden my-2">
      <div className="px-3 py-2 bg-[#121622] border-b border-white/[0.06] flex items-center justify-between gap-2 flex-wrap text-xs">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex items-center gap-2 text-slate-200 hover:text-white font-mono text-[11px] truncate cursor-pointer"
        >
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
          <span className="font-semibold text-slate-200">{filepath || 'File Changes'}</span>
          <span className="text-emerald-400 font-semibold">+{additions}</span>
          <span className="text-rose-400 font-semibold">-{deletions}</span>
        </button>

        {backupPath && (
          <button
            type="button"
            disabled={isReverting}
            onClick={() => onRevert(backupPath)}
            className="px-2.5 py-1 rounded bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/35 text-amber-300 text-[11px] font-mono flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
            title="Restore previous file version from safe backup"
          >
            {isReverting ? (
              <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
            ) : (
              <RotateCcw className="w-3 h-3 text-amber-400" />
            )}
            <span>Revert to .bak</span>
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="p-2.5 overflow-x-auto text-[11px] font-mono max-h-72 leading-relaxed">
          {lines.map((line, idx) => {
            let lineClass = 'text-slate-400'
            let bgClass = ''
            if (line.startsWith('+++') || line.startsWith('---')) {
              lineClass = 'text-slate-500 font-semibold'
            } else if (line.startsWith('@@')) {
              lineClass = 'text-cyan-400 font-semibold'
              bgClass = 'bg-cyan-500/5'
            } else if (line.startsWith('+')) {
              lineClass = 'text-emerald-300 font-medium'
              bgClass = 'bg-emerald-500/10'
            } else if (line.startsWith('-')) {
              lineClass = 'text-rose-300 font-medium'
              bgClass = 'bg-rose-500/10'
            }

            return (
              <div key={idx} className={`px-1.5 py-0.5 rounded-sm whitespace-pre ${lineClass} ${bgClass}`}>
                {line || ' '}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
