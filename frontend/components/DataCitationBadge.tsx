"use client";

import type { DataCitationItem } from "@/types/api";

interface DataCitationGroupProps {
  items: DataCitationItem[];
  numberMap: Map<string, number>;
}

function CitationBadge({ item, number }: { item: DataCitationItem; number: number }) {
  return (
    <span className="citation-badge" tabIndex={0}>
      <span className="citation-badge-pill">
        <span className="citation-badge-label">[{number}]</span>
      </span>
      <span className="citation-tooltip" role="tooltip">
        <span className="citation-tooltip-type">{item.type_label || item.type}</span>
        <span className="citation-tooltip-detail">{item.detail}</span>
      </span>
    </span>
  );
}

export function DataCitationGroup({ items, numberMap }: DataCitationGroupProps) {
  if (items.length === 0) return null;

  return (
    <span className="citation-group" aria-label="Tham chiếu dữ liệu">
      {items.map((item) => (
        <CitationBadge
          key={item.key}
          item={item}
          number={numberMap.get(item.key) ?? 0}
        />
      ))}
    </span>
  );
}
