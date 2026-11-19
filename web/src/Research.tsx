import { useEffect, useState } from 'react';
import type { Locale, Messages } from './i18n';
import type { components } from './schema';
import { getJSON, requestJSON, RequestError } from './api';
import { InputFields } from './InputFields';
import { downloadJSON } from './download';

type Catalog = components['schemas']['ResearchCatalog'];
type Result = components['schemas']['ResearchResult'];
type Tool = components['schemas']['ResearchTool'];

function ResearchTool({ tool, locale, t }: { tool: Tool; locale: Locale; t: Messages }) {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function run(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form));
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await requestJSON<Result>(
        `/api/research/${tool.id}`, { locale, values }, String(values.query ?? tool.title[locale]), tool.id,
      );
      setResult(response.data);
    } catch (failure) { setError(failure instanceof RequestError ? failure.detail ?? t.error : t.error); }
    finally { setBusy(false); }
  }

  return <section className="panel research-tool">
    <h2>{tool.title[locale]}</h2><p>{tool.description[locale]}</p>
    <form onSubmit={event => { event.preventDefault(); void run(event.currentTarget); }}>
      <InputFields fields={tool.fields} prefix={tool.id} locale={locale} disabled={busy} />
      <button className="primary" disabled={busy}>{busy ? t.working : t.researchSubmit}</button>
    </form>
    {error && <p role="alert" className="notice">{error}</p>}
    {result && <div className="research-results" aria-live="polite">
      {result.cards.length === 0 && <p>{t.researchEmpty}</p>}
      {result.cards.map((card, index) => <article key={index} className="confirmation">
        <h3>{card.title}</h3><p>{card.text}</p>
        <dl>{(card.fields ?? []).map(field => <div key={field.label}><dt>{field.label}</dt><dd><bdi>{field.value}</bdi></dd></div>)}</dl>
        {card.provenance && <p><a href={card.provenance.url} target="_blank" rel="noreferrer">{card.provenance.publisher}</a>
          <small> · {t['researchMode_' + card.provenance.mode]} · <bdi>{card.provenance.retrieved_at}</bdi></small>
        </p>}
      </article>)}
      {result.cards.length > 0 && <button className="text-button" type="button"
        onClick={() => downloadJSON(`${tool.id}-evidence.json`, result)}>{t.researchExport}</button>}
    </div>}
  </section>;
}

export function Research({ locale, t }: { locale: Locale; t: Messages }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    getJSON<Catalog>('/api/research/catalog', controller.signal)
      .then(setCatalog).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, []);
  if (!catalog) return <p role={failed ? 'alert' : 'status'}>{failed ? t.error : t.loading}</p>;
  return <div className="research-workspace">
    <header><h2>{catalog.title[locale]}</h2><p>{catalog.intro[locale]}</p></header>
    {catalog.tools.map(tool => <ResearchTool key={tool.id + locale} tool={tool} locale={locale} t={t} />)}
  </div>;
}
