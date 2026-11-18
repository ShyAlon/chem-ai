import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { post, RequestError } from './api';
import type { components } from './schema';
import { DecisionCard, Evidence, LanguageSwitch } from './components';
import { applyLocale, initialLocale, languages } from './i18n';
import './style.css';

const defaultLocale = initialLocale();
applyLocale(defaultLocale);

function App() {
  const [locale, setLocale] = useState(defaultLocale);
  const [text, setText] = useState('');
  const [inputs, setInputs] = useState<components['schemas']['Interpretation'] | null>(null);
  const [decision, setDecision] = useState<components['schemas']['Decision'] | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [interpretationId, setInterpretationId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const t = languages[locale];

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  function reset() {
    setInputs(null);
    setDecision(null);
    setRequestId(null);
    setInterpretationId(null);
    setFailed(false);
  }

  async function run(send: () => Promise<{ requestId: string | null }>) {
    setPending(true);
    setFailed(false);
    try {
      const { requestId: id } = await send();
      setRequestId(id);
    } catch (error) {
      setRequestId(error instanceof RequestError ? error.requestId : null);
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  const supported = inputs && inputs.surface !== 'unknown' && inputs.materials !== 'unknown';
  return (
    <>
      <header className="site-header">
        <div className="brand"><img src="/icon.svg" alt="" width="36" height="36" /><bdi>HomeChem</bdi></div>
        <LanguageSwitch locale={locale} choose={next => { applyLocale(next); setLocale(next); }} t={t} />
      </header>
      <main>
        <section className="hero">
          <div className="eyebrow">{t.workspace}</div>
          <h1>{t.heading}</h1>
          <p>{t.intro}</p>
        </section>
        {!online && <p className="notice" role="status">{t.offline}</p>}
        <div className="layout">
          <div className="panel notebook">
            <form onSubmit={event => { event.preventDefault(); if (!online || pending || inputs || !text.trim()) return;
              void run(async () => {
                const result = await post('interpret', { text: text.trim() });
                setInputs(result.data);
                setInterpretationId(result.requestId);
                return result;
              }); }}>
              <label htmlFor="question">{t.prompt}</label>
              <textarea id="question" dir="auto" value={text} maxLength={1000} rows={4}
                required disabled={pending} placeholder={t.placeholder} onChange={event => { reset(); setText(event.target.value); }} />
              <div className="actions">
                <button className="primary" disabled={!online || pending || !text.trim() || Boolean(inputs)}>{pending && !inputs ? t.working : t.inspect}</button>
                <button className="text-button" type="button" disabled={pending} onClick={() => {
                  reset();
                  setText(t.exampleText);
                  document.getElementById('question')?.focus();
                }}>{t.example}</button>
              </div>
            </form>
            {inputs && !decision && (
              <section className="confirmation" aria-labelledby="confirm-title">
                <h2 id="confirm-title">{supported ? t.confirm : t.unverified}</h2>
                <dl>
                  <dt>{t.surface}</dt><dd>{inputs.surface === 'unknown' ? t.unknown : t.exampleTitle}</dd>
                  <dt>{t.material}</dt><dd>{inputs.materials === 'unknown' ? t.unknown : t.materialTitle}</dd>
                </dl>
                {!supported && <p>{t.outsideScope}</p>}
                <div className="actions">
                  {supported && <button className="primary" type="button" disabled={!online || pending}
                    onClick={() => void run(async () => {
                      const result = await post('assess', { ...inputs, confirmed: true });
                      setDecision(result.data);
                      return result;
                    })}>{pending ? t.working : t.assess}</button>}
                  <button className="text-button" type="button" disabled={pending} onClick={() => {
                    reset();
                    document.getElementById('question')?.focus();
                  }}>{supported ? t.mismatch : t.edit}</button>
                </div>
              </section>
            )}
            {decision && <DecisionCard t={t} decision={decision} />}
            {failed && <p className="notice" role="alert">{t.error}</p>}
            <div className="catalog"><strong>{t.current}</strong><span>{t.exampleTitle}</span></div>
          </div>
          <Evidence key={requestId} t={t} decision={decision} requestId={requestId} interpretationId={interpretationId} />
        </div>
      </main>
    </>
  );
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<App />);
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
