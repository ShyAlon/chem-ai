import type { components } from './schema';
import type { Locale, Messages } from './i18n';

type Evidence = components['schemas']['EvidenceContext'];

export function RelatedEvidence({ evidence, locale, t }: { evidence?: Evidence | null; locale: Locale; t: Messages }) {
  if (!evidence) return null;
  return <section className="related-evidence" aria-label={t.relatedEvidence}>
    <h3>{t.relatedEvidence}</h3>
    <p>{evidence.message[locale]}</p>
    {(evidence.items ?? []).map(item => <article key={item.id}>
      <h4><a href={item.provenance.url} target="_blank" rel="noreferrer">{item.title[locale]}</a></h4>
      <p>{item.summary[locale]}</p>
      <small>{item.provenance.publisher} · {t['researchMode_' + item.provenance.mode]}</small>
    </article>)}
  </section>;
}
