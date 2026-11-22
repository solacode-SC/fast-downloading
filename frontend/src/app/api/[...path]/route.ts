import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_BASES = [
  process.env.API_INTERNAL_URL || "http://api:8000",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
];

async function fetchBackend(targetPath: string, init: RequestInit): Promise<Response> {
  let lastError: unknown = null;
  for (const base of API_BASES) {
    const url = `${base.replace(/\/$/, "")}${targetPath}`;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        return await fetch(url, init);
      } catch (err) {
        lastError = err;
        // Wait 350ms if backend uvicorn is mid-reload in dev
        if (attempt === 0) {
          await new Promise((r) => setTimeout(r, 350));
        }
      }
    }
  }
  throw lastError ?? new Error("Backend API unreachable");
}

async function handleProxy(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const { path } = await context.params;
  const subPath = path.map((seg) => encodeURIComponent(seg)).join("/");
  const search = req.nextUrl.search || "";
  const targetPath = `/api/${subPath}${search}`;

  const forwardHeaders = new Headers();
  for (const key of [
    "content-type",
    "accept",
    "range",
    "if-range",
    "x-request-id",
    "x-forwarded-for",
    "user-agent",
  ]) {
    const val = req.headers.get(key);
    if (val) forwardHeaders.set(key, val);
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const bodyBuffer = hasBody ? await req.arrayBuffer() : undefined;

  try {
    const upstream = await fetchBackend(targetPath, {
      method: req.method,
      headers: forwardHeaders,
      body: bodyBuffer,
      cache: "no-store",
    });

    const respHeaders = new Headers();
    for (const [k, v] of upstream.headers.entries()) {
      const low = k.toLowerCase();
      if (low === "transfer-encoding" || low === "content-encoding" || low === "connection") {
        continue;
      }
      respHeaders.set(k, v);
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: respHeaders,
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "NETWORK",
          message: "Backend API is temporarily reloading or unreachable.",
          hint: "Wait a second and try again.",
          retryable: true,
        },
      },
      { status: 503 }
    );
  }
}

export const GET = handleProxy;
export const POST = handleProxy;
export const DELETE = handleProxy;
export const OPTIONS = handleProxy;
