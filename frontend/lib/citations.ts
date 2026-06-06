import type { DataCitationItem } from "@/types/api";

export const DATA_CITATION_RE = /\[Data:\s*[^\]]+\]/g;
const GROUP_RE = /(\w+)\s*\(([^)]+)\)/g;

export type ContentPart =
  | { kind: "text"; value: string }
  | { kind: "citation"; raw: string };

export function buildCitationMap(
  items: DataCitationItem[],
): Map<string, DataCitationItem> {
  return new Map(items.map((item) => [item.key, item]));
}

export function parseCitationGroups(
  raw: string,
): Array<{ type: string; ids: string[] }> {
  const inner = raw.replace(/^\[Data:\s*/, "").replace(/\]$/, "").trim();
  const groups: Array<{ type: string; ids: string[] }> = [];

  for (const match of inner.matchAll(GROUP_RE)) {
    const type = match[1].trim();
    const ids = match[2]
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && s.toLowerCase() !== "+more");
    if (ids.length > 0) groups.push({ type, ids });
  }

  return groups;
}

export function splitContentWithCitations(content: string): ContentPart[] {
  const parts: ContentPart[] = [];
  let lastIndex = 0;

  for (const match of content.matchAll(DATA_CITATION_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      parts.push({ kind: "text", value: content.slice(lastIndex, index) });
    }
    parts.push({ kind: "citation", raw: match[0] });
    lastIndex = index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push({ kind: "text", value: content.slice(lastIndex) });
  }

  return parts.length > 0 ? parts : [{ kind: "text", value: content }];
}

export function resolveCitationRefs(
  raw: string,
  map: Map<string, DataCitationItem>,
): DataCitationItem[] {
  const refs: DataCitationItem[] = [];
  const seen = new Set<string>();

  for (const group of parseCitationGroups(raw)) {
    for (const id of group.ids) {
      const key = `${group.type}:${id}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const found = map.get(key);
      if (found) {
        refs.push(found);
      } else {
        refs.push({
          key,
          type: group.type,
          id,
          label: `${group.type} #${id}`,
          detail: `Không có chi tiết cho ${group.type} #${id}.`,
          icon: "📎",
          type_label: group.type,
        });
      }
    }
  }

  return refs;
}
