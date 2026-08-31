
import type { AuditEntry } from '../types'
import { CHANNEL_ICONS, CHANNEL_LABEL } from './ChannelChip'
import { fmtTs } from '../utils/formatters'
import { Zap } from 'lucide-react'

const AUDIT_DOT: Record<string, string> = {
  send_whatsapp_msg:   'bg-emerald-400',
  send_email_reminder: 'bg-sky-400',
  get_voice_call:      'bg-violet-400',
  create_payment_link: 'bg-amber-400',
  escalate_to_human:   'bg-red-400',
  log_promise_to_pay:  'bg-blue-400',
  complete_case:       'bg-emerald-600',
}

export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  if (!entries || entries.length === 0) {
    return <p className="text-xs text-zinc-500 py-4">No audit entries yet.</p>
  }
  const sorted = [...entries].reverse()
  return (
    <div className="flex flex-col gap-0">
      {sorted.map((e, i) => (
        <div key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className={`w-2 h-2 rounded-full mt-1 shrink-0 ${AUDIT_DOT[e.event_triggered] ?? 'bg-zinc-500'}`} />
            {i < sorted.length - 1 && <div className="w-px flex-1 bg-zinc-800 my-1" />}
          </div>
          <div className="pb-4 min-w-0">
            <p className="text-xs text-zinc-500">{fmtTs(e.next_contact ?? null)}</p>
            <p className="text-sm font-medium text-zinc-200 mt-0.5 flex items-center gap-1.5">
              {(() => {
                const Icon = CHANNEL_ICONS[e.event_triggered] ?? Zap
                return <Icon className="w-4 h-4 text-zinc-400" />
              })()}
              <span>{CHANNEL_LABEL[e.event_triggered] ?? e.event_triggered.replace(/_/g, ' ')}</span>
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">
              Status: <span className="text-zinc-400">{e.recovery_status}</span>
              {e.next_contact && (
                <> · Next: <span className="text-zinc-400">{fmtTs(e.next_contact)}</span></>
              )}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
