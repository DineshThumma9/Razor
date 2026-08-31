
import { Skeleton } from '@/components/ui/skeleton'
import type { Case } from '../types'
import { fmt, fmtDate, relTime } from '../utils/formatters'
import { TypeBadge } from './TypeBadge'
import { StatusPill } from './StatusPill'
import { ChannelChip } from './ChannelChip'

const STATUS_ROW_BORDER: Record<string, string> = {
  escalated:   'border-l-red-500',
  in_progress: 'border-l-amber-500',
  pending:     'border-l-zinc-600',
  recovered:   'border-l-emerald-500',
  closed:      'border-l-zinc-700',
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
    <div className="rounded-lg border border-zinc-800/60 overflow-hidden h-full bg-[#0d0d12]">
      {/* Header */}
      <div className="grid grid-cols-[2fr_1fr_1.2fr_1fr_1.2fr_1fr_32px] gap-3 px-4 py-2.5 border-b border-zinc-800/60 bg-zinc-900/30">
        {['Customer', 'Amount', 'Type', 'Status', 'Last Contact', 'Next Scheduled', ''].map((h) => (
          <p key={h} className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{h}</p>
        ))}
      </div>

      {/* Rows */}
      <div className="overflow-y-auto max-h-150 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="grid grid-cols-[2fr_1fr_1.2fr_1fr_1.2fr_1fr_32px] gap-3 px-4 py-3 border-b border-zinc-800/40">
              {Array.from({ length: 6 }).map((__, j) => (
                <Skeleton key={j} className="h-4 w-full bg-zinc-800/60" />
              ))}
            </div>
          ))
        ) : cases.length === 0 ? (
        <div className="py-16 text-center text-zinc-600 text-sm">No cases found. Run the agent to generate cases.</div>
      ) : (
        cases.map((c) => (
          <div
            key={c.case_id}
            onClick={() => onRowClick(c.case_id)}
            className={`grid grid-cols-[2fr_1fr_1.2fr_1fr_1.2fr_1fr_32px] gap-3 px-4 py-3 border-b border-zinc-800/40 border-l-2 cursor-pointer hover:bg-zinc-800/20 transition-colors items-center ${STATUS_ROW_BORDER[c.recovery_status] ?? 'border-l-zinc-700'}`}
          >
            {/* Customer */}
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-200 truncate">{c.customer.name}</p>
              <p className="text-xs text-zinc-500 truncate">{c.customer.email}</p>
              {c.customer.contact && (
                <p className="text-xs text-zinc-600 truncate">+91 {c.customer.contact}</p>
              )}
            </div>

            {/* Amount */}
            <p className={`text-sm font-semibold ${c.recovery_status === 'recovered' ? 'text-emerald-400' : 'text-zinc-200'}`}>
              ₹{fmt(c.amount_inr)}
            </p>

            {/* Type */}
            <TypeBadge type={c.case_type} />

            {/* Status */}
            <StatusPill status={c.recovery_status} />

            {/* Last contact */}
            <div className="flex flex-col gap-0.5">
              <ChannelChip action={c.last_action_taken} />
              <p className="text-xs text-zinc-600">{relTime(c.first_seen_at)}</p>
            </div>

            {/* Next scheduled */}
            <p className="text-xs text-zinc-400">{fmtDate(c.next_retry_at)}</p>

            {/* Chevron */}
            <svg className="w-4 h-4 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        ))
      )}
      </div>
    </div>
  )
}
