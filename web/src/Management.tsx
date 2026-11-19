import { getJSON, requestJSON } from './api';
import { downloadJSON } from './download';
import type { components } from './schema';
import { useEffect, useState } from 'react';
import type { Locale } from './i18n';

type Material = components['schemas']['MaterialDefinition'];
type Catalog = components['schemas']['ManagementCatalog'];

export function Management({ locale, messages }: { locale: Locale; messages: Record<string, Record<string, string>> }) {
  const t = messages[locale];
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [draft, setDraft] = useState('');
  const [procedureDraft, setProcedureDraft] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [text, setText] = useState('');
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    getJSON<Catalog>('/api/management/catalog', controller.signal)
      .then((data: Catalog) => { setCatalog(data); setText(data.debug_example); setDraft(JSON.stringify(data.materials, null, 2)); setProcedureDraft(JSON.stringify(data.procedure_definitions, null, 2)); })
      .catch(() => { if (!controller.signal.aborted) setError(t.error); });
    return () => controller.abort();
  }, []);

  async function run(action: () => Promise<void>) {
    setError(''); setNotice(''); setBusy(true);
    try { await action(); } catch (failure) {
      setError(`${t.error} ${failure instanceof Error ? failure.message : ''}`);
    } finally { setBusy(false); }
  }

  if (!catalog) return <section className="panel"><h1>{t.title}</h1><p role={error ? 'alert' : 'status'}>{error || t.loading}</p></section>;
  return <div className="management">
    <h1>{t.title}</h1>
    <p>{t.recognized} · {catalog.policy_version}</p>
    {error && <p role="alert" className="notice">{error}</p>}
    {notice && <p role="status" className="notice">{notice}</p>}
    <section className="panel">
      <h2>{t.materials}</h2>
      <div className="table-scroll"><table><thead><tr><th>{t.id}</th><th>{t.en}</th><th>{t.he}</th><th>{t.aliases}</th></tr></thead>
        <tbody>{catalog.materials.map(material => <tr key={material.id}><td><code>{material.id}</code></td><td>{material.labels.en}</td><td dir="rtl">{material.labels.he}</td><td>{material.aliases.join(', ')}</td></tr>)}</tbody>
      </table></div>
      <h3>{t.add}</h3>
      <form className="management-form" onSubmit={event => {
        event.preventDefault();
        const fields = new FormData(event.currentTarget);
        try {
          const entries = JSON.parse(draft) as Material[];
          entries.push({ id: String(fields.get('id')), labels: { en: String(fields.get('en')), he: String(fields.get('he')) }, aliases: String(fields.get('aliases')).split('\n').map(alias => alias.trim()).filter(Boolean) });
          setDraft(JSON.stringify(entries, null, 2));
          setNotice(t.save);
          event.currentTarget.reset();
        } catch { setError(t.error); }
      }}>
        <label>{t.id}<input name="id" dir="ltr" pattern="[a-z][a-z0-9_]*" maxLength={64} required /></label>
        <label>{t.en}<input name="en" maxLength={100} required /></label>
        <label>{t.he}<input name="he" dir="rtl" maxLength={100} required /></label>
        <label>{t.aliases}<textarea name="aliases" dir="ltr" required rows={3} /></label>
        <button className="primary" disabled={busy}>{t.save}</button>
      </form>
      <h3>{t.draft}</h3>
      <p>{t.instructions}</p>
      <label htmlFor="catalog-draft">{t.raw}</label>
      <textarea id="catalog-draft" className="catalog-json" dir="ltr" rows={12} value={draft} onChange={event => { setDraft(event.target.value); setNotice(''); }} />
      <button className="primary" disabled={busy} onClick={() => void run(async () => {
        const { data: validated } = await requestJSON<components['schemas']['MaterialCatalog']>('/api/management/validate', { materials: JSON.parse(draft) }, '', 'management.validate');
        downloadJSON('materials.json', validated.materials);
        setNotice(t.validated);
      })}>{t.export}</button>
    </section>
    <section className="panel">
      <h2>{t.procedures}</h2>
      <div className="table-scroll"><table><thead><tr><th>{t.object}</th><th>{t.material}</th><th>{t.surface}</th><th>{t.finishes}</th></tr></thead>
        <tbody>{catalog.procedures.map(procedure => <tr key={procedure.surface}><td>{procedure.object}</td><td>{procedure.material}</td><td>{procedure.surface}</td><td>{procedure.finishes.map(finish => finish ?? '∅').join(', ')}</td></tr>)}</tbody>
      </table></div>
      <p>{t.procedureInstructions}</p>
      <label htmlFor="procedure-draft">{t.procedureDraft}</label>
      <textarea id="procedure-draft" className="catalog-json" dir="ltr" rows={12} value={procedureDraft} onChange={event => setProcedureDraft(event.target.value)} />
      <button type="button" className="primary" disabled={busy} onClick={() => void run(async () => {
        const { data: validated } = await requestJSON<components['schemas']['ProcedureCatalog']>('/api/management/validate-procedures', { procedures: JSON.parse(procedureDraft) }, '', 'management.validate-procedures');
        downloadJSON('procedures.json', validated.procedures);
        setNotice(t.proceduresValidated);
      })}>{t.exportProcedures}</button>
      <details><summary>{t.ruleDetails}</summary><pre dir="ltr">{JSON.stringify(catalog.procedures, null, 2)}</pre></details>
    </section>
    <section className="panel">
      <h2>{t.algorithm}</h2><ol>{catalog.algorithm.map(step => <li key={step} dir="ltr">{step}</li>)}</ol>
      <h3>{t.inspector}</h3>
      <form onSubmit={event => { event.preventDefault(); void run(async () => {
        const response = await requestJSON('/api/management/resolve', { text }, text, 'management.resolve');
        setResult(response.data);
      }); }}>
        <label htmlFor="resolve-text">{t.english}</label>
        <textarea id="resolve-text" dir="ltr" required maxLength={1000} rows={3} value={text} onChange={event => { setText(event.target.value); setResult(null); }} />
        <button className="primary" disabled={busy}>{t.inspect}</button>
      </form>
      {result !== null && <pre dir="ltr" role="status">{JSON.stringify(result, null, 2)}</pre>}
    </section>
    <section className="panel"><h2>{t.dictionaries}</h2>
      {Object.entries(catalog).filter(([key]) => !['materials', 'procedures', 'algorithm', 'policy_version', 'scenarios', 'procedure_definitions'].includes(key)).map(([name, value]) =>
        <details key={name}><summary>{name}</summary><pre dir="ltr">{JSON.stringify(value, null, 2)}</pre></details>)}
    </section>
    <section className="panel">
      <h2>{t.scenarios}</h2>
      {catalog.scenarios.map(entry => <details key={entry.id}><summary>{entry.title[locale]}</summary>
        <pre dir="ltr">{JSON.stringify(entry, null, 2)}</pre>
      </details>)}
    </section>
  </div>;
}
