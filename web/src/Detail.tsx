import type { Company } from './types';
const time = (n: number | null) => n === null ? 'Time unknown' : `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, '0')}`;
export function Detail({ company: c }: { company: Company }) {
  const profile = { Sector: c.sector_id, Subsector: c.subsector_id, Domain: c.domain,
    LinkedIn: c.linkedin_url, Ownership: c.ownership_status, 'Funding stage': c.funding_stage,
    Capabilities: c.capabilities?.join(', '), 'End markets': c.end_markets?.join(', '),
    Headquarters: c.headquarters_country_codes?.join(', '), 'Operating countries': c.operating_country_codes?.join(', '),
    'Operating regions': c.operating_region_codes?.join(', ') };
  return <><h2>{c.name}</h2><p>{c.description || 'Business description unknown'}</p>
    <dl>{Object.entries(profile).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Unknown'}</dd></div>)}</dl>
    <details><summary>Identity decision and profile evidence</summary><pre>{JSON.stringify({ identity: c.identity,
      field_evidence: c.field_evidence, industry_codes: c.industry_codes, financial_observations: c.financial_observations }, null, 2)}</pre></details>
    <h3>{c.claims?.length || 0} attributed assertions</h3>
    {c.claims?.map(claim => <article key={claim.id}><p className="badge">{claim.status.replaceAll('_', ' ')} · {claim.annotation?.time_class.replaceAll('_', ' ') || 'Not classified'}</p>
      <h3>{claim.text}</h3>{claim.annotation && <p className="muted">{claim.annotation.rationale}</p>}
      {claim.evidence.map(e => <blockquote key={e.id}><p>“{e.quote}”</p>
        <small>{e.speaker_label || 'Speaker unknown'} · {e.segments.map(s => time(s.start)).join(', ')} · {e.role}</small><br />
        <a href={'/api/sources/' + e.source_id} target="_blank" rel="noreferrer">{e.title}</a>
        <details><summary>Transcript context</summary>{e.segments.map(s => <p key={s.id}>{s.text}</p>)}</details>
      </blockquote>)}
      <details><summary>Extraction provenance</summary><pre>{JSON.stringify(claim.extraction, null, 2)}</pre></details>
    </article>)}
  </>;
}
