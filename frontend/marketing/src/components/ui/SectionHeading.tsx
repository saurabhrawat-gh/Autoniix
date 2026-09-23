import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import Reveal from "./Reveal";

export default function SectionHeading({
  eyebrow,
  title,
  lead,
  align = "center",
  className,
}: {
  eyebrow: string;
  title: ReactNode;
  lead?: ReactNode;
  align?: "center" | "left";
  className?: string;
}) {
  return (
    <Reveal className={cn("max-w-3xl", align === "center" ? "mx-auto text-center" : "", className)}>
      <p className="eyebrow mb-4">{eyebrow}</p>
      <h2 className="t-h1 text-content-primary">{title}</h2>
      {lead && <p className="t-lead mt-5">{lead}</p>}
    </Reveal>
  );
}
