import type { components } from './schema';

export function HowItWorks({ guide: t }: { guide: components['schemas']['GuideView'] }) {
  return (
    <article className="guide-page">
      <header className="hero guide-hero">
        <h1>{t.title}</h1>
        <p>{t.intro}</p>
      </header>
      <div className="layout guide-layout">
        <ol className="panel guide-steps">
          {t.steps.map(step => (
            <li key={step.title}>
              <h2>{step.title}</h2>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
        <aside className="panel evidence guide-example" aria-labelledby="guide-example-title">
          <h2 id="guide-example-title">{t.exampleTitle}</h2>
          <blockquote>{t.question}</blockquote>
          <dl>
            {t.fields.map(([label, value]) => (
              <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
          <p>{t.exampleResult}</p>
        </aside>
      </div>
      <a href="/" className="text-button guide-back">{t.back}</a>
    </article>
  );
}
