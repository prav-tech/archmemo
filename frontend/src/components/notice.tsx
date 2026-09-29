import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "error" | "success";

const tones: Record<Tone, { box: string; icon: React.ElementType }> = {
  info: { box: "border-primary/25 bg-accent text-accent-foreground", icon: Info },
  warning: { box: "border-warning/30 bg-warning-soft text-warning", icon: AlertTriangle },
  error: { box: "border-destructive/30 bg-destructive/5 text-destructive", icon: XCircle },
  success: { box: "border-success/30 bg-success-soft text-success", icon: CheckCircle2 },
};

interface NoticeProps {
  tone?: Tone;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}

/** Inline message for errors, warnings and empty-state guidance. */
export function Notice({ tone = "info", title, children, className }: NoticeProps) {
  const { box, icon: Icon } = tones[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-md border px-4 py-3 text-sm", box, className)}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="leading-relaxed">{children}</div>}
      </div>
    </div>
  );
}
