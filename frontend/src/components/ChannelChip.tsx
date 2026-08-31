import React from 'react'
import {
  MessageCircle,
  Mail,
  Phone,
  Link as LinkIcon,
  AlertTriangle,
  Calendar,
  BarChart,
  CheckCircle,
  Zap,
} from 'lucide-react'

export const CHANNEL_ICONS: Record<string, React.ElementType> = {
  send_whatsapp_msg:  MessageCircle,
  send_email_reminder:Mail,
  get_voice_call:     Phone,
  create_payment_link:LinkIcon,
  escalate_to_human:  AlertTriangle,
  log_promise_to_pay: Calendar,
  get_next_salary_date:BarChart,
  complete_case:      CheckCircle,
}

export const CHANNEL_LABEL: Record<string, string> = {
  send_whatsapp_msg:   'WhatsApp',
  send_email_reminder: 'Email',
  get_voice_call:      'Voice',
  create_payment_link: 'Payment Link',
  escalate_to_human:   'Escalated',
  log_promise_to_pay:  'Promise',
  get_next_salary_date:'Salary Date',
  complete_case:       'Completed',
}

export function ChannelChip({ action }: { action: string | null }) {
  if (!action) return <span className="text-zinc-600 text-xs">—</span>
  const Icon = CHANNEL_ICONS[action] ?? Zap
  const label = CHANNEL_LABEL[action] ?? action.replace(/_/g, ' ')
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-zinc-400">
      <Icon className="w-3.5 h-3.5 text-zinc-500" />
      <span>{label}</span>
    </span>
  )
}
