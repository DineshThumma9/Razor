import React from "react"
import { cn } from "@/lib/utils"

export interface BubbleProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "inbound" | "outbound" | "default" | "primary"
}

export function Bubble({
  variant = "default",
  className,
  children,
  ...props
}: BubbleProps) {
  const variantStyles = {
    // Inbound (Customer): Clean dark muted bubble from shadcn screenshot
    inbound: "bg-[#27272a] text-zinc-100 rounded-2xl rounded-tl-sm self-start max-w-[80%]",
    // Outbound (Agent / Primary): Clean primary blue/indigo bubble from shadcn screenshot
    outbound: "bg-[#2563eb] text-white rounded-2xl rounded-tr-sm self-end max-w-[80%]",
    default: "bg-[#27272a] text-zinc-100 rounded-2xl self-start max-w-[80%]",
    primary: "bg-[#2563eb] text-white rounded-2xl self-end max-w-[80%]",
  }

  return (
    <div
      className={cn(
        "px-4 py-2.5 text-sm inline-block shadow-sm break-words",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function BubbleContent({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("leading-relaxed", className)} {...props}>
      {children}
    </div>
  )
}
