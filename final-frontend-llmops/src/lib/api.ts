import type { AppId, InvokeRequest, InvokeResponse, HealthResponse } from "@/types/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/`, { cache: "no-store" });
  return handleResponse<HealthResponse>(res);
}

export async function invoke(
  appId: AppId,
  userInput: string,
  model?: string
): Promise<InvokeResponse> {
  const body: InvokeRequest = { app_id: appId, user_input: userInput };
  if (model) body.model = model;
  
  const res = await fetch(`${BASE_URL}/invoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<InvokeResponse>(res);
}

export async function submitFeedback(
  requestId: string,
  score: number,
  comment?: string
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE_URL}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId, score, comment }),
  });
  return handleResponse(res);
}

// NOT_IMPLEMENTED: /ready does not exist on backend
// NOT_IMPLEMENTED: /manifest does not exist on backend