"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  buildCitationMap,
  resolveCitationRefs,
  splitContentWithCitations,
} from "@/lib/citations";
import type { DataCitationItem } from "@/types/api";
import { DataCitationGroup } from "./DataCitationBadge";

interface MarkdownMessageProps {
  content: string;
  dataCitations?: DataCitationItem[];
}

export function MarkdownMessage({ content, dataCitations = [] }: MarkdownMessageProps) {
  const citationMap = buildCitationMap(dataCitations);
  const parts = splitContentWithCitations(content);

  if (parts.length === 1 && parts[0].kind === "text") {
    return (
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="markdown-body markdown-with-citations">
      {parts.map((part, idx) => {
        if (part.kind === "text") {
          if (!part.value.trim()) return null;
          return (
            <ReactMarkdown key={`text-${idx}`} remarkPlugins={[remarkGfm]}>
              {part.value}
            </ReactMarkdown>
          );
        }

        const refs = resolveCitationRefs(part.raw, citationMap);
        return <DataCitationGroup key={`cite-${idx}`} items={refs} />;
      })}
    </div>
  );
}
