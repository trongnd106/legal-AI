#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
CONTRACTS_DIR="/home/trong/Documents/graphrag/data-contracts"
SUMMARY_FILE="/tmp/contract_summary.json"

echo "=== Phân tích hàng loạt HĐLĐ ==="
echo "API: $API_URL"
echo ""

RESULTS=()
for f in "$CONTRACTS_DIR"/Mau-hop-dong-*.docx; do
    fname=$(basename "$f")
    echo ">>> Đang phân tích: $fname ..."
    resp=$(curl -s -X POST "$API_URL/api/contract/analyze" \
        -F "file=@$f" \
        -F "wage_region=IV")
    
    score=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('compliance_score','?'))" 2>/dev/null || echo "ERROR")
    n_clauses=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('num_clauses','?'))" 2>/dev/null || echo "?")
    n_viol=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('num_violations','?'))" 2>/dev/null || echo "?")
    n_high=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('num_high_risk','?'))" 2>/dev/null || echo "?")
    missing=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print('; '.join(d.get('missing_mandatory',[])) or '-')" 2>/dev/null || echo "?")
    
    echo "   → Score: $score | Clauses: $n_clauses | VIOLATIONS: $n_viol | HIGH_RISK: $n_high | Missing: $missing"
    echo ""
    
    RESULTS+=("$(echo "$resp")")
done

echo "=== TỔNG KẾT ==="
echo ""
printf "%-30s %8s %8s %8s %8s  %s\n" "FILE" "SCORE" "Đ.KHOẢN" "VI PHẠM" "RỦI RO" "THIẾU ĐK BẮT BUỘC"
printf "%-30s %8s %8s %8s %8s  %s\n" "----" "-----" "-------" "-------" "------" "------------------"

TOTAL_SCORE=0
TOTAL_VIOL=0
TOTAL_HIGH=0
COUNT=0

for r in "${RESULTS[@]}"; do
    fname=$(echo "$r" | python3 -c "import sys,json; print(json.load(sys.stdin).get('filename','?'))" 2>/dev/null)
    score=$(echo "$r" | python3 -c "import sys,json; print(json.load(sys.stdin).get('compliance_score','?'))" 2>/dev/null)
    nc=$(echo "$r" | python3 -c "import sys,json; print(json.load(sys.stdin).get('num_clauses','?'))" 2>/dev/null)
    nv=$(echo "$r" | python3 -c "import sys,json; print(json.load(sys.stdin).get('num_violations','?'))" 2>/dev/null)
    nh=$(echo "$r" | python3 -c "import sys,json; print(json.load(sys.stdin).get('num_high_risk','?'))" 2>/dev/null)
    miss=$(echo "$r" | python3 -c "import sys,json; d=json.load(sys.stdin); mm=d.get('missing_mandatory',[]); print('; '.join(mm) if mm else '—')" 2>/dev/null)
    
    printf "%-30s %8s %8s %8s %8s  %s\n" "$fname" "$score" "$nc" "$nv" "$nh" "$miss"
    
    TOTAL_SCORE=$(echo "$TOTAL_SCORE + $score" | bc 2>/dev/null || echo 0)
    TOTAL_VIOL=$((TOTAL_VIOL + nv))
    TOTAL_HIGH=$((TOTAL_HIGH + nh))
    COUNT=$((COUNT + 1))
done

if [ "$COUNT" -gt 0 ]; then
    AVG_SCORE=$(echo "scale=1; $TOTAL_SCORE / $COUNT" | bc 2>/dev/null || echo "?")
    echo ""
    echo "=== TRUNG BÌNH ==="
    echo "  Compliance score trung bình: $AVG_SCORE"
    echo "  Tổng vi phạm: $TOTAL_VIOL"
    echo "  Tổng rủi ro cao: $TOTAL_HIGH"
    echo "  Số hợp đồng: $COUNT"
fi

echo ""
echo "=== Kết thúc ==="
