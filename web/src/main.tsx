import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { post, getJSON, RequestError } from './api';
import { ChemistryBackdrop } from './ChemistryBackdrop';
import { HowItWorks } from './HowItWorks';
import type { components } from './schema';
import { DecisionCard, Evidence, LanguageSwitch } from './components';
import { applyLocale, initialLocale } from './i18n';
import './style.css';
import { UseCaseWorkspace } from './UseCases';
import { Management } from './Management';
import { ActivityTimeline } from './ActivityTimeline';
import { Research } from './Research';
import { QuestionHints } from './QuestionHints';
import { InputFields } from './InputFields';

const guidePath = '/how-it-works';
const showManagement = window.location.pathname.replace(/\/$/, '') === '/management';
const showGuide = window.location.pathname.replace(/\/$/, '') === guidePath;
const defaultLocale = initialLocale();
applyLocale(defaultLocale);

type ApplicationCatalog = components['schemas']['ApplicationCatalog'];

function App({ catalog }: { catalog: ApplicationCatalog }) {
  const [locale, setLocale] = useState(defaultLocale);
  const [workspace, setWorkspace] = useState('cleaning');
  const [text, setText] = useState('');
  const [inputs, setInputs] = useState<components['schemas']['InterpretResult'] | null>(null);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [decision, setDecision] = useState<components['schemas']['Decision'] | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [interpretationId, setInterpretationId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [retrySeconds, setRetrySeconds] = useState(0);
  const [online, setOnline] = useState(navigator.onLine);
  const t = catalog.messages[locale];
  const useCases = catalog.scenarios;
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    document.title = `HomeChem · ${showGuide ? catalog.guide[locale].title : t.workspace}`;
  }, [locale]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  useEffect(() => {
    if (!retrySeconds) return;
    const timer = window.setTimeout(() => setRetrySeconds(retrySeconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);


  function reset() {
    setChecks({});
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
      const retry = error instanceof RequestError ? error.retryAfter : undefined;
      if (retry) setRetrySeconds(retry);
      else setFailed(true);
    } finally {
      setPending(false);
    }
  }

  const review = inputs?.presentation?.[locale];
  const supported = Boolean(review?.assessment);
  return (
    <>
      <ChemistryBackdrop scroller={main} />
      <header className="site-header">
        <a href="/" className="brand"><img src="/icon.svg" alt="" width="36" height="36" /><bdi>HomeChem</bdi></a>
        <div className="header-actions">
          <nav aria-label={t.navigation}><a className="guide-link" href="/management" aria-current={showManagement ? 'page' : undefined}>{t.management}</a> <a className="guide-link" href={guidePath} aria-current={showGuide ? 'page' : undefined}>{t.guideLink}</a></nav>
          <LanguageSwitch locale={locale} choose={next => { applyLocale(next); setLocale(next); }} t={t} />
        </div>
      </header>
      <main ref={main}>
        {showManagement ? <Management locale={locale} messages={catalog.management_messages} /> : showGuide ? <HowItWorks guide={catalog.guide[locale]} /> : (
          <>
            <section className="hero">
              <div className="eyebrow">{t.workspace}</div>
              <h1>{workspace === 'research' ? t.researchTitle : workspace === 'cleaning' ? <>{t.heading} <em>{t.headingAccent}</em></> : useCases.find(item => item.id === workspace)?.title[locale]}</h1>
              <p>{workspace === 'cleaning' ? t.intro : t.scenarioIntro}</p>
            </section>
            {!online && <p className="notice" role="status">{t.offline}</p>}
            <nav className="use-case-nav" aria-label={t.useCases}>
              <button type="button" aria-pressed={workspace === 'cleaning'} onClick={() => setWorkspace('cleaning')}>{t.cleaning}</button>
              <button type="button" aria-pressed={workspace === 'research'} onClick={() => setWorkspace('research')}>{t.researchTitle}</button>
              {useCases.map(item => <button type="button" key={item.id} aria-pressed={workspace === item.id}
                onClick={() => setWorkspace(item.id)}>{item.title[locale]}</button>)}
            </nav>
            {workspace === 'research' ? <Research locale={locale} t={t} /> : workspace !== 'cleaning' ? <UseCaseWorkspace key={workspace + locale} entry={useCases.find(item => item.id === workspace)!} locale={locale} t={t} /> : <div className="layout">
              <div className="panel notebook" aria-busy={pending}>
                <form onSubmit={event => { event.preventDefault(); if (!online || pending || retrySeconds || inputs || !text.trim()) return;
                  void run(async () => {
                    const result = await post('interpret', { text: text.trim() }, text);
                    setInputs(result.data);
                    setInterpretationId(result.requestId);
                    return result;
                  }); }}>
                  <label htmlFor="question">{t.prompt}</label>
                  <QuestionHints key={locale} text={text} disabled={pending || Boolean(inputs)} label={t.hintLabel} locale={locale}
                    choose={hint => { reset(); setText(hint); }}>
                    {hints => <textarea aria-autocomplete="list" aria-controls={hints.expanded ? 'question-hints' : undefined}
                      aria-activedescendant={hints.activeId} id="question" dir="auto" value={text} maxLength={1000} rows={4} enterKeyHint="go"
                    required disabled={pending} placeholder={t.placeholder}
                    onChange={event => { reset(); setText(event.target.value); }}
                    onKeyDown={event => {
                      if (hints.onKeyDown(event)) return;
                      if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
                      event.preventDefault();
                      const question = event.currentTarget;
                      if (event.ctrlKey) {
                        const { value, maxLength, selectionStart, selectionEnd } = question;
                        if (value.length - (selectionEnd - selectionStart) >= maxLength) return;
                        question.setRangeText('\n', selectionStart, selectionEnd, 'end');
                        reset();
                        setText(question.value);
                      } else if (!event.repeat) {
                        question.form?.requestSubmit();
                      }
                    }} />}
                  </QuestionHints>
                  <div className="actions">
                    <button className="primary" disabled={!online || pending || retrySeconds > 0 || !text.trim() || Boolean(inputs)}>{pending && !inputs ? t.working : t.inspect}</button>
                    <button className="text-button" type="button" disabled={pending} onClick={() => {
                      reset();
                      setText(catalog.example_text[locale]);
                      document.getElementById('question')?.focus();
                    }}>{t.example}</button>
                  </div>
                </form>
                {inputs && !decision && (
                  <section className="confirmation" aria-labelledby="confirm-title">
                    <h2 id="confirm-title">{supported ? t.confirm : t.unverified}</h2>
                    <dl>
                      {review?.fields.map(field => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}
                    </dl>
                    {review?.confirmation && <p>{review.confirmation}</p>}
                    {inputs.context_id && (review?.questions ?? []).length > 0 && <form className="clarification-form" onSubmit={event => {
                      event.preventDefault();
                      const answers = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
                      void run(async () => {
                        const result = await post('clarify', { context_id: inputs.context_id!, answers }, text);
                        setInputs(result.data); setChecks({}); setInterpretationId(result.requestId);
                        return result;
                      });
                    }}>
                      <InputFields fields={review!.questions!} prefix="clarification" locale={locale} disabled={pending} />
                      <button className="primary" disabled={pending}>{pending ? t.working : t.clarify}</button>
                    </form>}
                    {supported && (review?.checks ?? []).map(check => <label key={check.id} className="procedure-check">
                      <input type="checkbox" checked={Boolean(checks[check.id])} disabled={pending}
                        onChange={event => setChecks(values => ({ ...values, [check.id]: event.target.checked }))} />
                      <span>{check.label}</span>
                    </label>)}
                    <div className="actions">
                      {supported && review && <button className="primary" type="button" disabled={!online || pending || (review.checks ?? []).some(check => !checks[check.id])}
                        onClick={() => void run(async () => {
                          const result = await post('assess', {
                            ...review.assessment!,
                            checks,
                          }, text);
                          setDecision(result.data);
                          return result;
                        })}>{pending ? t.working : review.accept}</button>}
                      <button className="text-button" type="button" disabled={pending} onClick={() => {
                        reset();
                        document.getElementById('question')?.focus();
                      }}>{supported ? t.mismatch : t.edit}</button>
                    </div>
                  </section>
                )}
                {decision && <DecisionCard t={t} decision={decision} locale={locale} />}
                {retrySeconds > 0 && <p className="notice" role="status">{t.rateLimited.replace('{seconds}', String(retrySeconds))}</p>}
                {failed && <p className="notice" role="alert">{t.error}</p>}
              </div>
              <Evidence key={requestId} t={t} locale={locale} related={decision?.evidence ?? inputs?.evidence} decision={decision} requestId={requestId} interpretationId={interpretationId} />
            </div>}
          </>
        )}
        <ActivityTimeline t={t} />
      </main>
      <footer className="site-footer">
        <strong>{t.current}</strong><span>{catalog.procedures.map(option => option[locale].title).join(' · ')}</span>
      </footer>
    </>
  );
}

const root = document.getElementById('root');
function CatalogLoader() {
  const [catalog, setCatalog] = useState<ApplicationCatalog | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setFailed(false);
    getJSON<ApplicationCatalog>('/api/catalog', controller.signal)
      .then(setCatalog).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [attempt]);
  if (catalog) return <App catalog={catalog} />;
  return <main><section className="panel" role={failed ? 'alert' : 'status'}>
    <p>{failed ? 'Catalog unavailable / הקטלוג אינו זמין' : 'Loading / טוען…'}</p>
    {failed && <button type="button" onClick={() => setAttempt(value => value + 1)}>Retry / נסו שוב</button>}
  </section></main>;
}
if (root) createRoot(root).render(<CatalogLoader />);
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
