import React from 'react'
import { ShieldAlert, AlertTriangle, Terminal, FileCode, Check, X, ShieldCheck } from 'lucide-react'

export default function ToolApprovalCard({ approval, onDecision }) {
  if (!approval) return null

  const { approval_id, tool_name, arguments: args, target_path, is_external, message } = approval

  return (
    <div className="rounded-xl border border-amber-500/40 bg-[#16130D] p-3.5 sm:p-4 shadow-xl shadow-amber-500/5 animate-in fade-in duration-200">
      <div className="flex items-start gap-3">
        <div className="h-9 w-9 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0 text-amber-400">
          <ShieldAlert className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-white">Tool Approval Required</span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30">
              {tool_name}
            </span>
            {is_external && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1 font-semibold">
                <AlertTriangle className="w-3 h-3 text-rose-400" />
                <span>EXTERNAL PC PATH</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 mt-1 leading-relaxed">
            {message || `The agent wants to execute ${tool_name}.`}
          </p>

          {/* Details Box */}
          <div className="mt-2.5 rounded-lg bg-[#0C0E14] border border-white/[0.08] p-2.5 space-y-1.5 text-xs font-mono">
            {target_path && (
              <div className="flex items-start gap-2">
                <span className="text-slate-500 shrink-0">Path:</span>
                <span className={`break-all ${is_external ? 'text-amber-300 font-semibold' : 'text-slate-200'}`}>
                  {target_path}
                </span>
              </div>
            )}
            {args?.command && (
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <Terminal className="w-3.5 h-3.5 text-[#D97757]" />
                  <span>Command:</span>
                </div>
                <div className="p-2 rounded bg-black/60 border border-white/[0.06] text-emerald-300 break-all whitespace-pre-wrap">
                  {args.command}
                </div>
              </div>
            )}
            {args?.script && (
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <FileCode className="w-3.5 h-3.5 text-[#D97757]" />
                  <span>Python Script:</span>
                </div>
                <div className="p-2 rounded bg-black/60 border border-white/[0.06] text-sky-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {args.script}
                </div>
              </div>
            )}
            {tool_name === 'edit_file_content' && args?.find && (
              <div className="text-[11px] text-slate-400">
                Editing target file (replacing specified block)
              </div>
            )}
          </div>

          {/* Action Decision Buttons */}
          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => onDecision(approval_id, 'allow_once')}
              className="min-h-[36px] px-3.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium flex items-center gap-1.5 shadow-sm transition cursor-pointer"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Allow Once</span>
            </button>

            <button
              type="button"
              onClick={() => onDecision(approval_id, 'always_allow')}
              className="min-h-[36px] px-3.5 rounded-lg bg-sky-600/30 hover:bg-sky-600/40 text-sky-200 border border-sky-500/40 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
              title="Automatically allow this tool in the future without asking"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-sky-300" />
              <span>Always Allow {tool_name}</span>
            </button>

            <button
              type="button"
              onClick={() => onDecision(approval_id, 'deny')}
              className="min-h-[36px] px-3.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
              <span>Deny</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
