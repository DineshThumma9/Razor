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
import { PhoneCall, Mail } from "lucide-react"
import { useState } from "react"

const SimulateSheet = () => {
    const [isSimulating, setIsSimulating] = useState(false);
    const [success, setSuccess] = useState(false);

    return (
        <Sheet>
            <SheetTrigger render={<Button className='bg-red-700/90 text-white hover:bg-red-600 rounded-full px-4 text-sm font-medium transition-colors shadow-sm shadow-red-900/20'>Simulate Events</Button>} />
            <SheetContent className="bg-[#09090d] border-l border-zinc-800 text-zinc-100 flex flex-col gap-0 p-0 overflow-hidden w-full sm:max-w-md">
                <div className="p-6 pb-4 border-b border-zinc-800/60 shrink-0">
                    <SheetHeader>
                        <SheetTitle className="text-zinc-100 text-lg font-semibold tracking-tight">Simulate Event</SheetTitle>
                        <SheetDescription className="text-zinc-400 text-sm mt-1">
                            Trigger a simulated failure event to test the recovery flow and agent behaviors.
                        </SheetDescription>
                    </SheetHeader>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                    <div className="space-y-3">
                        <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Follow Up</Label>
                        <Input className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all h-9" placeholder="Enter Case ID (Optional)" />
                    </div>

                    <div className="space-y-3">
                        <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Event Type</Label>
                        <RadioGroup defaultValue="payment-failed" className="gap-2">
                            <FieldLabel htmlFor="event-payment" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                    <FieldContent>
                                        <FieldTitle className="text-sm font-medium text-zinc-200">Payment Failed</FieldTitle>
                                    </FieldContent>
                                    <RadioGroupItem value="payment-failed" id="event-payment" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                </Field>
                            </FieldLabel>

                            <FieldLabel htmlFor="event-order" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                    <FieldContent>
                                        <FieldTitle className="text-sm font-medium text-zinc-200">Order Failed</FieldTitle>
                                    </FieldContent>
                                    <RadioGroupItem value="order-failed" id="event-order" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                </Field>
                            </FieldLabel>

                            <FieldLabel htmlFor="event-invoice" className="border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-800/50 hover:border-zinc-700/80 rounded-lg cursor-pointer transition-all has-[[data-checked]]:border-violet-500/50 has-[[data-checked]]:bg-violet-500/10">
                                <Field orientation="horizontal" className="p-3 w-full justify-between items-center flex">
                                    <FieldContent>
                                        <FieldTitle className="text-sm font-medium text-zinc-200">Invoice Failed</FieldTitle>
                                    </FieldContent>
                                    <RadioGroupItem value="invoice-failed" id="event-invoice" className="border-zinc-600 text-violet-500 h-4 w-4" />
                                </Field>
                            </FieldLabel>
                        </RadioGroup>
                    </div>

                    <div className="space-y-3">
                        <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Simulation Amount</Label>
                        <Input type="number" className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all mb-3 h-9" placeholder="Enter specific amount (e.g. 500)" />
                        
                        <RadioGroup className="grid grid-cols-3 gap-2" defaultValue="1k-5k">
                            <div>
                                <RadioGroupItem value="1k-5k" id="amt-low" className="peer sr-only" />
                                <Label htmlFor="amt-low" className="flex items-center justify-center px-3 py-2.5 border border-zinc-800/80 rounded-md bg-zinc-900/30 text-zinc-400 cursor-pointer hover:bg-zinc-800/50 hover:text-zinc-300 peer-data-[checked]:border-violet-500/50 peer-data-[checked]:text-violet-300 peer-data-[checked]:bg-violet-500/10 transition-all text-xs font-medium">1k - 5k</Label>
                            </div>
                            <div>
                                <RadioGroupItem value="5k-10k" id="amt-med" className="peer sr-only" />
                                <Label htmlFor="amt-med" className="flex items-center justify-center px-3 py-2.5 border border-zinc-800/80 rounded-md bg-zinc-900/30 text-zinc-400 cursor-pointer hover:bg-zinc-800/50 hover:text-zinc-300 peer-data-[checked]:border-violet-500/50 peer-data-[checked]:text-violet-300 peer-data-[checked]:bg-violet-500/10 transition-all text-xs font-medium">5k - 10k</Label>
                            </div>
                            <div>
                                <RadioGroupItem value="10k-20k" id="amt-high" className="peer sr-only" />
                                <Label htmlFor="amt-high" className="flex items-center justify-center px-3 py-2.5 border border-zinc-800/80 rounded-md bg-zinc-900/30 text-zinc-400 cursor-pointer hover:bg-zinc-800/50 hover:text-zinc-300 peer-data-[checked]:border-violet-500/50 peer-data-[checked]:text-violet-300 peer-data-[checked]:bg-violet-500/10 transition-all text-xs font-medium">10k - 20k</Label>
                            </div>
                        </RadioGroup>
                    </div>

                    <div className="space-y-3">
                        <Label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Contact Details</Label>
                        <div className="flex flex-col gap-3">
                            <div className="relative flex items-center group">
                                <PhoneCall className="absolute left-3 w-4 h-4 text-zinc-500 group-focus-within:text-violet-500 transition-colors" />
                                <Input className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all pl-9 h-9" placeholder="WhatsApp Number" />
                            </div>
                            <div className="relative flex items-center group">
                                <Mail className="absolute left-3 w-4 h-4 text-zinc-500 group-focus-within:text-violet-500 transition-colors" />
                                <Input className="bg-zinc-900/50 border-zinc-800/80 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-violet-500/50 focus-visible:border-violet-500/50 transition-all pl-9 h-9" placeholder="Email Address" type="email" />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-6 pt-4 border-t border-zinc-800/60 bg-[#09090d]/90 backdrop-blur shrink-0">
                    <form 
                        className="flex w-full sm:justify-end gap-3"
                        onSubmit={(e) => {
                            e.preventDefault();
                            setIsSimulating(true);
                            // Fake a delay for UI
                            setTimeout(() => {
                                setIsSimulating(false);
                                setSuccess(true);
                                setTimeout(() => setSuccess(false), 2000);
                            }, 1000);
                        }}
                    >
                        <SheetClose render={<Button type="button" variant="ghost" className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800">Cancel</Button>} />
                        <Button 
                            type="submit" 
                            disabled={isSimulating || success}
                            className={`text-white shadow-sm transition-all ${
                                success ? "bg-green-600 hover:bg-green-500 shadow-green-900/20" : 
                                "bg-violet-600 hover:bg-violet-500 shadow-violet-900/20"
                            }`}
                        >
                            {isSimulating ? "Simulating..." : success ? "Simulation Triggered!" : "Run Simulation"}
                        </Button>
                    </form>
                </div>
            </SheetContent>
        </Sheet>
    )
}

export default SimulateSheet;