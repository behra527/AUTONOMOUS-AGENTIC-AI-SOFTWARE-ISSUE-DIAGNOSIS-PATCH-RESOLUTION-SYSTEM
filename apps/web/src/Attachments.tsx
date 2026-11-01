import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "./api";

type Attachment = {
  id: string;
  filename: string;
  content: string;
  redacted: boolean;
};
export default function Attachments({ ticketId }: { ticketId: string }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["attachments", ticketId],
    queryFn: () => api<Attachment[]>(`/tickets/${ticketId}/attachments`),
  });
  return (
    <section className="attachments">
      <h3>Supporting text logs</h3>
      <p className="muted">
        Optional .txt or .log, up to 32,000 characters. Remove sensitive
        information before uploading. Common secrets and email addresses are
        redacted automatically.
      </p>
      <label>
        Attach a sanitized log
        <input
          type="file"
          accept=".txt,.log"
          disabled={busy || (query.data?.length || 0) >= 5}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            setError("");
            setBusy(true);
            try {
              if (file.size > 64000)
                throw new Error("The log must be at most 64 KB.");
              const content = await file.text();
              if (content.length > 32000)
                throw new Error("The log must be at most 32,000 characters.");
              await post(`/tickets/${ticketId}/attachments`, {
                filename: file.name,
                content,
              });
              await client.invalidateQueries({
                queryKey: ["attachments", ticketId],
              });
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      {busy && <small>Sanitizing and saving…</small>}
      {(error || query.error) && (
        <p className="error" role="alert">
          {error || query.error?.message}
        </p>
      )}
      {query.data?.map((a) => (
        <details key={a.id}>
          <summary>
            {a.filename}
            {a.redacted ? " · redacted" : ""}
          </summary>
          <pre>{a.content}</pre>
        </details>
      ))}
    </section>
  );
}
