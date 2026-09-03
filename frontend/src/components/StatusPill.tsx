const STATUS_STYLES: Record<string, string> = {
  escalated:   'bg-transparent text-red-400 border-red-500/30',
  in_progress: 'bg-transparent text-amber-400 border-amber-500/30',
  pending:     'bg-transparent text-zinc-400 border-zinc-600/40',
  recovered:   'bg-transparent text-emerald-400 border-emerald-500/30',
  closed:      'bg-transparent text-zinc-500 border-zinc-700/30',
}

const STATUS_LABELS: Record<string, string> = {
  escalated: 'Escalated', in_progress: 'In Progress',
  pending: 'Pending', recovered: 'Recovered', closed: 'Closed',
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium  text-${STATUS_STYLES[status] ?? 'bg-zinc-800 text-zinc-400'}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}
