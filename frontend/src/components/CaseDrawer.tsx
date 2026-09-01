import { useState, useEffect } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
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
  const [error, setError] = useState<string | null>(null)
  const [approving, setApproving] = useState(false)
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    if (!caseId || !open) return
    setLoading(true)
    setDetail(null)
    setError(null)
    fetchCase(caseId)
      .then(setDetail)
      .catch((err) => setError(err?.message || 'Failed to load case details'))
      .finally(() => setLoading(false))
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
    <div className="h-full bg-[#0f0f14] border-l border-zinc-800/60 p-0 flex flex-col relative">
      {loading && (
        <div className="p-6 flex flex-col gap-3">
          <Skeleton className="h-6 w-48 bg-zinc-800" />
          <Skeleton className="h-4 w-64 bg-zinc-800" />
          <Skeleton className="h-4 w-32 bg-zinc-800" />
          <Separator className="bg-zinc-800 my-2" />
          <Skeleton className="h-24 w-full bg-zinc-800" />
        </div>
      )}

      {error && !loading && (
        <div className="p-6 flex flex-col items-center justify-center text-center h-full">
          <p className="text-sm text-red-400 mb-2">{error}</p>
          <button onClick={onClose} className="text-xs text-zinc-500 hover:text-zinc-300 underline">Close</button>
        </div>
      )}

      {!detail && !loading && !error && (
        <div className="p-6 flex flex-col items-center justify-center text-center h-full text-zinc-500 text-sm">
          Select a case to view details
        </div>
      )}

      {detail && !loading && (
        <>
          {/* Header */}
          <div className="px-6 pt-6 pb-4 border-b border-zinc-800/60">
            <div className="text-left p-0">
              <div className="flex justify-between items-center mb-1">
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Case Details</p>
                <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
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
            </div>
          </div>

          {/* Body — scrollable */}
          <ScrollArea className="flex-1 px-6 py-4">
            <div className="flex flex-col gap-6">
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
          </ScrollArea>

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
    </div>
  )
}
