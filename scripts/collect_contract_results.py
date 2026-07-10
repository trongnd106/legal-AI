"""Collect results from all 10 contracts via API and print summary."""
import json
import re
import subprocess
import sys
from pathlib import Path

CONTRACTS_DIR = Path("/home/trong/Documents/graphrag/data-contracts")
API_URL = "http://localhost:8000"

# Map description patterns to VR rule codes
VR_PATTERNS = [
    (r'thử việc.*(90|180|ngày).*vượt', 'VR002'),
    (r'thời gian thử việc.*(90|180|ngày).*vượt', 'VR002'),
    (r'Thời gian thử việc.*vượt', 'VR002'),
    (r'giờ.*tuần.*vượt.*48', 'VR003'),
    (r'Thời giờ làm việc \(.*giờ/tuần\) vượt', 'VR003'),
    (r'giờ.*ngày.*vượt.*8', 'VR003B'),
    (r'Thời giờ làm việc \(.*giờ/ngày\) vượt', 'VR003B'),
    (r'nghỉ phép năm.*thấp hơn', 'VR008'),
    (r'phép năm.*thấp hơn', 'VR008'),
    (r'Ngày nghỉ phép năm.*thấp hơn', 'VR008'),
    (r'Không tìm thấy.*bảo hiểm xã hội', 'VR009'),
    (r'Không tìm thấy.*BHYT', 'VR009B'),
    (r'thiếu.*BHXH', 'VR009'),
    (r'thiếu.*BHYT', 'VR009B'),
    (r'không đề cập.*bảo hiểm', 'VR009'),
    (r'không đề cập.*trợ cấp thôi việc', 'VR011'),
    (r'không đề cập.*trợ cấp mất việc', 'VR011'),
    (r'Trợ cấp thôi việc.*không', 'VR011'),
    (r'địa điểm làm việc.*Không tìm thấy', 'VR015'),
    (r'Không tìm thấy.*địa điểm làm việc', 'VR015'),
    (r'bất lợi một chiều', 'VR012'),
    (r'từ bỏ quyền', 'VR013'),
    (r'cạnh tranh.*tháng', 'VR014'),
    (r'lương.*tháng/lần', 'VR016'),
    (r'chu kỳ trả lương', 'VR016'),
    (r'phạt tiền', 'VR005'),
    (r'ký lần thứ [3-9]', 'VR007'),
    (r'lương thử việc.*85', 'VR004'),
    (r'báo trước.*45', 'VR010'),
    (r'báo trước.*30', 'VR010'),
]

def extract_vrs(md: str) -> set[str]:
    vrs = set()
    for pattern, vr in VR_PATTERNS:
        if re.search(pattern, md, re.IGNORECASE):
            vrs.add(vr)
    return vrs

results = []
for i in range(1, 11):
    fname = f"Mau-hop-dong-{i:02d}.docx"
    fpath = CONTRACTS_DIR / fname
    if not fpath.exists():
        print(f"SKIP: {fname} not found", file=sys.stderr)
        continue

    print(f"Processing {fname}...", file=sys.stderr)
    try:
        resp = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{API_URL}/api/contract/analyze",
             "-F", f"file=@{fpath}", "-F", "wage_region=IV", "-F", "skip_llm_review=true"],
            capture_output=True, text=True, timeout=120
        )
        data = json.loads(resp.stdout)
        md = data.get("markdown_report", "")
        vrs = extract_vrs(md)
        results.append({
            "file": fname,
            "score": data.get("compliance_score", 0),
            "clauses": data.get("num_clauses", 0),
            "violations": data.get("num_violations", 0),
            "high_risk": data.get("num_high_risk", 0),
            "missing": data.get("missing_mandatory", []),
            "vrs": sorted(vrs),
        })
        print(f"  OK: score={data.get('compliance_score')}, VRs={sorted(vrs)}", file=sys.stderr)
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)

# Print summary table
print()
print("=" * 120)
print(f"{'FILE':<25} {'SCORE':>6} {'CLS':>4} {'VIOL':>5} {'HIGH':>5} {'MISSING':<30} {'VR RULES'}")
print("-" * 120)
for r in results:
    miss = "; ".join(r["missing"]) if r["missing"] else "—"
    vrs = ", ".join(r["vrs"]) if r["vrs"] else "—"
    print(f"{r['file']:<25} {r['score']:>6.1f} {r['clauses']:>4} {r['violations']:>5} {r['high_risk']:>5} {miss:<30} {vrs}")
print("-" * 120)

if results:
    avg_score = sum(r["score"] for r in results) / len(results)
    total_viol = sum(r["violations"] for r in results)
    total_high = sum(r["high_risk"] for r in results)
    print(f"{'TRUNG BÌNH / TỔNG':<25} {avg_score:>6.1f} {'':>4} {total_viol:>5} {total_high:>5}")
    print()

    # All VR codes found
    all_vrs = set()
    for r in results:
        all_vrs.update(r["vrs"])
    print(f"Các VR codes phát hiện: {sorted(all_vrs)}")

    # Per-VR statistics
    print("\nThống kê theo VR rule:")
    print(f"{'Rule':<8} {'Số HĐ vi phạm':<16}")
    print("-" * 24)
    for vr in sorted(all_vrs):
        count = sum(1 for r in results if vr in r["vrs"])
        print(f"{vr:<8} {count:<16}")
