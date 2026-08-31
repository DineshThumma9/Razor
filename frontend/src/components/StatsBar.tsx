
import { Skeleton } from '@/components/ui/skeleton'
import type { Stats } from '../types'
import { fmt } from '../utils/formatters'

export function StatsBar({ stats, loading }: { stats: Stats | null; loading: boolean }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full mb-8">
        {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 rounded-xl bg-zinc-800/50" />)}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full mb-8">
      {/* At Risk */}
      <div className="bg-[#0f0f14] border border-zinc-800/60 rounded-xl p-5 flex flex-col justify-center">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">At Risk</p>
        <p className="text-3xl font-bold text-amber-400">₹{fmt(stats.total_at_risk_inr)}</p>
      </div>

      {/* Recovered */}
      <div className="bg-[#0f0f14] border border-zinc-800/60 rounded-xl p-5 flex flex-col justify-center">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Recovered</p>
        <p className="text-3xl font-bold text-emerald-400">₹{fmt(stats.recovered_amount_inr)}</p>
      </div>

      {/* Recovery Rate */}
      <div className="bg-[#0f0f14] border border-zinc-800/60 rounded-xl p-5 flex flex-col justify-center">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Recovery Rate</p>
        <p className="text-3xl font-bold text-violet-400">{stats.recovery_rate_pct}%</p>
      </div>

      {/* Active Cases */}
      <div className="bg-[#0f0f14] border border-zinc-800/60 rounded-xl p-5 flex flex-col justify-center">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Total Cases</p>
        <p className="text-3xl font-bold text-zinc-100">{stats.total_cases}</p>
      </div>
    </div>
  )
}
