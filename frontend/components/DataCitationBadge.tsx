"use client";

import type { DataCitationItem } from "@/types/api";

interface DataCitationGroupProps {
  items: DataCitationItem[];
}

function CitationBadge({ item }: { item: DataCitationItem }) {
  return (
    <span className="citation-badge" tabIndex={0}>
      <span className="citation-badge-pill">
        <span className="citation-badge-icon" aria-hidden>
          {item.icon}
        </span>
        <span className="citation-badge-label">{item.label}</span>
      </span>
      <span className="citation-tooltip" role="tooltip">
        <span className="citation-tooltip-type">{item.type_label || item.type}</span>
        <span className="citation-tooltip-detail">{item.detail}</span>
      </span>
    </span>
  );
}

export function DataCitationGroup({ items }: DataCitationGroupProps) {
  if (items.length === 0) return null;

  return (
    <span className="citation-group" aria-label="Tham chiếu dữ liệu">
      {items.map((item) => (
        <CitationBadge key={item.key} item={item} />
      ))}
    </span>
  );
}
