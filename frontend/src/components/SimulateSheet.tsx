import { useState, useEffect } from 'react'
import { 
    Sheet, 
    SheetContent, 
    SheetHeader, 
    SheetTitle, 
    SheetTrigger,
    SheetClose
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Field, FieldContent, FieldLabel, FieldTitle } from "@/components/ui/field"
import { fetchCase, API_BASE_URL } from "../api"
import { useCaseStore } from "../store/useCaseStore"
import type { Case } from "../types"
import { 
    Send, 
    Loader2, 
    FastForward, 
    CheckCircle2, 
    Copy, 
    Check, 
    MessageSquare, 
    CreditCard, 
    Play, 
    ChevronRight,
    RotateCcw
} from "lucide-react"

interface ChatMessage {
    id: string
    sender: 'user' | 'agent' | 'system'
    text: string
    timestamp: Date
    isStatus?: boolean
    channel?: 'whatsapp' | 'email' | 'system'
}

function buildChatFromAuditLog(caseData: Case): ChatMessage[] {
    const msgs: ChatMessage[] = []
    
    // Initial failure entry
    msgs.push({
        id: `init-${caseData.case_id}`,
        sender: 'system',
        text: `Payment failure detected: ₹${(caseData.amount_inr || 0).toLocaleString()} (${caseData.failure_reason || 'Declined'})`,
        timestamp: caseData.first_seen_at ? new Date(caseData.first_seen_at) : new Date(),
        isStatus: true,
        channel: 'system',
    })

    if (caseData.audit_log && caseData.audit_log.length > 0) {
        caseData.audit_log.forEach((log, i) => {
            if (log.event_triggered === 'payment_failed') return

            const nextStr = log.next_contact ? ` · Next scheduled: ${new Date(log.next_contact).toLocaleDateString()}` : ''
            const text = (log.message || `Agent action: ${log.event_triggered.replace(/_/g, ' ')}`) + nextStr
            const isCust = log.direction === 'inbound' || log.event_triggered === 'customer_reply'
            const isSys = log.direction === 'system' || ['get_next_salary_date', 'log_promise_to_pay'].includes(log.event_triggered)
            
            msgs.push({
                id: `log-${caseData.case_id}-${i}-${log.event_triggered}`,
                sender: isCust ? 'user' : isSys ? 'system' : 'agent',
                text,
                timestamp: log.created_at ? new Date(log.created_at) : new Date(),
                isStatus: isSys,
                channel: (log.channel as any) || (isSys ? 'system' : 'whatsapp')
            })
        })
    }

    if (['recovered', 'closed', 'escalated'].includes(caseData.recovery_status)) {
        const terminalMsg = caseData.recovery_status === 'escalated'
            ? `Case escalated to human support (Attempt count: ${caseData.attempt_count}/3).`
            : `Case resolved and marked as ${caseData.recovery_status.toUpperCase()}.`
        msgs.push({
            id: `term-${caseData.case_id}`,
            sender: 'system',
            text: terminalMsg,
            timestamp: new Date(),
            isStatus: true,
            channel: 'system',
        })
    }

    return msgs
}

