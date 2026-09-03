import { useEffect, useState } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { useCaseStore } from './store/useCaseStore'

import { StatsBar } from './components/StatsBar'
import { EscalationPanel } from './components/EscalationPanel'
import { CaseTable } from './components/CaseTable'
import { CaseDrawer } from './components/CaseDrawer'

import SimulateSheet from './components/SimulateSheet'
import { Sheet, SheetContent } from '@/components/ui/sheet'

export default function App() {
  const [drawerWidth, setDrawerWidth] = useState(720)

  const {
    cases,
    stats,
    loadingCases,
    loadingStats,
    selectedCaseId,
    drawerOpen,
    sseConnected,
    setSelectedCaseId,
    setDrawerOpen,
    refreshData,
    initSSE,
  } = useCaseStore()

  useEffect(() => {
    refreshData()
    const cleanupSSE = initSSE()
    const id = setInterval(refreshData, 20000)
    return () => {
      cleanupSSE()
      clearInterval(id)
    }
  }, [refreshData, initSSE])

  const openDrawer = (id: string) => {
    setSelectedCaseId(id)
    setDrawerOpen(true)
  }

  const escalatedCases = cases.filter((c) => c.recovery_status === 'escalated')
  const recoveredCases = cases.filter((c) => c.recovery_status === 'recovered' || c.recovery_status === 'closed')
  const processingCases = cases.filter((c) => !['escalated', 'recovered', 'closed'].includes(c.recovery_status))

  return (
    <TooltipProvider delay={0}>
      <div className="flex flex-col h-screen overflow-hidden bg-[#0a0a0c] text-zinc-300 font-sans selection:bg-indigo-500/30">
        
        {/* Header (Top Navigation) */}
        <header className="bg-[#09090d]/80 backdrop-blur sticky top-0 z-40 shrink-0 border-b border-zinc-800/60">
          <div className="max-w-screen-xl mx-auto px-6 h-14 flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-violet-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span className="font-semibold text-zinc-100 tracking-tight">Renvue</span>
              <span className="text-zinc-700 mx-1">·</span>
              <span className="text-xs text-zinc-500">Recovery Ops</span>
            </div>

            <div className="flex items-center gap-2.5">
              {/* Sandbox Mode Badge */}
              <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[11px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                <span>SANDBOX MODE</span>
              </div>

              {/* Gateway Health Circuit Breaker */}
              <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900/90 border border-zinc-800 text-[11px] font-mono text-zinc-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>RAILS 100%</span>
              </div>

              {/* Live SSE Stream Connection Badge */}
              <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900/90 border border-zinc-800">
                <span className="relative flex h-2 w-2">
                  {sseConnected && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  )}
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${sseConnected ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                </span>
                <span className="text-[11px] font-mono tracking-tight text-zinc-400">
                  {sseConnected ? 'LIVE SSE' : 'CONNECTING...'}
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto">
          <main className="max-w-screen-xl mx-auto px-6 py-8">
            <div className="flex w-full justify-end mb-6 gap-3">
              <Button 
                variant="outline" 
                onClick={async () => {
                   if(confirm('Are you sure you want to clear all cases?')) {
                       const { clearAllCases } = await import('./api');
                       await clearAllCases();
                       refreshData();
                   }
                }}
                className="bg-red-950/20 border-red-900/50 text-red-500 hover:bg-red-900/40 hover:text-red-400"
              >
                Clear All Cases
              </Button>
              <SimulateSheet />
            </div>
            
            <StatsBar stats={stats} loading={loadingStats} />

            {/* Escalation panel */}
            <EscalationPanel
              cases={escalatedCases}
              onSelect={openDrawer}
              onApprove={refreshData}
            />

            {/* Processing Queue */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-semibold text-zinc-200">Active Processing Queue</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {loadingCases ? 'Loading…' : `${processingCases.length} active cases · live SSE updates`}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-zinc-700 bg-transparent text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 h-8 text-xs"
                  onClick={refreshData}
                >
                  Refresh
                </Button>
              </div>
              <CaseTable
                cases={processingCases}
                loading={loadingCases}
                onRowClick={openDrawer}
              />
            </div>

            {/* Success Section */}
            {recoveredCases.length > 0 && (
              <div className="mb-8">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-base font-semibold text-emerald-400">Successfully Recovered</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {recoveredCases.length} resolved cases
                    </p>
                  </div>
                </div>
                <CaseTable
                  cases={recoveredCases}
                  loading={loadingCases}
                  onRowClick={openDrawer}
                />
              </div>
            )}
          </main>
        </div>

        {/* Case Details Slide-Over Sheet */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent 
            side="right" 
            showCloseButton={false} 
            style={{ width: `${drawerWidth}px`, maxWidth: '95vw' }}
            className="bg-[#0d1117] border-l border-zinc-800 text-zinc-100 flex flex-col p-0 shadow-2xl transition-none"
          >
            <CaseDrawer
              caseId={selectedCaseId}
              open={drawerOpen}
              onClose={() => setDrawerOpen(false)}
              onAction={refreshData}
              width={drawerWidth}
              onResize={setDrawerWidth}
            />
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  )
}
