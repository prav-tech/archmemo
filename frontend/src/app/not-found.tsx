import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl space-y-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-sm leading-relaxed text-muted-foreground">
        There is nothing at this address. If you followed a decision ID, check that it is spelled like DEC-2024-001.
      </p>
      <div className="flex gap-2">
        <Button asChild>
          <Link href="/decisions">Browse decisions</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/">Go to briefing</Link>
        </Button>
      </div>
    </div>
  );
}
