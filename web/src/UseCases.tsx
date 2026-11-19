import { requestJSON } from './api';
import { InputFields } from './InputFields';
import { useState } from 'react';
import type { Locale, Messages } from './i18n';
import type { components } from './schema';

type Scenario = components['schemas']['ScenarioView'];

export function UseCaseWorkspace({ entry, locale, t }: { entry: Scenario; locale: Locale; t: Messages }) {
  const [result, setResult] = useState('');
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(form: HTMLFormElement) {
    setBusy(true); setFailed(false); setResult('');
    const values = Object.fromEntries(new FormData(form).entries());
    try {
      const response = await requestJSON<components['schemas']['ScenarioResult']>(
        `/api/scenarios/${entry.id}/evaluate`, { locale, values }, entry.example[locale], entry.id,
      );
      setResult(response.data.result);
    } catch { setFailed(true); } finally { setBusy(false); }
  }

  return <section className="panel use-case-workspace">
    <div className="eyebrow">{t.scenarioScope}</div>
    <h2>{entry.title[locale]}</h2>
    <h3>{entry.example[locale]}</h3>
    <h3>{t.scenarioSteps}</h3>
    <ol>{entry.steps[locale].map(step => <li key={step}>{step}</li>)}</ol>
    {entry.fields.length > 0 && <form onChange={() => setResult('')} onSubmit={event => { event.preventDefault(); void submit(event.currentTarget); }}>
      <InputFields fields={entry.fields} prefix={entry.id} locale={locale} disabled={busy} />
      <button className="primary" disabled={busy}>{busy ? t.working : entry.submit[locale]}</button>
    </form>}
    {result && <p role="status" className="confirmation">{result}</p>}
    {failed && <p role="alert">{t.error}</p>}
    <h3>{t.scenarioWhy}</h3><p>{entry.why[locale]}</p>
    <p><a href={entry.source.url} target="_blank" rel="noreferrer">{t.scenarioSource} · {entry.source.title}</a></p>
  </section>;
}
