import type { AuditEntry } from '../types'
import { fmtTs } from '../utils/formatters'
import { Message, MessageHeader, MessageFooter } from '@/components/ui/message'
import { Bubble } from '@/components/ui/bubble'

export function AuditTimeline({ 
  entries, 
  customerName, 
}: { 
  entries: AuditEntry[]
  customerName?: string
}) {
  if (!entries || entries.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-zinc-500">
        No events recorded yet.
      </div>
    )
  }

  // Pure Chronological Order: Earliest -> Latest
  const chronological = [...entries]

  return (
    <div className="relative pl-6 border-l border-zinc-800 space-y-7 ml-2">
      {chronological.map((e, idx) => {
        const isWhatsApp = e.channel === 'whatsapp' || e.event_triggered === 'send_whatsapp_msg'
        const isEmail = e.channel === 'email' || e.event_triggered === 'send_email_reminder'
        const isCustomer = e.direction === 'inbound' || e.event_triggered === 'customer_reply'
        const isPaymentLink = e.channel === 'link' || e.event_triggered === 'create_payment_link'
        const isEscalation = e.event_triggered === 'escalate_to_human'
        const isInitialFailure = e.event_triggered === 'payment_failed'
        const isSalary = e.event_triggered === 'get_next_salary_date'
        const isPromiseToPay = e.event_triggered === 'log_promise_to_pay'

        // 1. CHAT MESSAGE: Inbound from Customer (Shadcn Message & Bubble)
        if (isCustomer && e.message) {
          return (
            <div key={idx} className="relative group">
              {/* Event Marker on timeline */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-zinc-600 border-2 border-[#0d1117]" />
              
              <Message className="items-start max-w-[85%] mr-auto">
                <MessageHeader className="text-zinc-400 text-xs">
                  {customerName || 'Customer'}
                </MessageHeader>
                <Bubble variant="inbound">
                  {e.message}
                </Bubble>
                <MessageFooter>
                  {e.created_at ? fmtTs(e.created_at) : ''}
                </MessageFooter>
              </Message>
            </div>
          )
        }

        // 2. CHAT MESSAGE: Outbound Agent WhatsApp / Message (Shadcn Message & Bubble)
        if (isWhatsApp && !isCustomer && e.message) {
          return (
            <div key={idx} className="relative group">
              {/* Event Marker on timeline */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-[#0d1117]" />
              
              <Message className="items-end max-w-[85%] ml-auto">
                <Bubble variant="outbound">
                  {e.message}
                </Bubble>
                <MessageFooter className="text-right flex items-center justify-end gap-1.5 text-zinc-500">
                  <span>Delivered</span>
                  <span>·</span>
                  <span>{e.created_at ? fmtTs(e.created_at) : ''}</span>
                </MessageFooter>
              </Message>
            </div>
          )
        }

        // 3. CHAT MESSAGE: Outbound Email
        if (isEmail && e.message) {
          return (
            <div key={idx} className="relative group">
              {/* Event Marker on timeline */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-[#0d1117]" />
              
              <Message className="items-end max-w-[85%] ml-auto">
                <Bubble variant="outbound" className="bg-blue-600/90 text-white">
                  <div className="text-xs font-medium text-blue-200 mb-1">Email Reminder</div>
                  {e.message}
                </Bubble>
                <MessageFooter className="text-right">
                  Sent · {e.created_at ? fmtTs(e.created_at) : ''}
                </MessageFooter>
              </Message>
            </div>
          )
        }

        // 4. CHAT MESSAGE: Outbound Payment Link
        if (isPaymentLink && e.message) {
          return (
            <div key={idx} className="relative group">
              {/* Event Marker on timeline */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-[#0d1117]" />
              
              <Message className="items-end max-w-[85%] ml-auto">
                <Bubble variant="outbound">
                  <div className="text-xs font-medium text-blue-200 mb-1">Payment Link</div>
                  <div className="font-mono text-xs text-white break-all">{e.message}</div>
                </Bubble>
                <MessageFooter className="text-right">
                  Generated · {e.created_at ? fmtTs(e.created_at) : ''}
                </MessageFooter>
              </Message>
            </div>
          )
        }

        // 5. EVENT: Payment Decline Event
        if (isInitialFailure) {
          return (
            <div key={idx} className="relative">
              {/* Rose Marker Dot */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-rose-500 border-2 border-[#0d1117]" />
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-zinc-200">Payment Failed</span>
                  <span className="text-zinc-600">·</span>
                  <span className="text-[11px] font-mono text-zinc-500">{e.created_at ? fmtTs(e.created_at) : ''}</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {e.message || `Transaction decline recorded: ₹${e.amount}`}
                </p>
              </div>
            </div>
          )
        }

        // 6. EVENT: Escalated to Human Operations
        if (isEscalation) {
          return (
            <div key={idx} className="relative">
              {/* Rose Marker Dot */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-rose-500 border-2 border-[#0d1117]" />
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-rose-400">Escalated to Human</span>
                  <span className="text-zinc-600">·</span>
                  <span className="text-[11px] font-mono text-zinc-500">{e.created_at ? fmtTs(e.created_at) : ''}</span>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {e.message || 'Automated recovery sequence ended without settlement.'}
                </p>
              </div>
            </div>
          )
        }

        // 7. EVENT: Salary Milestone / Promise to Pay Scheduled
        if (isSalary || isPromiseToPay) {
          return (
            <div key={idx} className="relative">
              {/* Indigo Marker Dot */}
              <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-indigo-500 border-2 border-[#0d1117]" />
              <div className="space-y-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-zinc-200">
                    {isSalary ? 'Milestone Scheduled' : 'Promise to Pay'}
                  </span>
                  <span className="text-zinc-600">·</span>
                  <span className="text-[11px] font-mono text-zinc-500">{e.created_at ? fmtTs(e.created_at) : ''}</span>
                </div>
                <p className="text-xs text-zinc-400">
                  {e.message || 'Follow-up timeline calculated.'}
                </p>
                {e.next_contact && (
                  <p className="text-[11px] font-mono text-indigo-400 mt-1">
                    Scheduled retry: {fmtTs(e.next_contact)}
                  </p>
                )}
              </div>
            </div>
          )
        }

        // 8. GENERIC EVENT
        return (
          <div key={idx} className="relative">
            <div className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-zinc-600 border-2 border-[#0d1117]" />
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-300 capitalize">{e.event_triggered.replace(/_/g, ' ')}</span>
              <span className="font-mono text-zinc-500">{e.created_at ? fmtTs(e.created_at) : ''}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
