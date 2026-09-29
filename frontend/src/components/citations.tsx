"use client";

import * as React from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Matches a decision ID, plus the marker the backend appends after an ID the model
 * cited that was NOT in recalled memory ("DEC-2024-001 ⚠ UNVERIFIED – not in recalled memory").
 */
const CITATION_RE = /(DEC-\d{4}-\d{3})(\s*⚠ UNVERIFIED\s*[–-]\s*not in recalled memory)?/g;

export interface CitationContext {
  /** IDs the model cited that were present in recalled memory */
  verified: ReadonlySet<string>;
  /** IDs the model cited that were NOT in recalled memory */
  unverified: ReadonlySet<string>;
  titles: Readonly<Record<string, string | null | undefined>>;
}

const chipBase =
  "inline-flex items-center gap-1 rounded border px-1.5 py-px align-baseline font-mono text-[0.85em] font-medium leading-snug no-underline";

/** A decision ID. Verified IDs link to the decision; unverified IDs are flagged and do not link. */
export function CitationChip({
  id,
  title,
  unverified = false,
}: {
  id: string;
  title?: string | null;
  unverified?: boolean;
}) {
  if (unverified) {
    return (
      <span
        className={cn(chipBase, "border-warning/40 bg-warning-soft text-warning")}
        title="The model cited this ID, but it was not in recalled memory. Treat it as unsupported."
      >
        <AlertTriangle className="h-3 w-3" aria-hidden />
        {id}
        <span className="font-sans text-[0.9em] font-normal">not in memory</span>
      </span>
    );
  }
  return (
    <Link
      href={`/decisions/${id}`}
      title={title ?? undefined}
      className={cn(chipBase, "border-primary/25 bg-primary/10 text-primary hover:bg-primary/20")}
    >
      {id}
    </Link>
  );
}

/** Replace every decision ID inside a plain string with a chip. */
export function CitedText({ text, ctx }: { text: string; ctx?: CitationContext }) {
  const matches = Array.from(text.matchAll(CITATION_RE));
  if (matches.length === 0) return <>{text}</>;

  const nodes: React.ReactNode[] = [];
  let last = 0;
  matches.forEach((m, i) => {
    const start = m.index ?? 0;
    if (start > last) nodes.push(text.slice(last, start));
    const id = m[1];
    const flagged = Boolean(m[2]) || Boolean(ctx?.unverified.has(id));
    nodes.push(<CitationChip key={i} id={id} title={ctx?.titles[id]} unverified={flagged} />);
    last = start + m[0].length;
  });
  if (last < text.length) nodes.push(text.slice(last));
  return <>{nodes}</>;
}

function withCitations(children: React.ReactNode, ctx?: CitationContext): React.ReactNode {
  return React.Children.map(children, (child) =>
    typeof child === "string" ? <CitedText text={child} ctx={ctx} /> : child
  );
}

/** Renders briefing markdown with every decision ID turned into a chip. */
export function BriefingMarkdown({ markdown, ctx }: { markdown: string; ctx?: CitationContext }) {
  const components = React.useMemo<Components>(
    () => ({
      p: ({ children }) => <p>{withCitations(children, ctx)}</p>,
      li: ({ children }) => <li>{withCitations(children, ctx)}</li>,
      strong: ({ children }) => <strong>{withCitations(children, ctx)}</strong>,
      em: ({ children }) => <em>{withCitations(children, ctx)}</em>,
      h1: ({ children }) => <h1>{withCitations(children, ctx)}</h1>,
      h2: ({ children }) => <h2>{withCitations(children, ctx)}</h2>,
      h3: ({ children }) => <h3>{withCitations(children, ctx)}</h3>,
      h4: ({ children }) => <h4>{withCitations(children, ctx)}</h4>,
      th: ({ children }) => <th>{withCitations(children, ctx)}</th>,
      td: ({ children }) => <td>{withCitations(children, ctx)}</td>,
      // The model sometimes wraps IDs in backticks; still render those as chips.
      code: ({ children, className }) => {
        const text = typeof children === "string" ? children : null;
        if (!className && text && /^DEC-\d{4}-\d{3}$/.test(text.trim())) {
          return <CitedText text={text.trim()} ctx={ctx} />;
        }
        return <code className={className}>{children}</code>;
      },
    }),
    [ctx]
  );

  return (
    <div className="briefing-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
