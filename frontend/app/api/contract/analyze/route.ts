import { type NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

// Timeout 10 phút — phân tích hợp đồng phức tạp mất vài phút
const ANALYZE_TIMEOUT_MS = 10 * 60 * 1000;

export async function POST(req: NextRequest): Promise<NextResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);

  try {
    const formData = await req.formData();

    const upstream = await fetch(`${BACKEND_URL}/api/contract/analyze`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return NextResponse.json(
        { detail: "Phân tích hợp đồng quá thời gian chờ (10 phút). Vui lòng thử lại." },
        { status: 504 },
      );
    }
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: `Lỗi proxy: ${msg}` }, { status: 502 });
  } finally {
    clearTimeout(timer);
  }
}
