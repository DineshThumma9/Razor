import React from "react"
import { cn } from "@/lib/utils"

export function Message({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col gap-1 w-full", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function MessageHeader({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("text-xs text-zinc-400 font-medium px-1", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function MessageContent({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("text-sm leading-relaxed", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function MessageFooter({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("text-[11px] text-zinc-500 px-1 font-mono", className)}
      {...props}
    >
      {children}
    </div>
  )
}
