import { useEffect, useState } from 'react';
import { getJSON } from './api';
import { downloadBlob } from './download';
import type { Messages } from './i18n';
import type { components } from './schema';

type Trace = components['schemas']['ActivityTrace'];
type Selection = { key: string; requestedKey: string; running: boolean };

export function ActivityTimeline({ t }: { t: Messages }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [open, setOpen] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(false);

  useEffect(() => {
    const receive = (event: Event) => {
      const detail = (event as CustomEvent<Selection>).detail;
      setSelection(current => detail.running || current?.requestedKey === detail.requestedKey ? detail : current);
      if (detail.running) { setTrace(null); setUnavailable(false); setDownloadError(false); }
    };
    window.addEventListener('homechem.activity', receive);
    return () => window.removeEventListener('homechem.activity', receive);
  }, []);

  useEffect(() => {
    if (!selection) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const poll = async () => {
      try {
        const result = await getJSON<Trace>(`/api/activities/${selection.key}`, controller.signal);
        if (!controller.signal.aborted) { setTrace(result); setUnavailable(false); }
      } catch {
        if (!selection.running && !controller.signal.aborted) setUnavailable(true);
      }
      if (selection.running && !controller.signal.aborted) timer = window.setTimeout(poll, 450);
    };
    void poll();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [selection]);

  async function download() {
    if (!selection || !trace) return;
    setDownloading(true); setDownloadError(false);
    try {
      const response = await fetch(`/api/activities/${selection.key}/download`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Download unavailable');
      downloadBlob(`homechem-debug-${trace.request_id}.zip`, await response.blob());
    } catch { setDownloadError(true); }
    finally { setDownloading(false); }
  }

  if (!selection) return null;
  const running = selection.running;
  return <aside className="activity-panel" aria-label={t.activityTitle}>
    <button type="button" className="activity-toggle" aria-expanded={open} aria-controls="activity-details" onClick={() => setOpen(value => !value)}>
      <span className={running ? 'activity-beacon running' : 'activity-beacon'} />
      <strong>{t.activityTitle}</strong>
      <span className="activity-summary">{running ? t.activityRunning : trace ? `${trace.activities.length} · ${trace.duration_ms.toFixed(0)} ms` : '—'}</span>
      <span aria-hidden="true">{open ? '−' : '+'}</span>
    </button>
    {open && <div id="activity-details" className="activity-details">
      {unavailable && <p>{t.activityUnavailable}</p>}
      {!trace?.activities.length && <p>{running ? t.activityWaiting : t.activityNoSteps}</p>}
      <ol className="activity-track">
        {trace?.activities.map(step => <li key={step.id} className={`activity-step ${step.status}`}>
          <span className="activity-node" aria-hidden="true">{step.status === 'running' ? '◌' : step.status === 'error' ? '!' : '✓'}</span>
          <details>
            <summary><span className="activity-kind">{t['activityKind_' + step.kind] ?? step.kind}</span>
              <bdi>{step.name}</bdi><small>{step.status === 'running' ? t.activityRunning : `${step.duration_ms.toFixed(1)} ms`}</small>
            </summary>
            <dl>{Object.entries(step.details ?? {}).map(([key, value]) => <div key={key}><dt><bdi>{key}</bdi></dt><dd><bdi>{String(value ?? '—')}</bdi></dd></div>)}</dl>
            {Object.keys(step.debug ?? {}).length > 0 && <pre dir="ltr">{JSON.stringify(step.debug, null, 2)}</pre>}
          </details>
        </li>)}
      </ol>
      {trace && <div className="activity-correlation"><small>{t.request}</small><code dir="ltr">{trace.request_id}</code>
        {trace.trace_id && <><small>{t.activityTraceId}</small><code dir="ltr">{trace.trace_id}</code></>}
      </div>}
    </div>}
    <div className="activity-download">
      {downloadError && <small role="alert" dir="auto">{t.activityDownloadError}</small>}
      <button type="button" dir="auto" onClick={() => void download()} disabled={running || !trace || downloading}>
        <span aria-hidden="true">⇩ </span>{downloading ? t.activityDownloading : t.activityDownload}
      </button>
    </div>
  </aside>;
}
