import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet"
import {
    Field,
    FieldContent,
    FieldLabel,
    FieldTitle,
} from "@/components/ui/field"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { PhoneCall, Mail, User, Send, Bot, Loader2, CheckCircle2 } from "lucide-react"
import { useState, useEffect } from "react"
import { simulateFire, simulateAction, fetchCase } from "../api"
import type { Case } from "../types"

// Simple chat message type for the UI
type ChatMessage = {
    id: string;
    sender: "agent" | "user";
    text: string;
    timestamp: Date;
    isStatus?: boolean;
}

const SimulateSheet = () => {
    // State machine: 1 (Form) -> 2 (Chat/Action)
    const [step, setStep] = useState<1 | 2>(1);
    
    // Step 1 Form State
    const [eventType, setEventType] = useState("order.failed");
    const [amount, setAmount] = useState("5000");
    const [name, setName] = useState("Dinesh");
    const [email, setEmail] = useState("");
    const [phone, setPhone] = useState("");
    const [declineReason, setDeclineReason] = useState("Insufficient funds");
    
    // Simulation State
    const [isSimulating, setIsSimulating] = useState(false);
    const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
    const [resumeCaseId, setResumeCaseId] = useState("");
    const [activeCase, setActiveCase] = useState<Case | null>(null);
    
    // Step 2 Chat State
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [replyText, setReplyText] = useState("");
    const [isPolling, setIsPolling] = useState(false);

    // Reset state when opening/closing
    const handleOpenChange = (open: boolean) => {
        if (!open) {
            // Reset after a delay so animation finishes
            setTimeout(() => {
                setStep(1);
                setActiveCaseId(null);
                setChatHistory([]);
                setIsSimulating(false);
            }, 300);
        }
    };

    // Trigger the initial simulation
    const handleFireEvent = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSimulating(true);
        try {
            const res = await simulateFire({
                event_type: eventType,
                decline_reason: declineReason,
                amount: (parseInt(amount) || 5000) * 100,
                name: name || "Test User",
                email: email || "test@example.com",
                phone: phone || "9876543210"
            });
            
            setActiveCaseId(res.id);
            
            // Add initial system message
            setChatHistory([{
                id: Date.now().toString(),
                sender: "agent",
                text: `Event ${eventType} fired. Agent is analyzing the case...`,
                timestamp: new Date(),
                isStatus: true
            }]);
            
            setStep(2);
            setIsPolling(true);
        } catch (error) {
            console.error("Failed to fire event", error);
        } finally {
            setIsSimulating(false);
        }
    };

    const handleResumeEvent = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!resumeCaseId) return;
        setIsSimulating(true);
        try {
            setActiveCaseId(resumeCaseId);
            
            // Add initial system message
            setChatHistory([{
                id: Date.now().toString(),
                sender: "agent",
                text: `Resumed session for case ${resumeCaseId}...`,
                timestamp: new Date(),
                isStatus: true
            }]);
            
            setStep(2);
            setIsPolling(true);
        } catch (error) {
            console.error("Failed to resume event", error);
        } finally {
            setIsSimulating(false);
        }
    };

    // Customer Actions
    const handleAction = async (actionType: "reply" | "pay" | "ignore", messageText: string = "") => {
        if (!activeCaseId) return;
        
        setIsSimulating(true);
        try {
            if (actionType === "reply" && messageText) {
                setChatHistory(prev => [...prev, {
                    id: Date.now().toString(),
                    sender: "user",
                    text: messageText,
                    timestamp: new Date()
                }]);
                setReplyText("");
            } else if (actionType === "pay") {
                setChatHistory(prev => [...prev, {
                    id: Date.now().toString(),
                    sender: "user",
                    text: "💰 Paid via link",
                    timestamp: new Date(),
                    isStatus: true
                }]);
            } else if (actionType === "ignore") {
                setChatHistory(prev => [...prev, {
                    id: Date.now().toString(),
                    sender: "user",
                    text: "🙈 Ignored communication",
                    timestamp: new Date(),
                    isStatus: true
                }]);
            }

            // Call the backend
            await simulateAction({
                case_id: activeCaseId,
                actions: actionType,
                messages: messageText,
                customer: {
                    name: activeCase?.customer?.name || name || "Test User",
                    email: activeCase?.customer?.email || email || "test@example.com",
                    contact: activeCase?.customer?.contact || phone || "9876543210"
                }
            });

            // Force an immediate poll to see agent's reaction
            pollCaseStatus();
        } catch (error) {
            console.error("Action failed", error);
        } finally {
            setIsSimulating(false);
        }
    };

    // Polling logic to watch the agent's actions
    const pollCaseStatus = async () => {
        if (!activeCaseId) return;
        try {
            const caseData = await fetchCase(activeCaseId);
            setActiveCase(caseData);
            
            const latestLog = caseData.audit_log?.[caseData.audit_log.length - 1];
            if (latestLog) {
                const nextStr = latestLog.next_contact ? ` (Next retry: ${new Date(latestLog.next_contact).toLocaleDateString()})` : '';
                const actionMsg = `Agent: ${latestLog.event_triggered} [Attempt ${caseData.attempt_count}] -> ${latestLog.recovery_status}${nextStr}`;
                setChatHistory(prev => {
                    // Avoid duplicating the exact same status message
                    if (prev.length > 0 && prev[prev.length - 1].text === actionMsg) return prev;
                    return [...prev, {
                        id: Date.now().toString() + Math.random(),
                        sender: "agent",
                        text: actionMsg,
                        timestamp: new Date(),
                        isStatus: true
                    }];
                });
            }

            if (caseData.recovery_status === "recovered" || caseData.recovery_status === "closed" || caseData.recovery_status === "escalated") {
                setIsPolling(false);
                const terminalMsg = caseData.recovery_status === "escalated"
                    ? `🚨 Case is now ESCALATED to human support (Attempt count: ${caseData.attempt_count}).`
                    : `Case is now ${caseData.recovery_status}.`;
                setChatHistory(prev => {
                    if (prev.length > 0 && prev[prev.length - 1].text === terminalMsg) return prev;
                    return [...prev, {
                        id: Date.now().toString(),
                        sender: "agent",
                        text: terminalMsg,
                        timestamp: new Date(),
                        isStatus: true
                    }];
                });
            }
        } catch (error) {
            console.error("Poll failed", error);
        }
    };

    useEffect(() => {
        if (!isPolling || !activeCaseId) return;
        const interval = setInterval(pollCaseStatus, 2500);
        return () => clearInterval(interval);
    }, [isPolling, activeCaseId]);


    return (
        <Sheet onOpenChange={handleOpenChange}>
            <SheetTrigger render={<Button className='bg-red-700/90 text-white hover:bg-red-600 rounded-full px-4 text-sm font-medium transition-colors shadow-sm shadow-red-900/20'>
                    Simulate Events
                </Button>} />
            
            <SheetContent className="bg-[#09090d] border-l border-zinc-800 text-zinc-100 flex flex-col gap-0 p-0 overflow-hidden w-full sm:max-w-md">
                <div className="p-6 pb-4 border-b border-zinc-800/60 shrink-0">
                    <SheetHeader>
                        <SheetTitle className="text-zinc-100 text-lg font-semibold tracking-tight flex items-center justify-between">
                            <span>{step === 1 ? "Simulate Event" : "Live Agent Simulation"}</span>
                            {step === 2 && activeCaseId && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(activeCaseId); }}
                                    className="flex items-center gap-1.5 text-[11px] font-mono text-zinc-400 bg-zinc-800/60 hover:bg-zinc-700 hover:text-zinc-200 px-2 py-1 rounded transition-colors"
                                    title="Copy Case ID"
                                >
                                    <span className="truncate max-w-[120px]">{activeCaseId}</span>
                                    <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                    </svg>
                                </button>
                            )}
                        </SheetTitle>
                        <SheetDescription className="text-zinc-400 text-sm mt-1">
                            {step === 1 
                                ? "Trigger a simulated failure event to test the recovery flow and agent behaviors."
                                : "Act as the customer. Reply to the agent or take quick actions."}
                        </SheetDescription>
                    </SheetHeader>
                </div>
                
                {step === 1 ? (
                    // ----------------------------------------------------
                    // STEP 1: CONFIGURATION FORM
                    // ----------------------------------------------------
                    <>
                        <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                            <div className="space-y-3 pb-6 border-b border-zinc-800/60">
                                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Resume Existing Case</Label>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Paste Case ID (e.g. pay_fail_...)"
                                        value={resumeCaseId}
                                        onChange={(e) => setResumeCaseId(e.target.value)}
                                        className="bg-zinc-900/50 border-zinc-800/80 focus-visible:ring-violet-500/30 text-zinc-200 placeholder:text-zinc-600 h-10"
                                    />
                                    <Button 
                                        onClick={handleResumeEvent}
                                        disabled={!resumeCaseId || isSimulating}
                                        className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 h-10 px-4 shrink-0"
                                    >
                                        Resume
                                    </Button>
                                </div>
                            </div>
                            <div className="space-y-3">
                                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Create New Event Type</Label>
                                <RadioGroup value={eventType} onValueChange={setEventType} className="gap-2 mt-2">
                                    <FieldLabel htmlFor="event-order" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                        <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                            <FieldContent>
                                                <FieldTitle className="text-sm font-medium text-zinc-200">Payment Failed</FieldTitle>
                                            </FieldContent>
                                            <RadioGroupItem value="order.failed" id="event-order" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                        </Field>
                                    </FieldLabel>
                                    
                                    <FieldLabel htmlFor="event-sub" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                        <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                            <FieldContent>
                                                <FieldTitle className="text-sm font-medium text-zinc-200">Subscription Halted</FieldTitle>
                                            </FieldContent>
                                            <RadioGroupItem value="subscription_failed" id="event-sub" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                        </Field>
                                    </FieldLabel>

                                    <FieldLabel htmlFor="event-invoice" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                        <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                            <FieldContent>
                                                <FieldTitle className="text-sm font-medium text-zinc-200">Invoice Expired</FieldTitle>
                                            </FieldContent>
                                            <RadioGroupItem value="invoice_failed" id="event-invoice" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                        </Field>
                                    </FieldLabel>
                                </RadioGroup>
                            </div>

                            <div className="space-y-3">
                                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Simulation Amount (INR)</Label>
                                <Input 
                                    type="number" 
                                    value={amount}
                                    onChange={e => setAmount(e.target.value)}
                                    className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all mb-3 h-9" 
                                />
                                <div className="space-y-2 pt-2">
                                    <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Decline Reason</Label>
                                    <Input 
                                        value={declineReason}
                                        onChange={e => setDeclineReason(e.target.value)}
                                        className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all h-9" 
                                    />
                                </div>
                            </div>

                            <div className="space-y-3">
                                <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Customer Details (Optional)</Label>
                                <div className="flex flex-col gap-3">
                                    <div className="relative flex items-center group">
                                        <User className="absolute left-3 w-4 h-4 text-zinc-500 group-focus-within:text-violet-500 transition-colors" />
                                        <Input 
                                            value={name} onChange={e => setName(e.target.value)}
                                            className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all pl-9 h-9" placeholder="Customer Name" />
                                    </div>
                                    <div className="relative flex items-center group">
                                        <PhoneCall className="absolute left-3 w-4 h-4 text-zinc-500 group-focus-within:text-violet-500 transition-colors" />
                                        <Input 
                                            value={phone} onChange={e => setPhone(e.target.value)}
                                            className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all pl-9 h-9" placeholder="WhatsApp Number" />
                                    </div>
                                    <div className="relative flex items-center group">
                                        <Mail className="absolute left-3 w-4 h-4 text-zinc-500 group-focus-within:text-violet-500 transition-colors" />
                                        <Input 
                                            value={email} onChange={e => setEmail(e.target.value)}
                                            className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all pl-9 h-9" placeholder="Email Address" type="email" />
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="p-6 pt-4 border-t border-zinc-800/60 bg-[#09090d]/90 backdrop-blur shrink-0">
                            <form className="flex w-full sm:justify-end gap-3" onSubmit={handleFireEvent}>
                                <SheetClose className="inline-flex h-10 items-center justify-center rounded-md px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors">
                                    Cancel
                                </SheetClose>
                                <Button 
                                    type="submit" 
                                    disabled={isSimulating}
                                    className="bg-violet-600 hover:bg-violet-500 text-white shadow-sm shadow-violet-900/20 transition-all"
                                >
                                    {isSimulating ? (
                                        <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Starting...</>
                                    ) : "Run Simulation"}
                                </Button>
                            </form>
                        </div>
                    </>
                ) : (
                    // ----------------------------------------------------
                    // STEP 2: CHAT & ACTIONS
                    // ----------------------------------------------------
                    <div className="flex flex-col h-full overflow-hidden bg-black/20">
                        {/* Status Bar */}
                        <div className="px-6 py-2 border-b border-zinc-800/60 flex items-center justify-between bg-zinc-900/30">
                            <span className="text-xs text-zinc-400">Case ID: <span className="font-mono text-zinc-300">{activeCaseId?.slice(0, 12)}...</span></span>
                            <span className="flex items-center gap-2">
                                {isPolling && <span className="relative flex h-2 w-2">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
                                </span>}
                                <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">{activeCase?.recovery_status || 'analyzing'}</span>
                            </span>
                        </div>

                        {/* Chat Messages */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                            {chatHistory.map((msg) => (
                                <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    {msg.isStatus ? (
                                        <div className="mx-auto my-2 px-3 py-1 rounded-full bg-zinc-800/50 border border-zinc-700/50 text-xs text-zinc-400 flex items-center gap-2">
                                            {msg.sender === 'user' ? <CheckCircle2 className="w-3 h-3 text-green-500" /> : <Bot className="w-3 h-3 text-violet-500" />}
                                            {msg.text}
                                        </div>
                                    ) : (
                                        <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                                            msg.sender === 'user' 
                                                ? 'bg-violet-600 text-white rounded-br-sm' 
                                                : 'bg-zinc-800 text-zinc-200 border border-zinc-700/50 rounded-bl-sm'
                                        }`}>
                                            <p>{msg.text}</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Action Bar */}
                        <div className="p-4 bg-zinc-950/80 border-t border-zinc-800/60 backdrop-blur-md shrink-0">
                            <div className="flex gap-2 mb-3">
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="flex-1 bg-zinc-900 border-zinc-700 hover:bg-zinc-800 text-zinc-300"
                                    onClick={() => handleAction('pay')}
                                    disabled={isSimulating}
                                >
                                    💳 Pay Now
                                </Button>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="flex-1 bg-zinc-900 border-zinc-700 hover:bg-zinc-800 text-zinc-300"
                                    onClick={() => handleAction('ignore')}
                                    disabled={isSimulating}
                                >
                                    🙈 Ignore
                                </Button>
                            </div>
                            
                            <form 
                                className="flex items-center gap-2"
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    if(replyText.trim()) handleAction('reply', replyText);
                                }}
                            >
                                <Input 
                                    value={replyText}
                                    onChange={e => setReplyText(e.target.value)}
                                    placeholder="Reply to agent..." 
                                    className="bg-zinc-900/50 border-zinc-700 focus-visible:ring-violet-500 text-zinc-200 h-10"
                                    disabled={isSimulating}
                                />
                                <Button 
                                    type="submit" 
                                    size="icon" 
                                    className="h-10 w-10 shrink-0 bg-violet-600 hover:bg-violet-500 text-white"
                                    disabled={!replyText.trim() || isSimulating}
                                >
                                    {isSimulating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                </Button>
                            </form>
                        </div>
                    </div>
                )}
            </SheetContent>
        </Sheet>
    )
}

export default SimulateSheet;