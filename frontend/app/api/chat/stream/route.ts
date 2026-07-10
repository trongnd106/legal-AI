import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function POST(req: NextRequest): Promise<Response> {
  const body = await req.text();

  const upstream = await fetch(`${BACKEND_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body,
  });

  if (!upstream.ok) {
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
