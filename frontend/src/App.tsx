import { useState, useEffect, useCallback } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { fetchCases, fetchStats } from './api'
import type { Case, Stats } from './types'

import { StatsBar } from './components/StatsBar'
import { EscalationPanel } from './components/EscalationPanel'
import { CaseTable } from './components/CaseTable'
import { CaseDrawer } from './components/CaseDrawer'

export default function App() {
  const [cases, setCases] = useState<Case[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loadingCases, setLoadingCases] = useState(true)
  const [loadingStats, setLoadingStats] = useState(true)
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([fetchCases(), fetchStats()])
      setCases(c)
      setStats(s)
    } catch {
      // silently ignore polling errors
    } finally {
      setLoadingCases(false)
      setLoadingStats(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 10000)
    return () => clearInterval(id)
  }, [refresh])

  const openDrawer = (id: string) => {
    setSelectedCaseId(id)
    setDrawerOpen(true)
  }

  const escalatedCases = cases.filter((c) => c.recovery_status === 'escalated')

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-[#09090d] text-zinc-100 font-sans">
        {/* Nav */}
        <header className="bg-[#09090d]/80 backdrop-blur sticky top-0 z-40">
          <div className="max-w-screen-xl mx-auto px-6 h-14 flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-violet-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span className="font-semibold text-zinc-100 tracking-tight">Renvue</span>
              <span className="text-zinc-700 mx-1">·</span>
              <span className="text-xs text-zinc-500">Recovery Ops</span>
            </div>
          </div>
        </header>

        {/* Main */}
        <main className="max-w-screen-xl h-full mx-auto px-6 py-8">
          {/* New prominent Stats Bar */}

          {/* Escalation panel */}
          <EscalationPanel
            cases={escalatedCases}
            onSelect={openDrawer}
            onApprove={refresh}
          />

          
          {/* Queue header */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-base font-semibold text-zinc-200">Recovery Queue</h1>
              <p className="text-xs text-zinc-500 mt-0.5">
                {loadingCases ? 'Loading…' : `${cases.length} cases · auto-refreshes every 10s`}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 bg-transparent text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 h-8 text-xs"
              onClick={refresh}
            >
              Refresh
            </Button>
          </div>

          <StatsBar stats={stats} loading={loadingStats} />

          <CaseTable
            cases={cases}
            loading={loadingCases}
            onRowClick={openDrawer}
          />
        </main>

        {/* Case detail drawer */}
        <CaseDrawer
          caseId={selectedCaseId}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          onAction={refresh}
        />
      </div>
    </TooltipProvider>
  )
}
