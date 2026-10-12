import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Company = {
  id: string;
  name: string;
  identity_status: string;
  domain: string | null;
  linkedin_url: string | null;
};
type Evidence = {
  quote: string;
  start: number;
  end: number;
  speaker_label: string;
  segment_index: number;
  source_id: string;
  title: string;
  url: string | null;
  sha256: string;
  parent_sha256: string;
  run_id: string;
  provenance: { review: string; retrieved_at: string; selection: string };
};
type Claim = {
  id: string;
  statement: string;
  predicate: string;
  review_status: string;
  evidence: Evidence[];
};
type Detail = Company & {
  claims: Claim[];
  identity_decisions: { rationale: string }[];
};
type Run = {
  id: string;
  status: string;
  created_at: string;
  trace_url: string | null;
  trace_status: string;
  origin: string;
  result: { delta: Record<string, number>; cost_basis: string } | null;
};
async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok)
    throw new Error(
      `Could not load data (${r.status}). Check the local API and database.`,
    );
  return r.json();
}
const time = (n: number) =>
  `${Math.floor(n / 60)}:${Math.floor(n % 60)
    .toString()
    .padStart(2, "0")}`;
function App() {
  const [companies, setCompanies] = useState<Company[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [tab, setTab] = useState("companies"),
    [query, setQuery] = useState("");
  async function refresh() {
    setError("");
    setLoading(true);
    try {
      const [c, r] = await Promise.all([
        get<Company[]>("/api/companies"),
        get<Run[]>("/api/runs"),
      ]);
      setCompanies(c);
      setRuns(r);
      setSelected((s) =>
        s && c.some((x) => x.id === s) ? s : (c[0]?.id ?? null),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  useEffect(() => {
    let active = true;
    setDetail(null);
    if (selected)
      get<Detail>(`/api/companies/${selected}`)
        .then((d) => {
          if (active) setDetail(d);
        })
        .catch((e) => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [selected]);
  return (
    <>
      <header>
        <a className="brand" href="/">
          yoyo<span> / company intelligence</span>
        </a>
        <div className="headerlinks">
          <a href="http://localhost:5050" target="_blank" rel="noreferrer">
            Database ↗
          </a>
          <a
            href="https://smith.langchain.com"
            target="_blank"
            rel="noreferrer"
          >
            LangSmith ↗
          </a>
          <span className="local">LOCAL</span>
        </div>
      </header>
      <main>
        <div className="heading">
          <div>
            <p className="eyebrow">RESEARCH LEDGER · 001</p>
            <h1>Follow the evidence.</h1>
            <p className="muted">
              Companies, attributed claims, and the passages behind them.
            </p>
          </div>
          <button onClick={() => void refresh()}>Refresh data ↻</button>
        </div>
        <div className="notice">
          <span>REFERENCE DATA</span> Two selected passages from one archived
          episode. Pending human review; identities and statements are not
          independently verified.
        </div>
        <nav aria-label="Dataset views">
          <button
            className={tab === "companies" ? "active" : ""}
            onClick={() => setTab("companies")}
          >
            Companies <small>{companies.length}</small>
          </button>
          <button
            className={tab === "runs" ? "active" : ""}
            onClick={() => setTab("runs")}
          >
            Run history <small>{runs.length}</small>
          </button>
        </nav>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {loading && <p role="status">Loading ledger…</p>}
        {tab === "companies" ? (
          <div className="workspace">
            <aside>
              <label htmlFor="search">Find a company</label>
              <input
                id="search"
                placeholder="Search by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <p className="listlabel">COMPANY / IDENTITY</p>
              {companies
                .filter((c) =>
                  c.name.toLowerCase().includes(query.toLowerCase()),
                )
                .map((c) => (
                  <button
                    key={c.id}
                    className={`company ${selected === c.id ? "selected" : ""}`}
                    onClick={() => setSelected(c.id)}
                  >
                    <strong>{c.name}</strong>
                    <span>
                      Unresolved identity <b>→</b>
                    </span>
                  </button>
                ))}
              {!loading && !companies.length && (
                <p className="muted">
                  No companies yet. Import the reference fixture to begin.
                </p>
              )}
              {companies.length > 0 &&
                !companies.some((c) =>
                  c.name.toLowerCase().includes(query.toLowerCase()),
                ) && <p>No matching companies.</p>}
            </aside>
            <section className="detail">
              {detail ? (
                <>
                  <div className="detailtitle">
                    <h2>{detail.name}</h2>
                    <span className="badge">Episode-scoped identity</span>
                  </div>
                  <p className="muted">
                    Domain, LinkedIn, ownership, funding stage and valuation:
                    unknown.
                  </p>
                  <details>
                    <summary>Identity decision & record ID</summary>
                    <p>{detail.identity_decisions[0]?.rationale}</p>
                    <code>{detail.id}</code>
                  </details>
                  <h3>
                    Attributed claims <small>{detail.claims.length}</small>
                  </h3>
                  {detail.claims.map((c) => (
                    <article key={c.id}>
                      <div className="claimtype">
                        {c.predicate.replaceAll("_", " ")}
                        <span>NOT VERIFIED</span>
                      </div>
                      <h4>{c.statement}</h4>
                      {c.evidence.map((e, i) => (
                        <div key={i}>
                          <blockquote>“{e.quote}”</blockquote>
                          <div className="evidencemeta">
                            <strong>
                              {time(e.start)}–{time(e.end)}
                            </strong>
                            <span>{e.speaker_label} · identity unknown</span>
                            <span>Segment {e.segment_index}</span>
                          </div>
                          <details>
                            <summary>Inspect source & provenance</summary>
                            <p>{e.title}</p>
                            <p>{e.provenance.review}</p>
                            <p>{e.provenance.selection}</p>
                            <dl>
                              <dt>Retrieved</dt>
                              <dd>{e.provenance.retrieved_at}</dd>
                              <dt>Excerpt SHA-256</dt>
                              <dd>
                                <code>{e.sha256}</code>
                              </dd>
                              <dt>Parent SHA-256</dt>
                              <dd>
                                <code>{e.parent_sha256}</code>
                              </dd>
                              <dt>Origin run</dt>
                              <dd>
                                <code>{e.run_id}</code>
                              </dd>
                            </dl>
                            <div className="links">
                              <a
                                href={`/api/sources/${e.source_id}/artifact`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Stored source JSON ↗
                              </a>
                              {runs.find((r) => r.id === e.run_id)
                                ?.trace_url && (
                                <a
                                  href={
                                    runs.find((r) => r.id === e.run_id)!
                                      .trace_url!
                                  }
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Import trace ↗
                                </a>
                              )}
                            </div>
                          </details>
                        </div>
                      ))}
                    </article>
                  ))}
                </>
              ) : (
                <p className="muted">
                  {selected
                    ? "Loading company…"
                    : "Select a company to inspect its evidence."}
                </p>
              )}
            </section>
          </div>
        ) : (
          <section className="runtable">
            <h2>Persistent run history</h2>
            <p className="muted">
              Each import is recorded. Replays reuse the same research records.
            </p>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Started</th>
                    <th>Result</th>
                    <th>New companies</th>
                    <th>New claims</th>
                    <th>Observability</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td>
                        {new Date(r.created_at).toLocaleString()}
                        <code className="runid">{r.id}</code>
                      </td>
                      <td>{r.status}</td>
                      <td>{r.result?.delta.companies ?? "—"}</td>
                      <td>{r.result?.delta.claims ?? "—"}</td>
                      <td>
                        {r.trace_url ? (
                          <a
                            href={r.trace_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            View trace ↗
                          </a>
                        ) : (
                          r.trace_status
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!runs.length && <p>No runs yet.</p>}
          </section>
        )}
        <footer>Evidence stays attributable. Unknown stays unknown.</footer>
      </main>
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
