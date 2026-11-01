import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  Code2,
  FileSearch,
  FolderGit2,
  LayoutDashboard,
  LogOut,
  Plus,
  Search,
  ShieldCheck,
  Terminal,
  Ticket as TicketIcon,
  X,
} from "lucide-react";
import {
  api,
  post,
  setAccessToken,
  type Ticket,
  type Repo,
  type Run,
  type Evidence,
} from "./api";

import Attachments from "./Attachments";
import OidcLogin, { type OidcConfig } from "./OidcLogin";
type Page = "Overview" | "Issues" | "Repositories" | "Activity";
type Health = {
  auth_mode: string;
  model_mode: string;
  semantic_enabled: boolean;
  oidc?: OidcConfig;
};
const icons = {
  Overview: LayoutDashboard,
  Issues: TicketIcon,
  Repositories: FolderGit2,
  Activity,
};
const pretty = (s: string) => s.replaceAll("_", " ").toLowerCase();
function Badge({ value }: { value: string }) {
  return (
    <span className={"badge " + value.toLowerCase()}>
      <span />
      {pretty(value)}
    </span>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <FileSearch size={28} />
      <p>{text}</p>
    </div>
  );
}

export default function App() {
  const client = useQueryClient();
  const [signedIn, signIn] = useState(false);
  const [page, setPage] = useState<Page>("Overview");
  const [project, setProject] = useState("");
  const [selected, select] = useState<Ticket | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const [cursor, setCursor] = useState("");
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () =>
      api<{
        subject: string;
        memberships: { project_id: string; role: string }[];
      }>("/auth/me"),
    enabled: signedIn,
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<{ id: string; name: string }[]>("/projects"),
    enabled: signedIn,
  });
  const projectId = project || projects.data?.[0]?.id || "";
  const role =
    me.data?.memberships.find((m) => m.project_id === projectId)?.role ||
    "customer";
  const internal = role !== "customer";
  const tickets = useQuery({
    queryKey: ["tickets", projectId, cursor],
    queryFn: () =>
      api<{ items: Ticket[]; next_cursor: string | null }>(
        `/projects/${projectId}/tickets${cursor ? "?before=" + cursor : ""}`,
      ),
    enabled: signedIn && !!projectId,
    refetchInterval: 2500,
  });
  const repos = useQuery({
    queryKey: ["repos", projectId],
    queryFn: () => api<Repo[]>(`/projects/${projectId}/repositories`),
    enabled: signedIn && !!projectId && internal,
    refetchInterval: 3000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () =>
      api<
        {
          id: string;
          kind: string;
          status: string;
          attempts: number;
          error: string | null;
        }[]
      >(`/projects/${projectId}/jobs`),
    enabled: signedIn && !!projectId && internal,
    refetchInterval: 2500,
  });
  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
      await client.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function login(token: string) {
    setAccessToken(token);
    await action(async () => {
      await api("/auth/me");
      signIn(true);
    });
  }
  function logout() {
    setAccessToken("");
    signIn(false);
    select(null);
    setProject("");
    setPage("Overview");
    client.clear();
  }
  const queryError =
    me.error ||
    projects.error ||
    tickets.error ||
    (internal && (repos.error || jobs.error));
  const list = (tickets.data?.items || []).filter((t) =>
    (t.title + " " + t.status).toLowerCase().includes(filter.toLowerCase()),
  );
  if (!signedIn)
    return (
      <div className="login">
        <div className="login-story">
          <div className="wordmark">
            <span className="logo">
              <Activity />
            </span>
            BugHound-Ai
          </div>
          <div>
            <div className="eyebrow">FROM REPORT TO ROOT CAUSE</div>
            <h1>
              Every issue leaves
              <br />a trace.
            </h1>
            <p>
              Connect the report to the repository.
              <br />
              Investigate with evidence you can inspect.
            </p>
            <div className="trace-line">
              <span>01 / REPORT</span>
              <ArrowRight />
              <span>02 / INVESTIGATE</span>
              <ArrowRight />
              <span>03 / REVIEW</span>
            </div>
          </div>
          <small>Autonomous Agentic AI · Python investigation workspace</small>
        </div>
        <div className="login-panel">
          <span className="eyebrow">YOUR ENGINEERING WORKSPACE</span>
          <h2>Welcome to BugHound-Ai</h2>
          <p>Follow an issue from customer report to source evidence.</p>
          {health.isPending ? (
            <p>Connecting to API…</p>
          ) : health.isError ? (
            <p role="alert">API unavailable. Start the backend and retry.</p>
          ) : health.data?.auth_mode === "demo" ? (
            <>
              <div className="notice">
                Local demonstration · identities below are development-only.
              </div>
              <button onClick={() => login("demo-customer")} disabled={busy}>
                Enter as customer <ArrowRight size={17} />
              </button>
              <button
                className="secondary"
                onClick={() => login("demo-engineer")}
                disabled={busy}
              >
                Enter as engineer <Code2 size={17} />
              </button>
              <button
                className="text-button"
                onClick={() => login("demo-admin")}
                disabled={busy}
              >
                Administrator workspace
              </button>
            </>
          ) : (
            <OidcLogin config={health.data?.oidc} onToken={login} />
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div className="login-footer">
            <ShieldCheck size={16} /> Evidence stays in the internal workspace.
          </div>
        </div>
      </div>
    );
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="wordmark">
          <span className="logo">
            <Activity size={21} />
          </span>
          BugHound-Ai
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <label className="project-label">
          <span className="sr-only">Project</span>
          <select
            value={projectId}
            onChange={(e) => {
              setProject(e.target.value);
              select(null);
              setCursor("");
            }}
          >
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <nav>
          {(
            [
              "Overview",
              "Issues",
              ...(internal ? ["Repositories", "Activity"] : []),
            ] as Page[]
          ).map((p) => {
            const Icon = icons[p];
            return (
              <button
                key={p}
                className={p === page ? "nav active" : "nav"}
                onClick={() => {
                  setPage(p);
                  select(null);
                }}
              >
                <Icon size={18} />
                {p}
                {p === "Issues" && (
                  <span className="count">
                    {tickets.data?.items.length || 0}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="phase-card">
          <div>
            <span className="live-dot" /> INVESTIGATOR WORKSPACE
          </div>
          <p>
            Traceable source evidence.
            <br />
            Human judgment at every step.
          </p>
          <span className="phase-track">
            <i />
          </span>
          <small>Phase 1 + 2 · development build</small>
        </div>
        <div className="profile">
          <span className="avatar">{role.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{me.data?.subject}</strong>
            <small>{role}</small>
          </div>
          <button className="icon-button" title="Sign out" onClick={logout}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div>
            Workspace <ChevronRight size={14} />
            <strong>{selected ? "Issue details" : page}</strong>
          </div>
          <div>
            <span className="live-dot" />
            {health.data?.model_mode === "demo"
              ? "Retrieval demo"
              : "Live model"}
            <span className="topbar-divider" />
            <span>{internal ? "Internal workspace" : "Customer portal"}</span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {internal ? "ENGINEERING OPERATIONS" : "CUSTOMER SUPPORT"}
              </div>
              <h1>
                {selected
                  ? "Issue investigation"
                  : page === "Overview"
                    ? "A clearer path to resolution."
                    : page === "Issues"
                      ? "Issue workspace"
                      : page === "Repositories"
                        ? "Connected repositories"
                        : "Workspace activity"}
              </h1>
              <p>
                {selected
                  ? "Follow the report, inspect the evidence, understand the next step."
                  : "Every report connected. Every hypothesis grounded. Every decision yours."}
              </p>
            </div>
            <button onClick={() => setCreating(true)}>
              <Plus size={17} />
              New issue
            </button>
          </div>
          {(error || queryError) && (
            <div className="error" role="alert">
              {error || (queryError as Error).message}
              <button
                className="icon-button"
                onClick={() => {
                  setError("");
                  client.invalidateQueries();
                }}
              >
                Retry
              </button>
            </div>
          )}
          {!projectId && !projects.isPending && (
            <Empty text="No project membership found. Ask your administrator to provision access." />
          )}
          {selected ? (
            <IssueDetails
              ticket={
                tickets.data?.items.find((t) => t.id === selected.id) ||
                selected
              }
              internal={internal}
              repos={repos.data || []}
              close={() => select(null)}
              action={action}
              busy={busy}
            />
          ) : page === "Repositories" ? (
            <Repositories
              repos={repos.data || []}
              admin={role === "admin"}
              projectId={projectId}
              action={action}
              busy={busy}
            />
          ) : page === "Activity" ? (
            <ActivityView projectId={projectId} jobs={jobs.data || []} />
          ) : (
            <>
              {page === "Overview" && (
                <>
                  <div className="metrics">
                    <Metric
                      label="Reported issues"
                      value={tickets.data?.items.length || 0}
                      caption="In this page of the queue"
                      icon={<TicketIcon />}
                    />
                    <Metric
                      label="In investigation"
                      value={
                        (tickets.data?.items || []).filter((t) =>
                          ["QUEUED", "INVESTIGATING"].includes(t.status),
                        ).length
                      }
                      caption="Queued or processing"
                      icon={<Activity />}
                    />
                    <Metric
                      label="Evidence available"
                      value={
                        (tickets.data?.items || []).filter(
                          (t) => t.status === "DIAGNOSED",
                        ).length
                      }
                      caption="Ready for engineer review"
                      icon={<FileSearch />}
                    />
                    <Metric
                      label={internal ? "Indexed snapshots" : "Needs attention"}
                      value={
                        internal
                          ? (repos.data || [])
                              .flatMap((r) => r.snapshots)
                              .filter((s) => s.status === "READY").length
                          : (tickets.data?.items || []).filter(
                              (t) => t.status === "ESCALATED",
                            ).length
                      }
                      caption={
                        internal
                          ? "Immutable Git commits"
                          : "Escalated to engineering"
                      }
                      icon={<FolderGit2 />}
                    />
                  </div>
                  <div className="workflow-banner">
                    <div className="banner-icon">
                      <FileSearch size={27} />
                    </div>
                    <div>
                      <strong>Evidence first. Always.</strong>
                      <p>
                        {internal
                          ? "Investigations link to exact commits, symbols and source lines. All diagnoses remain unverified until independently reviewed."
                          : "Submit what happened and what you expected. Your engineering team will investigate and share progress here."}
                      </p>
                    </div>
                    <span className="outline-tag">HUMAN REVIEW REQUIRED</span>
                  </div>
                </>
              )}
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>
                      {internal
                        ? "Investigation queue"
                        : "Your reported issues"}
                    </h2>
                    <p>Select an issue to see its latest progress.</p>
                  </div>
                  <div className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search issues"
                      placeholder="Search issues…"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    />
                  </div>
                </div>
                <div className="issue-table">
                  <div className="table-head">
                    <span>ISSUE / SUMMARY</span>
                    <span>STATUS</span>
                    <span>REPORTED</span>
                    <span />
                  </div>
                  {tickets.isPending ? (
                    <Empty text="Loading issues…" />
                  ) : list.length === 0 ? (
                    <Empty text="No issues here yet. Create a report to start an investigation." />
                  ) : (
                    list.map((t) => (
                      <button
                        className="issue-row"
                        key={t.id}
                        onClick={() => select(t)}
                      >
                        <div className="issue-title">
                          <span className="issue-icon">
                            <TicketIcon size={17} />
                          </span>
                          <div>
                            <small>ISS-{t.id.slice(0, 6).toUpperCase()}</small>
                            <strong>{t.title}</strong>
                          </div>
                        </div>
                        <Badge value={t.status} />
                        <span className="muted">
                          {new Date(t.created_at).toLocaleDateString()}
                        </span>
                        <ChevronRight size={18} />
                      </button>
                    ))
                  )}
                </div>
                <div className="panel-footer">
                  <span>
                    {list.length} issues shown · updates automatically
                  </span>
                  <div>
                    {cursor && (
                      <button
                        className="text-button"
                        onClick={() => setCursor("")}
                      >
                        First page
                      </button>
                    )}
                    {tickets.data?.next_cursor && (
                      <button
                        className="text-button"
                        onClick={() => setCursor(tickets.data!.next_cursor!)}
                      >
                        Next page <ArrowRight size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </section>
              <div className="bottom-grid">
                <section className="panel next-step">
                  <span className="eyebrow">HOW IT WORKS</span>
                  <h2>From symptom to source.</h2>
                  <div className="steps">
                    {[
                      "Report the behavior",
                      "Retrieve relevant evidence",
                      "Review the hypothesis",
                    ].map((s, i) => (
                      <div key={s}>
                        <span>0{i + 1}</span>
                        <p>{s}</p>
                        <Check size={14} />
                      </div>
                    ))}
                  </div>
                </section>
                <section className="panel next-step">
                  <span className="eyebrow">
                    {internal ? "WORKSPACE CAPABILITIES" : "YOUR REPORT"}
                  </span>
                  <h2>
                    {internal
                      ? "Built for traceable investigation."
                      : "A clear view of your progress."}
                  </h2>
                  <div className="capability">
                    <span className="live-dot" />
                    {internal
                      ? "Python AST & exact source references"
                      : "Your reports remain private to your project team"}
                  </div>
                  <div className="capability">
                    <span className="live-dot" />
                    {!internal
                      ? "Status updates appear automatically"
                      : health.data?.semantic_enabled
                        ? "Semantic + lexical retrieval"
                        : "Lexical retrieval · embeddings not configured"}
                  </div>
                  <p className="muted">
                    {internal
                      ? "Audit, patch generation and sandbox testing are scheduled for Phase 3."
                      : "An investigation update does not mean the issue is resolved. Your team will confirm when a fix is released."}
                  </p>
                </section>
              </div>
            </>
          )}
        </main>
        <footer>
          BUGHOUND-AI / AUTONOMOUS AGENTIC AI
          <span>
            Diagnosis is a hypothesis. Source evidence is not runtime proof.
          </span>
        </footer>
      </div>
      {creating && (
        <TicketForm
          close={() => setCreating(false)}
          submit={(body, key) =>
            action(async () => {
              const t = await post<Ticket>(
                `/projects/${projectId}/tickets`,
                body,
                key,
              );
              setCreating(false);
              select(t);
            })
          }
          busy={busy}
          error={error}
        />
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  caption,
  icon,
}: {
  label: string;
  value: number;
  caption: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="metric">
      <div>
        {label}
        <span>{icon}</span>
      </div>
      <strong>{String(value).padStart(2, "0")}</strong>
      <small>{caption}</small>
    </div>
  );
}

function TicketForm({
  close,
  submit,
  busy,
  error,
}: {
  close: () => void;
  submit: (body: unknown, key: string) => Promise<void>;
  busy: boolean;
  error: string;
}) {
  const [requestKey] = useState(() => crypto.randomUUID());
  function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    submit(
      {
        title: f.get("title"),
        description: f.get("description"),
        expected_behavior: f.get("expected"),
        actual_behavior: f.get("actual"),
        reproduction_steps: String(f.get("steps")).split("\n").filter(Boolean),
      },
      requestKey,
    );
  }
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-title"
      >
        <div className="panel-heading">
          <div>
            <span className="eyebrow">NEW REPORT</span>
            <h2 id="create-title">Tell us what happened.</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={close}
          >
            <X />
          </button>
        </div>
        <form onSubmit={send}>
          <label>
            Issue title
            <input
              autoFocus
              name="title"
              required
              minLength={4}
              maxLength={200}
              placeholder="e.g. Large PDF upload returns a server error"
            />
          </label>
          <label>
            Description
            <textarea
              name="description"
              required
              minLength={10}
              maxLength={8000}
              placeholder="Describe the issue and its impact…"
            />
          </label>
          <div className="form-grid">
            <label>
              Expected behavior
              <textarea
                name="expected"
                required
                minLength={3}
                maxLength={2000}
              />
            </label>
            <label>
              Actual behavior
              <textarea name="actual" required minLength={3} maxLength={2000} />
            </label>
          </div>
          <label>
            Steps to reproduce <small>One step per line</small>
            <textarea
              name="steps"
              required
              placeholder={
                "Open the upload page\nSelect a large PDF\nClick upload"
              }
            />
          </label>
          <small>
            Do not include passwords, API keys or personal customer data.
          </small>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div className="form-actions">
            <button type="button" className="secondary" onClick={close}>
              Cancel
            </button>
            <button disabled={busy}>
              {busy ? "Submitting…" : "Submit issue"}
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

type Action = (work: () => Promise<unknown>) => Promise<void>;
function IssueDetails({
  ticket,
  internal,
  repos,
  close,
  action,
  busy,
}: {
  ticket: Ticket;
  internal: boolean;
  repos: Repo[];
  close: () => void;
  action: Action;
  busy: boolean;
}) {
  const [snapshot, setSnapshot] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const runs = useQuery({
    queryKey: ["runs", ticket.id],
    queryFn: () => api<Run[]>(`/tickets/${ticket.id}/investigations`),
    refetchInterval: 2500,
  });
  const run = runs.data?.[0];
  const evidence = useQuery({
    queryKey: ["evidence", run?.id, run?.status],
    queryFn: () => api<Evidence[]>(`/investigations/${run!.id}/evidence`),
    enabled: internal && run?.status === "COMPLETED",
  });
  const options = repos.flatMap((r) =>
    r.snapshots
      .filter((s) => s.status === "READY")
      .map((s) => ({ id: s.id, repo: r.id, sha: s.commit_sha, name: r.name })),
  );
  const chosen = options.find((s) => s.id === snapshot) || options[0];
  const active =
    evidence.data?.find((e) => e.id === evidenceId) || evidence.data?.[0];
  return (
    <>
      <button className="text-button back" onClick={close}>
        ← Back to issues
      </button>
      <div className="detail-grid">
        <section className="panel detail-report">
          <div className="detail-title">
            <small>ISS-{ticket.id.slice(0, 6).toUpperCase()}</small>
            <Badge value={ticket.status} />
          </div>
          <h2>{ticket.title}</h2>
          <p className="preserve">{ticket.description}</p>
          <h3>Expected behavior</h3>
          <p className="preserve">{ticket.expected_behavior}</p>
          <h3>Actual behavior</h3>
          <p className="preserve">{ticket.actual_behavior}</p>
          <h3>Reproduction steps</h3>
          <ol>
            {ticket.reproduction_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
          <Attachments ticketId={ticket.id} />
          <hr />
          <h3>Investigation history</h3>
          {runs.isError && <p role="alert">{runs.error.message}</p>}
          {runs.data?.length ? (
            runs.data.map((r) => (
              <div className="history" key={r.id}>
                <Badge value={r.status} />
                <small>{new Date(r.created_at).toLocaleString()}</small>
              </div>
            ))
          ) : (
            <p className="muted">Waiting for engineering triage.</p>
          )}
        </section>
        <section className="panel diagnosis">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">FORENSIC INVESTIGATOR</span>
              <h2>
                {internal
                  ? "Evidence-based investigation"
                  : "Investigation progress"}
              </h2>
            </div>
            <FileSearch size={22} />
          </div>
          {internal && (
            <div className="investigation-controls">
              <label>
                Pinned repository snapshot
                <select
                  value={chosen?.id || ""}
                  onChange={(e) => setSnapshot(e.target.value)}
                >
                  {!options.length && (
                    <option value="">Index a repository first</option>
                  )}
                  {options.map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.name} · {s.sha.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={
                  busy ||
                  !chosen ||
                  ["QUEUED", "INVESTIGATING"].includes(ticket.status)
                }
                onClick={() =>
                  action(() =>
                    post(`/tickets/${ticket.id}/investigations`, {
                      repository_id: chosen.repo,
                      commit_sha: chosen.sha,
                    }),
                  )
                }
              >
                <Activity size={16} />
                Run investigation
              </button>
            </div>
          )}
          {run?.diagnosis?.hypotheses ? (
            <div className="diagnosis-content">
              <div className="notice">
                UNVERIFIED ·{" "}
                {run.diagnosis.mode === "demo"
                  ? "Retrieval-only demo. No LLM reasoning performed."
                  : "Model hypothesis. Independent review required."}
              </div>
              <h3>Investigation summary</h3>
              <p>{run.diagnosis.summary}</p>
              {run.diagnosis.hypotheses.map((h, i) => (
                <div className="hypothesis" key={i}>
                  <span className="eyebrow">CANDIDATE {i + 1}</span>
                  <h3>{h.title}</h3>
                  <p>{h.explanation}</p>
                  <div className="evidence-links">
                    {h.evidence_ids.map((id) => (
                      <button
                        className="text-button"
                        key={id}
                        onClick={() => {
                          setEvidenceId(id);
                          document
                            .getElementById("source-evidence")
                            ?.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        <Code2 size={14} />
                        Evidence {id.slice(0, 6)}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <h3>Missing information & limitations</h3>
              <ul>
                {[
                  ...run.diagnosis.missing_information,
                  ...run.diagnosis.limitations,
                ].map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
              <small className="muted">
                Prompt: {run.diagnosis.prompt_version}
              </small>
            </div>
          ) : (
            <Empty
              text={
                run?.status === "FAILED"
                  ? "Investigation failed. An engineer needs to review the job configuration."
                  : run && ["QUEUED", "INVESTIGATING"].includes(run.status)
                    ? "Investigation in progress. This view updates automatically."
                    : internal
                      ? "Choose an indexed commit to retrieve grounded source evidence."
                      : "Your report is with the engineering team. Status updates will appear here."
              }
            />
          )}
        </section>
      </div>
      {internal && run?.status === "COMPLETED" && (
        <section className="panel evidence-panel" id="source-evidence">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">SOURCE OF TRUTH</span>
              <h2>Evidence explorer</h2>
            </div>
            <span className="outline-tag">
              <ShieldCheck size={14} /> HASH CHECKED
            </span>
          </div>
          {evidence.error && <p className="error">{evidence.error.message}</p>}
          {active ? (
            <div className="source-layout">
              <div className="source-list">
                {evidence.data?.map((e) => (
                  <button
                    key={e.id}
                    className={
                      active.id === e.id
                        ? "source-item selected"
                        : "source-item"
                    }
                    onClick={() => setEvidenceId(e.id)}
                  >
                    <Code2 size={16} />
                    <div>
                      <strong>{e.symbol}</strong>
                      <small>
                        {e.path}:{e.start_line}–{e.end_line}
                      </small>
                    </div>
                  </button>
                ))}
              </div>
              <div className="source-content">
                <div className="source-toolbar">
                  <span>{active.path}</span>
                  <code>{active.commit_sha.slice(0, 12)}</code>
                </div>
                <pre>
                  {active.content.split("\n").map((line, i) => (
                    <div key={i}>
                      <span className="line-number">
                        {active.start_line + i}
                      </span>
                      <code>{line || " "}</code>
                    </div>
                  ))}
                </pre>
                <div className="source-hash">SHA-256 {active.content_hash}</div>
                <div className="source-meta">
                  <strong>Static call candidates</strong>
                  <p>
                    {active.metadata.call_candidates?.join(", ") ||
                      "None extracted"}
                  </p>
                  <small>
                    AST relationships are syntactic; dynamic dispatch may not
                    resolve.
                  </small>
                </div>
              </div>
            </div>
          ) : (
            <Empty text="No source evidence available for this investigation." />
          )}
        </section>
      )}
    </>
  );
}

function Repositories({
  repos,
  admin,
  projectId,
  action,
  busy,
}: {
  repos: Repo[];
  admin: boolean;
  projectId: string;
  action: Action;
  busy: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [sha, setSha] = useState<Record<string, string>>({});
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const [results, setResults] = useState<Evidence[]>([]);
  const options = repos.flatMap((r) =>
    r.snapshots
      .filter((s) => s.status === "READY")
      .map((s) => ({ ...s, name: r.name })),
  );
  return (
    <>
      <div className="section-actions">
        <p className="muted">
          Python source and documentation, pinned to an immutable commit.
        </p>
        {admin && (
          <button className="secondary" onClick={() => setAdding(!adding)}>
            <Plus size={16} />
            Connect repository
          </button>
        )}
      </div>
      {adding && (
        <section className="panel connection-form">
          <h2>Connect an authorized repository</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              action(async () => {
                await post("/repositories", {
                  project_id: projectId,
                  name: f.get("name"),
                  remote_url: f.get("url"),
                });
                setAdding(false);
              });
            }}
          >
            <label>
              Repository name
              <input name="name" required minLength={2} />
            </label>
            <label>
              HTTPS Git URL or allowlisted local path
              <input
                name="url"
                required
                placeholder="https://github.com/organization/python-service.git"
              />
            </label>
            <small>
              Only connect repositories you are authorized to inspect. Do not
              put credentials in URLs.
            </small>
            <button disabled={busy}>Connect repository</button>
          </form>
        </section>
      )}
      <div className="repo-grid">
        {repos.map((r) => (
          <section className="panel repo-card" key={r.id}>
            <div className="repo-heading">
              <span className="repo-icon">
                <FolderGit2 />
              </span>
              <div>
                <h2>{r.name}</h2>
                <small>{r.remote_url}</small>
              </div>
            </div>
            <div className="snapshot-list">
              {r.snapshots.map((s) => (
                <div key={s.id}>
                  <code>{s.commit_sha.slice(0, 12)}</code>
                  <Badge value={s.status} />
                  <small>
                    {s.stats.files ?? 0} files · {s.stats.chunks ?? 0} chunks ·{" "}
                    {s.stats.retrieval || "pending"}
                  </small>
                  {!!s.stats.syntax_errors?.length && (
                    <small className="warning">
                      {s.stats.syntax_errors.length} Python files skipped due to
                      syntax errors
                    </small>
                  )}
                </div>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                action(() =>
                  post(`/repositories/${r.id}/index`, {
                    commit_sha: sha[r.id],
                  }),
                );
              }}
            >
              <label>
                Exact commit SHA
                <input
                  aria-label={`Commit SHA for ${r.name}`}
                  value={sha[r.id] || ""}
                  onChange={(e) => setSha({ ...sha, [r.id]: e.target.value })}
                  required
                  pattern="[0-9a-f]{40}"
                  placeholder="40-character Git commit SHA"
                />
              </label>
              <button className="secondary" disabled={busy}>
                <Activity size={16} />
                Index snapshot
              </button>
            </form>
          </section>
        ))}
      </div>
      {!repos.length && (
        <section className="panel">
          <Empty text="No repositories connected. An administrator can add an authorized Python repository." />
        </section>
      )}
      <section className="panel search-panel">
        <span className="eyebrow">RETRIEVAL WORKBENCH</span>
        <h2>Find the relevant source.</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const id = selected || options[0]?.id;
            action(async () => {
              setResults(
                await api<Evidence[]>(
                  `/snapshots/${id}/search?q=${encodeURIComponent(query)}`,
                ),
              );
            });
          }}
        >
          <label>
            Snapshot
            <select
              value={selected || options[0]?.id || ""}
              onChange={(e) => {
                setSelected(e.target.value);
                setResults([]);
              }}
            >
              {options.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.commit_sha.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Search source and documentation
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
              minLength={2}
              maxLength={1000}
              placeholder="PDF upload size limit"
            />
          </label>
          <button disabled={busy || !options.length}>
            <Search size={16} />
            Search
          </button>
        </form>
        {results.map((e) => (
          <details className="search-result" key={e.id}>
            <summary>
              <Code2 size={16} />
              <strong>{e.symbol}</strong>
              <span>
                {e.path}:{e.start_line}–{e.end_line}
              </span>
            </summary>
            <pre>{e.content}</pre>
            <small>
              Commit {e.commit_sha} · SHA-256 {e.content_hash}
            </small>
          </details>
        ))}
      </section>
    </>
  );
}

function ActivityView({
  projectId,
  jobs,
}: {
  projectId: string;
  jobs: {
    id: string;
    kind: string;
    status: string;
    attempts: number;
    error: string | null;
  }[];
}) {
  const audit = useQuery({
    queryKey: ["audit", projectId],
    queryFn: () =>
      api<{ id: string; actor: string; action: string; created_at: string }[]>(
        `/projects/${projectId}/audit-events`,
      ),
    enabled: !!projectId,
    refetchInterval: 3000,
  });
  return (
    <div className="detail-grid">
      <section className="panel activity-panel">
        <h2>
          <Terminal size={19} /> Background jobs
        </h2>
        {jobs.map((j) => (
          <div className="activity-row" key={j.id}>
            <div>
              <strong>{pretty(j.kind)}</strong>
              <small>
                {j.id.slice(0, 8)} · attempt {j.attempts}
              </small>
              {j.error && <p className="warning">{j.error}</p>}
            </div>
            <Badge value={j.status} />
          </div>
        ))}
        {!jobs.length && <Empty text="No background jobs yet." />}
      </section>
      <section className="panel activity-panel">
        <h2>
          <ShieldCheck size={19} /> Audit trail
        </h2>
        {audit.error && <p className="error">{audit.error.message}</p>}
        {audit.data?.map((e) => (
          <div className="audit-row" key={e.id}>
            <span className="audit-dot" />
            <div>
              <strong>{pretty(e.action)}</strong>
              <p>
                {e.actor} · {new Date(e.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
