export let accessToken = "";
export function setAccessToken(value: string) {
  accessToken = value;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "Request failed");
  return body;
}
export function post<T>(
  path: string,
  body: unknown,
  key: string = crypto.randomUUID(),
) {
  return api<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Idempotency-Key": key },
  });
}
export type Ticket = {
  id: string;
  title: string;
  description: string;
  expected_behavior: string;
  actual_behavior: string;
  reproduction_steps: string[];
  status: string;
  created_at: string;
};
export type Snapshot = {
  id: string;
  commit_sha: string;
  status: string;
  stats: {
    files?: number;
    chunks?: number;
    retrieval?: string;
    syntax_errors?: string[];
  };
};
export type Repo = {
  id: string;
  name: string;
  remote_url: string;
  snapshots: Snapshot[];
};
export type Evidence = {
  id: string;
  path: string;
  symbol: string;
  kind: string;
  start_line: number;
  end_line: number;
  content: string;
  content_hash: string;
  commit_sha: string;
  hash_valid: boolean;
  metadata: { imports?: string[]; call_candidates?: string[] };
};
export type Run = {
  id: string;
  status: string;
  created_at: string;
  diagnosis?: {
    summary: string;
    mode: string;
    prompt_version: string;
    hypotheses: {
      title: string;
      explanation: string;
      evidence_ids: string[];
    }[];
    missing_information: string[];
    limitations: string[];
  };
};