export function SimulateSheet() {
    const [step, setStep] = useState<1 | 2>(1)
    const [isSimulating, setIsSimulating] = useState(false)
    const [isPolling, setIsPolling] = useState(false)
    const [copied, setCopied] = useState(false)
    
    const [eventType, setEventType] = useState("order.failed")
    const [declineReason, setDeclineReason] = useState("Insufficient funds")

    const handleScenarioChange = (val: string) => {
        setEventType(val)
        if (val === "order.failed") setDeclineReason("Insufficient funds")
        else if (val === "subscription_failed") setDeclineReason("Mandate auto-debit failed")
        else if (val === "invoice_failed") setDeclineReason("Invoice overdue")
    }
    const [amount, setAmount] = useState(5000)
    const [name, setName] = useState("Dinesh")
    const [email, setEmail] = useState("test@example.com")
    const [phone, setPhone] = useState("9876543210")
    const [resumeCaseId, setResumeCaseId] = useState("")
    const [showResumeInput, setShowResumeInput] = useState(false)

    // Step 2 Simulation Data
    const [activeCaseId, setActiveCaseId] = useState<string | null>(null)
    const [activeCase, setActiveCase] = useState<Case | null>(null)
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
    const [replyText, setReplyText] = useState("")

    // Live real-time sync with Zustand store when SSE events update active case
    const storeCase = useCaseStore(state => state.cases.find(c => c.case_id === activeCaseId))

    useEffect(() => {
        if (storeCase && activeCaseId) {
            setActiveCase(storeCase)
            setChatHistory(buildChatFromAuditLog(storeCase))
            if (['recovered', 'closed', 'escalated'].includes(storeCase.recovery_status)) {
                setIsPolling(false)
            }
        }
    }, [storeCase, activeCaseId])

    const handleCopyId = (e: React.MouseEvent) => {
        e.stopPropagation()
        if (!activeCaseId) return
        navigator.clipboard.writeText(activeCaseId)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    const resetState = () => {
        setStep(1)
        setIsSimulating(false)
        setIsPolling(false)
        setActiveCaseId(null)
        setActiveCase(null)
        setChatHistory([])
        setReplyText("")
        setResumeCaseId("")
        setShowResumeInput(false)
    }

    const handleOpenChange = (open: boolean) => {
        if (!open) resetState()
    }

    const handleResumeEvent = async () => {
        const targetId = resumeCaseId.trim()
        if (!targetId) return
        setIsSimulating(true)
        try {
            const caseData = await fetchCase(targetId)
            if (caseData) {
                setActiveCaseId(caseData.case_id)
                setActiveCase(caseData)
                setChatHistory(buildChatFromAuditLog(caseData))
                setStep(2)
                setIsPolling(true)
            }
        } catch (error) {
            console.error("Failed to resume case", error)
        } finally {
            setIsSimulating(false)
        }
    }

    const handleFireEvent = async (e?: React.FormEvent) => {
        if (e) e.preventDefault()
        if (showResumeInput && resumeCaseId.trim()) {
            return handleResumeEvent()
        }
        setIsSimulating(true)

        const payload = {
            event_type: eventType,
            decline_reason: declineReason,
            amount: Number(amount),
            name: name || "Dinesh",
            email: email || "test@example.com",
            phone: phone || "9876543210",
        }

        try {
            const res = await fetch(`${API_BASE_URL}/fake-event`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
            const data = await res.json()
            
            if (data.id) {
                setActiveCaseId(data.id)
                setChatHistory([
                    {
                        id: `init-${data.id}`,
                        sender: 'system',
                        text: `Payment failure detected: ₹${amount.toLocaleString()} (${declineReason})`,
                        timestamp: new Date(),
                        isStatus: true
                    }
                ])
                setStep(2)
                setIsPolling(true)
            }
        } catch (error) {
            console.error("Simulation trigger failed", error)
        } finally {
            setIsSimulating(false)
        }
    }

    const pollCaseStatus = async () => {
        if (!activeCaseId) return
        try {
            const caseData = await fetchCase(activeCaseId)
            if (!caseData) return
            setActiveCase(caseData)
            setChatHistory(buildChatFromAuditLog(caseData))

            if (caseData.recovery_status === "recovered" || caseData.recovery_status === "closed" || caseData.recovery_status === "escalated") {
                setIsPolling(false)
            }
        } catch (error) {
            console.error("Poll failed", error)
        }
    }

    const handleAction = async (actionType: 'pay' | 'ignore' | 'reply', msgContent?: string) => {
        if (!activeCaseId) return
        setIsSimulating(true)

        if (actionType === 'reply' && msgContent) {
            setChatHistory(prev => [...prev, {
                id: `pending-${Date.now()}`,
                sender: 'user',
                text: msgContent,
                timestamp: new Date(),
                channel: 'whatsapp'
            }])
            setReplyText("")
        }

        try {
            await fetch(`${API_BASE_URL}/fake-action`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    case_id: activeCaseId,
                    actions: actionType,
                    messages: msgContent || "",
                })
            })
            // Poll after short delay to let agent execute and write audit log
            setTimeout(pollCaseStatus, 1200)
        } catch (error) {
            console.error("Action dispatch failed", error)
        } finally {
            setIsSimulating(false)
        }
    }

    useEffect(() => {
        if (!isPolling || !activeCaseId) return
        const interval = setInterval(pollCaseStatus, 2500)
        return () => clearInterval(interval)
    }, [isPolling, activeCaseId])

    return (
        <Sheet onOpenChange={handleOpenChange}>
            <SheetTrigger render={
                <Button className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 h-9 shadow-sm">
                    <Play className="w-3.5 h-3.5 mr-1.5" /> Simulate Events
                </Button>
            } />
            
            <SheetContent className="bg-[#0b0f17] border-l border-zinc-800 text-zinc-100 flex flex-col gap-0 p-0 overflow-hidden w-full sm:max-w-lg shadow-2xl">
                {/* Clean Header */}
                <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-950/40 flex items-center justify-between shrink-0">
                    <SheetHeader>
                        <SheetTitle className="text-zinc-100 text-base font-semibold tracking-tight flex items-center gap-2">
                            <span>{step === 1 ? "Recovery Simulator" : "Live Recovery Testbench"}</span>
                            {step === 2 && activeCaseId && (
                                <button 
                                    onClick={handleCopyId}
                                    className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors"
                                    title="Copy Case ID"
                                >
                                    {copied ? (
                                        <>
                                            <Check className="w-3 h-3 text-emerald-400" />
                                            <span className="text-emerald-400 font-medium">Copied</span>
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="w-3 h-3 text-zinc-500" />
                                            <span className="text-zinc-400 truncate max-w-[100px]">{activeCaseId}</span>
                                        </>
                                    )}
                                </button>
                            )}
                        </SheetTitle>
                    </SheetHeader>
                    {step === 2 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={resetState}
                            className="text-xs text-zinc-400 hover:text-zinc-100 h-8 px-2"
                        >
                            <RotateCcw className="w-3.5 h-3.5 mr-1" /> New Run
                        </Button>
                    )}
                </div>
                
                {step === 1 ? (
                    // ----------------------------------------------------
                    // STEP 1: CONCISE CONFIGURATION FORM
                    // ----------------------------------------------------
                    <div className="flex-1 overflow-y-auto p-6 space-y-6">
                        {/* Scenario Presets */}
                        <div className="space-y-3">
                            <Label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                                Select Failure Scenario
                            </Label>
                            <RadioGroup value={eventType} onValueChange={handleScenarioChange} className="gap-2.5">
                                <FieldLabel htmlFor="sc-soft" className="border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 hover:border-zinc-700 rounded-xl cursor-pointer transition-all has-[[data-checked]]:border-indigo-500/60 has-[[data-checked]]:bg-indigo-500/10">
                                    <Field orientation="horizontal" className="p-3.5 w-full justify-between items-center flex">
                                        <FieldContent>
                                            <FieldTitle className="text-sm font-semibold text-zinc-100">Soft Decline (Insufficient Funds)</FieldTitle>
                                            <p className="text-xs text-zinc-400 mt-0.5">Schedules automated retry on upcoming salary milestone (15th or Friday).</p>
                                        </FieldContent>
                                        <RadioGroupItem value="order.failed" id="sc-soft" className="border-zinc-600 text-indigo-500 h-4 w-4" />
                                    </Field>
                                </FieldLabel>
                                
                                <FieldLabel htmlFor="sc-sub" className="border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 hover:border-zinc-700 rounded-xl cursor-pointer transition-all has-[[data-checked]]:border-indigo-500/60 has-[[data-checked]]:bg-indigo-500/10">
                                    <Field orientation="horizontal" className="p-3.5 w-full justify-between items-center flex">
                                        <FieldContent>
                                            <FieldTitle className="text-sm font-semibold text-zinc-100">Subscription Auto-Debit Failure</FieldTitle>
                                            <p className="text-xs text-zinc-400 mt-0.5">Recurring mandate failed. Dispatches OTP auth link if over ₹15,000.</p>
                                        </FieldContent>
                                        <RadioGroupItem value="subscription_failed" id="sc-sub" className="border-zinc-600 text-indigo-500 h-4 w-4" />
                                    </Field>
                                </FieldLabel>

                                <FieldLabel htmlFor="sc-invoice" className="border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 hover:border-zinc-700 rounded-xl cursor-pointer transition-all has-[[data-checked]]:border-indigo-500/60 has-[[data-checked]]:bg-indigo-500/10">
                                    <Field orientation="horizontal" className="p-3.5 w-full justify-between items-center flex">
                                        <FieldContent>
                                            <FieldTitle className="text-sm font-semibold text-zinc-100">Overdue Invoice</FieldTitle>
                                            <p className="text-xs text-zinc-400 mt-0.5">High-urgency email & payment link reminder sent.</p>
                                        </FieldContent>
                                        <RadioGroupItem value="invoice_failed" id="sc-invoice" className="border-zinc-600 text-indigo-500 h-4 w-4" />
                                    </Field>
                                </FieldLabel>
                            </RadioGroup>
                        </div>

                        {/* Customer & Amount Details */}
                        <div className="space-y-4 pt-2 border-t border-zinc-800/80">
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <Label className="text-xs text-zinc-400">Customer Name</Label>
                                    <Input
                                        value={name}
                                        onChange={e => setName(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') handleFireEvent(e) }}
                                        className="bg-zinc-900 border-zinc-800 text-zinc-100 h-9 text-xs"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="text-xs text-zinc-400">Amount (₹ INR)</Label>
                                    <Input
                                        type="number"
                                        value={amount}
                                        onChange={e => setAmount(Number(e.target.value))}
                                        onKeyDown={e => { if (e.key === 'Enter') handleFireEvent(e) }}
                                        className="bg-zinc-900 border-zinc-800 text-zinc-100 font-mono h-9 text-xs"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <Label className="text-xs text-zinc-400">Email Address</Label>
                                    <Input
                                        value={email}
                                        onChange={e => setEmail(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') handleFireEvent(e) }}
                                        className="bg-zinc-900 border-zinc-800 text-zinc-100 h-9 text-xs"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="text-xs text-zinc-400">Phone (+91)</Label>
                                    <Input
                                        value={phone}
                                        onChange={e => setPhone(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') handleFireEvent(e) }}
                                        className="bg-zinc-900 border-zinc-800 text-zinc-100 font-mono h-9 text-xs"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Collapsible Resume Option */}
                        <div className="pt-2 border-t border-zinc-800/80">
                            {!showResumeInput ? (
                                <button
                                    type="button"
                                    onClick={() => setShowResumeInput(true)}
                                    className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex items-center gap-1"
                                >
                                    <ChevronRight className="w-3 h-3" /> Resume an existing case by ID
                                </button>
                            ) : (
                                <div className="space-y-2">
                                    <Label className="text-xs text-zinc-400">Existing Case ID</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            placeholder="pay_fail_..."
                                            value={resumeCaseId}
                                            onChange={e => setResumeCaseId(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault()
                                                    handleResumeEvent()
                                                }
                                            }}
                                            className="bg-zinc-900 border-zinc-800 text-zinc-200 font-mono h-9 text-xs"
                                        />
                                        <Button
                                            type="button"
                                            onClick={handleResumeEvent}
                                            disabled={!resumeCaseId.trim() || isSimulating}
                                            variant="secondary"
                                            className="h-9 px-3 text-xs shrink-0"
                                        >
                                            Resume
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Footer Action */}
                        <div className="pt-4 border-t border-zinc-800 flex justify-end gap-3">
                            <SheetClose className="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
                                Cancel
                            </SheetClose>
                            <Button 
                                onClick={handleFireEvent} 
                                disabled={isSimulating}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold h-9 px-5 shadow-sm"
                            >
                                {isSimulating ? (
                                    <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> {showResumeInput && resumeCaseId.trim() ? "Resuming..." : "Starting..."}</>
                                ) : (
                                    showResumeInput && resumeCaseId.trim() ? "Resume Case" : "Launch Scenario"
                                )}
                            </Button>
                        </div>
                    </div>
                ) : (
                    // ----------------------------------------------------
                    // STEP 2: PROFESSIONAL LIVE TESTBENCH
                    // ----------------------------------------------------
                    <div className="flex flex-col h-full overflow-hidden">
                        {/* Live Case Telemetry Bar */}
                        <div className="px-6 py-2.5 border-b border-zinc-800 bg-zinc-950/60 flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                                <span className="text-zinc-400">Customer: <strong className="text-zinc-200">{name}</strong></span>
                                <span className="text-zinc-600">·</span>
                                <span className="text-zinc-400">Amount: <strong className="text-amber-400 font-mono">₹{amount.toLocaleString()}</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                {isPolling && (
                                    <span className="relative flex h-2 w-2">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                    </span>
                                )}
                                <span className="font-semibold text-xs text-zinc-300 uppercase tracking-wider">
                                    {activeCase?.recovery_status || 'Active'}
                                </span>
                            </div>
                        </div>

                        {/* Interactive Message Thread */}
                        <div className="flex-1 overflow-y-auto p-5 space-y-4">
                            {chatHistory.map((msg) => {
                                if (msg.isStatus) {
                                    return (
                                        <div key={msg.id} className="flex justify-center my-2">
                                            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-400">
                                                <CheckCircle2 className="w-3 h-3 text-indigo-400 shrink-0" />
                                                <span>{msg.text}</span>
                                            </div>
                                        </div>
                                    )
                                }

                                if (msg.sender === 'user') {
                                    return (
                                        <div key={msg.id} className="flex flex-col items-start max-w-[85%] mr-auto">
                                            <div className="text-[10px] font-medium text-zinc-500 px-1 mb-0.5">
                                                {name} (Customer)
                                            </div>
                                            <div className="bg-zinc-800 border border-zinc-700/60 text-zinc-100 rounded-2xl rounded-tl-sm px-4 py-2.5 text-xs shadow-sm leading-relaxed">
                                                <p>{msg.text}</p>
                                            </div>
                                        </div>
                                    )
                                }

                                // Outbound Agent Message
                                return (
                                    <div key={msg.id} className="flex flex-col items-end max-w-[88%] ml-auto">
                                        <div className="text-[10px] font-medium text-emerald-500 px-1 mb-0.5 flex items-center gap-1">
                                            <MessageSquare className="w-3 h-3" /> Renvue Recovery Agent
                                        </div>
                                        <div className="bg-[#0b3328] border border-emerald-700/40 text-emerald-50 rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs shadow-sm leading-relaxed">
                                            <p>{msg.text}</p>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>

                        {/* Action Panel */}
                        <div className="p-4 bg-zinc-950 border-t border-zinc-800 space-y-3 shrink-0">
                            {/* Fast-Forward & Settle Controls */}
                            <div className="flex gap-2">
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="flex-1 bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-200 text-xs h-9 font-medium"
                                    onClick={() => handleAction('ignore')}
                                    disabled={isSimulating}
                                    title="Simulate time passing to the next scheduled retry date"
                                >
                                    <FastForward className="w-3.5 h-3.5 mr-1.5 text-indigo-400" />
                                    Fast-Forward (+3 Days)
                                </Button>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="flex-1 bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-emerald-400 hover:text-emerald-300 text-xs h-9 font-medium"
                                    onClick={() => handleAction('pay')}
                                    disabled={isSimulating}
                                >
                                    <CreditCard className="w-3.5 h-3.5 mr-1.5" />
                                    Settle Payment
                                </Button>
                            </div>

                            {/* Customer Inbound Preset Chips */}
                            <div className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none">
                                <span className="text-[10px] uppercase font-semibold text-zinc-400 shrink-0 mr-1">Quick Reply:</span>
                                <button
                                    type="button"
                                    onClick={() => handleAction('reply', 'I will pay on the 15th once salary is credited')}
                                    disabled={isSimulating}
                                    className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:text-zinc-100 shrink-0 transition-colors"
                                >
                                    "Promise to pay on 15th"
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleAction('reply', 'My card was blocked, please send a new payment link')}
                                    disabled={isSimulating}
                                    className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:text-zinc-100 shrink-0 transition-colors"
                                >
                                    "Send new link"
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleAction('reply', 'STOP')}
                                    disabled={isSimulating}
                                    className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-rose-400 shrink-0 transition-colors"
                                >
                                    "STOP"
                                </button>
                            </div>

                            {/* Freeform Customer Reply */}
                            <form 
                                className="flex items-center gap-2"
                                onSubmit={(e) => {
                                    e.preventDefault()
                                    if (replyText.trim()) handleAction('reply', replyText)
                                }}
                            >
                                <Input 
                                    value={replyText}
                                    onChange={e => setReplyText(e.target.value)}
                                    placeholder="Simulate customer reply..." 
                                    className="bg-zinc-900 border-zinc-800 focus-visible:ring-indigo-500 text-zinc-100 h-9 text-xs"
                                    disabled={isSimulating}
                                />
                                <Button 
                                    type="submit" 
                                    size="icon" 
                                    className="h-9 w-9 shrink-0 bg-indigo-600 hover:bg-indigo-500 text-white"
                                    disabled={!replyText.trim() || isSimulating}
                                >
                                    {isSimulating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                                </Button>
                            </form>
                        </div>
                    </div>
                )}
            </SheetContent>
        </Sheet>
    )
}

export default SimulateSheet