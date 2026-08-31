import { useState, useEffect } from 'react'
import { Sheet, SheetContent, SheetHeader } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { fetchCase, approveEscalation, closeCase } from '../api'
import type { Case } from '../types'
import { fmt } from '../utils/formatters'
import { StatusPill } from './StatusPill'
import { TypeBadge } from './TypeBadge'
import { AuditTimeline } from './AuditTimeline'

export function CaseDrawer({
  caseId,
  open,
  onClose,
  onAction,
}: {
  caseId: string | null
  open: boolean
  onClose: () => void
  onAction: () => void
}) {
  const [detail, setDetail] = useState<Case | null>(null)
  const [loading, setLoading] = useState(false)
  const [approving, setApproving] = useState(false)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    if (!caseId || !open) return
    setLoading(true)
    setDetail(null)
    fetchCase(caseId).then(setDetail).finally(() => setLoading(false))
  }, [caseId, open])

  const handleApprove = async () => {
    if (!detail) return
    setApproving(true)
    try {
      await approveEscalation(detail.case_id)
      onAction()
      onClose()
    } finally {
      setApproving(false)
    }
  }

  const handleClose = async () => {
    if (!detail) return
    setClosing(true)
    try {
      await closeCase(detail.case_id)
      onAction()
      onClose()
    } finally {
      setClosing(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:w-130 bg-[#0f0f14] border-l border-zinc-800/60 p-0 flex flex-col"
      >
        {loading && (
          <div className="p-6 flex flex-col gap-3">
            <Skeleton className="h-6 w-48 bg-zinc-800" />
            <Skeleton className="h-4 w-64 bg-zinc-800" />
            <Skeleton className="h-4 w-32 bg-zinc-800" />
            <Separator className="bg-zinc-800 my-2" />
            <Skeleton className="h-24 w-full bg-zinc-800" />
          </div>
        )}

        {detail && !loading && (
          <>
            {/* Header */}
            <div className="px-6 pt-6 pb-4 border-b border-zinc-800/60">
              <SheetHeader className="text-left p-0">
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Case Details</p>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="text-xl font-semibold text-zinc-100 truncate">{detail.customer.name}</h2>
                    <p className="text-sm text-zinc-500 mt-0.5">{detail.customer.email}</p>
                    <p className="text-sm text-zinc-500">{detail.customer.contact ? `+91 ${detail.customer.contact}` : '—'}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-2xl font-bold text-amber-400">₹{fmt(detail.amount_inr)}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">At Risk</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  <StatusPill status={detail.recovery_status} />
                  <TypeBadge type={detail.case_type} />
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-zinc-700/40 bg-zinc-800/40 text-zinc-400">
                    Attempt {detail.attempt_count}/3
                  </span>
                  {detail.decline_type && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-zinc-700/40 bg-zinc-800/40 text-zinc-400">
                      {detail.decline_type} decline
                    </span>
                  )}
                </div>
              </SheetHeader>
            </div>

            {/* Body — scrollable */}
            <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
              {/* Failure reason */}
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Issue</p>
                <div className="p-3 rounded-md bg-zinc-800/30 border border-zinc-800">
                  <p className="text-sm text-zinc-300 font-medium">{detail.failure_reason}</p>
                </div>
              </div>

              {/* Audit Trail */}
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Recovery Trail</p>
                <AuditTimeline entries={detail.audit_log ?? []} />
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-zinc-800/60 bg-zinc-900/30 flex gap-3">
              {detail.recovery_status === 'escalated' ? (
                <Button
                  onClick={handleApprove}
                  disabled={approving}
                  className="flex-1 bg-amber-500 hover:bg-amber-600 text-amber-950 font-medium"
                >
                  {approving ? 'Approving…' : 'Approve & Retry'}
                </Button>
              ) : (
                <Button
                  onClick={handleClose}
                  disabled={closing}
                  className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700"
                >
                  {closing ? 'Closing…' : 'Mark as Closed'}
                </Button>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
