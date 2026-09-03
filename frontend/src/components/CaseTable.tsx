
import { Skeleton } from '@/components/ui/skeleton'
import type { Case } from '../types'
import { fmt, fmtTs } from '../utils/formatters'
import { TypeBadge } from './TypeBadge'
import { StatusPill } from './StatusPill'
import { ChannelChip } from './ChannelChip'

const STATUS_ROW_BORDER: Record<string, string> = {
  escalated:   'border-l-red-500/50',
  in_progress: 'border-l-amber-500/50',
  pending:     'border-l-zinc-700/50',
  recovered:   'border-l-emerald-500/50',
  closed:      'border-l-zinc-700/50',
}

export function CaseTable({
  cases,
  loading,
  onRowClick,
}: {
  cases: Case[]
  loading: boolean
  onRowClick: (id: string) => void
}) {
   

 
  return (
    <div className="rounded-xl border border-zinc-800/80 overflow-x-auto overflow-y-hidden h-full bg-[#0d0d12] shadow-2xl">
      <div className="min-w-[750px]">
      {/* Header */}
      <div className="grid grid-cols-[48px_2fr_1fr_1fr_1.2fr_1fr_1fr_90px] gap-4 px-5 py-3 border-b border-zinc-800/80 bg-zinc-900/50">
        {['#', 'Customer', 'Status', 'Amount', 'Type', 'Channel', 'Next Scheduled', ''].map((h, i) => (
          <p key={i} className="text-[11px] font-semibold text-zinc-500 uppercase tracking-widest">{h}</p>
        ))}
      </div>

      {/* Rows */}
      <div className="overflow-y-auto max-h-[600px] scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="grid grid-cols-[48px_2fr_1fr_1fr_1.2fr_1fr_1fr_90px] gap-4 px-5 py-4 border-b border-zinc-800/40">
              {Array.from({ length: 8 }).map((__, j) => (
                <Skeleton key={j} className="h-4 w-full bg-zinc-800/40 rounded-sm" />
              ))}
            </div>
          ))
        ) : cases.length === 0 ? (
        <div className="py-20 text-center text-zinc-600 text-sm">No cases found. Run the agent to generate cases.</div>
      ) : (
        cases.map((c, idx) => (
          <div
            key={c.case_id}
            onClick={() => onRowClick(c.case_id)}
            className={`grid grid-cols-[48px_2fr_1fr_1fr_1.2fr_1fr_1fr_90px] gap-4 px-5 py-3 border-b border-zinc-800/40 border-l-[3px] cursor-pointer hover:bg-zinc-800/30 transition-all items-center group ${STATUS_ROW_BORDER[c.recovery_status] ?? 'border-l-transparent'}`}
          >
            {/* Index */}
            <p className="text-xs font-mono text-zinc-600">
              {idx + 1}
            </p>

            {/* Customer */}
            <div className="min-w-0 flex flex-col justify-center">
              <p className="text-[13px] font-semibold text-zinc-200 truncate">{c.customer.name}</p>
              <p className="text-[11px] text-zinc-500 truncate mt-0.5">{c.customer.email}</p>
            </div>

            {/* Status */}
            <div className="flex items-center">
              <StatusPill status={c.recovery_status} />
            </div>

            {/* Amount */}
            <p className={`text-[13px] font-mono tracking-tight ${c.recovery_status === 'recovered' ? 'text-emerald-400' : 'text-zinc-300'}`}>
              ₹{fmt(c.amount_inr)}
            </p>

            {/* Type */}
            <div className="flex items-center">
              <TypeBadge type={c.case_type} />
            </div>

            {/* Channel */}
            <div className="flex items-center">
              <ChannelChip action={c.last_action_taken} />
            </div>

            {/* Next Scheduled */}
            <p className="text-[12px] text-zinc-400 whitespace-nowrap">
              {c.next_retry_at ? fmtTs(c.next_retry_at) : (c.recovery_status === 'closed' || c.recovery_status === 'recovered' ? '—' : 'Pending')}
            </p>

            {/* Action */}
            <div className="flex items-center justify-end">
              <button 
                className="px-3 py-1.5 rounded-md bg-zinc-800/50 text-zinc-300 text-[11px] font-medium border border-zinc-700/50 opacity-0 group-hover:opacity-100 group-hover:bg-zinc-700 hover:text-white hover:border-zinc-500 transition-all"
                onClick={(e) => { e.stopPropagation(); onRowClick(c.case_id); }}
              >
                Inspect
              </button>
            </div>
          </div>
        ))
      )}
      </div>
      </div>
    </div>
  )
}
