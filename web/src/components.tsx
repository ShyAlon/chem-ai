import { useState } from 'react';
import { RelatedEvidence } from './RelatedEvidence';
import type { Locale, Messages } from './i18n';
import type { components } from './schema';

type Decision = components['schemas']['Decision'];

export function LanguageSwitch({ locale, choose, t }: { locale: Locale; choose: (locale: Locale) => void; t: Messages }) {
  return (
    <div className="languages" role="group" aria-label={t.language}>
      <button type="button" lang="en" aria-pressed={locale === 'en'} onClick={() => choose('en')}>EN</button>
      <button type="button" lang="he" aria-pressed={locale === 'he'} onClick={() => choose('he')}>עברית</button>
    </div>
  );
}

export function Evidence({ t, decision, requestId, interpretationId, related, locale }: {
  related?: components['schemas']['EvidenceContext'] | null;
  locale: Locale;
  t: Messages;
  decision: Decision | null;
  requestId: string | null;
  interpretationId: string | null;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <aside className="evidence panel" aria-labelledby="evidence-title">
      <div className="eyebrow">{t.scope}</div>
      <h2 id="evidence-title">{t.evidence}</h2>
      {decision ? (
        <>
          {decision.source && <p><a href={decision.source.url} lang={decision.source.language}>{decision.source.title}</a><br /><small>{t.sourceLanguage}</small></p>}
          {decision.chemistry_source && <p><a href={decision.chemistry_source.url} lang={decision.chemistry_source.language}>{decision.chemistry_source.title}</a></p>}
          <dl>
            <dt>{t.rule}</dt><dd><bdi>{decision.rule}</bdi></dd>
            <dt>{t.version}</dt><dd><bdi>{decision.version}</bdi></dd>
          </dl>
        </>
      ) : !related && <p>{t.emptyEvidence}</p>}
      <RelatedEvidence evidence={related} locale={locale} t={t} />
      {requestId && (
        <div className="request">
          <small>{t.request}</small><code dir="ltr">{requestId}</code>
          {navigator.clipboard && <button className="text-button" type="button" onClick={async () => {
            try {
              await navigator.clipboard.writeText(requestId);
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}>{copied ? t.copied : t.copy}</button>}
        </div>
      )}
      {interpretationId && interpretationId !== requestId && (
        <div className="request">
          <small>{t.interpretation}</small><code dir="ltr">{interpretationId}</code>
        </div>
      )}
    </aside>
  );
}

export function DecisionCard({ t, decision, locale }: { t: Messages; decision: Decision; locale: Locale }) {
  const procedure = decision.procedure?.[locale];
  return (
    <section className={`decision ${decision.status}`} aria-live="polite">
      <h2>{procedure ? t.approved : t.unverified}</h2>
      {procedure && <>
        <ol>{procedure.steps.map(step => <li key={step}>{step}</li>)}</ol>
        <h3>{t.whyTitle}</h3><p>{procedure.why}</p>
      </>}
    </section>
  );
}
