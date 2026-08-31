const TYPE_STYLES: Record<string, string> = {
  failed_payment:     'bg-transparent text-violet-400 border-violet-500/30',
  abandoned_checkout: 'bg-transparent text-sky-400 border-sky-500/30',
  failed_subscription:'bg-transparent text-indigo-400 border-indigo-500/30',
  overdue_invoice:    'bg-transparent text-orange-400 border-orange-500/30',
}

export function TypeBadge({ type }: { type: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${TYPE_STYLES[type] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}>
      {type.replace(/_/g, ' ')}
    </span>
  )
}
