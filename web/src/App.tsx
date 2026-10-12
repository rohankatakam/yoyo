import { useEffect, useState } from 'react';
import { Detail } from './Detail';
import type { Company, Run, Source } from './types';

export function App() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, select] = useState('');
  const [detail, setDetail] = useState<Company | null>(null);
  const [query, search] = useState('');
  const [error, setError] = useState('');
  const [view, setView] = useState('Companies');
  async function refresh() {
    try {
      const data = await Promise.all(['companies', 'runs', 'sources'].map(async path => {
        const response = await fetch('/api/' + path);
        if (!response.ok) throw new Error(`Could not load ${path}`);
        return response.json();
      }));
      setCompanies(data[0]); setRuns(data[1]); setSources(data[2]); setError('');
    } catch (e) { setError(String(e)); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setDetail(null);
    fetch('/api/companies/' + selected, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('Could not load company'); return r.json(); })
      .then(setDetail).catch(e => { if (e.name !== 'AbortError') setError(String(e)); });
    return () => controller.abort();
  }, [selected, companies]);
  return <main>
    <header><div><p className="eyebrow">YOYO / RESEARCH LEDGER</p><h1>Company evidence</h1></div>
      <button onClick={refresh}>Refresh</button></header>
    <p className="muted">Source-backed assertions. Identity and factual accuracy remain subject to review.</p>
    <nav>{['Companies', 'Sources', 'Runs'].map(v => <button className={view === v ? 'active' : ''}
      key={v} onClick={() => setView(v)}>{v}</button>)}</nav>
    {error && <p role="alert">{error}</p>}
    {view === 'Companies' && <div className="layout"><aside>
      <input aria-label="Search companies" placeholder="Search companies" value={query} onChange={e => search(e.target.value)} />
      <p className="muted">{companies.length} company mentions</p>
      {companies.filter(c => c.name.toLowerCase().includes(query.toLowerCase())).map(c =>
        <button className={'entity ' + (selected === c.id ? 'active' : '')} key={c.id} onClick={() => select(c.id)}>
          <strong>{c.name}</strong><small>{c.sector_id || 'Sector unknown'}</small></button>)}
    </aside><section>{detail ? <Detail company={detail} /> : <p className="empty">Select a company to inspect its evidence.</p>}</section></div>}
    {view === 'Sources' && <section>{sources.map(s => <article key={s.id}>
      <h2>{s.title}</h2><p>{s.provider} · {s.external_id}</p>
      <a href={'/api/sources/' + s.id} target="_blank" rel="noreferrer">Normalized transcript + metadata</a>{' · '}
      <a href={'/api/sources/' + s.id + '/artifact'} target="_blank" rel="noreferrer">Original artifact</a>
    </article>)}</section>}
    {view === 'Runs' && <section>{runs.map(r => <article key={r.id}>
      <h2>{r.status} <small>{new Date(r.created_at).toLocaleString()}</small></h2>
      <p>{r.input.model || r.input.mode || 'Legacy import'} · {Object.keys(r.progress.operations || {}).length} model operations</p>
      {r.trace_url && <a href={r.trace_url} target="_blank" rel="noreferrer">Open LangSmith trace</a>}
      {r.error && <p role="alert">{r.error}</p>}
      <details><summary>Run record and committed counts</summary><pre>{JSON.stringify(r, null, 2)}</pre></details>
    </article>)}</section>}
  </main>;
}
