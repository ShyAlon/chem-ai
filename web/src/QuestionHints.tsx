import { useEffect, useState } from 'react';
import { getJSON } from './api';

type Props = {
  text: string;
  disabled: boolean;
  label: string;
  locale: string;
  children: (options: {
    expanded: boolean;
    activeId?: string;
    onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  }) => React.ReactNode;
  choose: (text: string) => void;
};

export function QuestionHints({ text, disabled, label, locale, children, choose }: Props) {
  const [active, setActive] = useState(-1);
  const [dismissed, setDismissed] = useState(false);
  const [matches, setMatches] = useState<string[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    setMatches([]);
    setActive(-1);
    const timer = window.setTimeout(() => {
      getJSON<string[]>('/api/hints?' + new URLSearchParams({ text, locale }), controller.signal)
        .then(setMatches).catch(() => {});
    }, 150);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [text, locale]);
  const expanded = !disabled && !dismissed && matches.length > 0;

  function accept(hint: string) {
    choose(hint);
    setActive(-1);
    setDismissed(true);
    document.getElementById('question')?.focus();
  }

  return <div className="question-hints" onInput={() => { setDismissed(false); setActive(-1); }}>
    {children({ expanded, activeId: expanded && active >= 0 ? `question-hint-${active}` : undefined,
      onKeyDown: event => {
        if (event.nativeEvent.isComposing) return false;
        if (event.key === 'Escape') { setDismissed(true); setActive(-1); return false; }
        if (!expanded || event.ctrlKey || event.metaKey || event.altKey) return false;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          setActive(index => event.key === 'ArrowDown' ? (index + 1) % matches.length : (index <= 0 ? matches.length : index) - 1);
          return true;
        }
        if ((event.key === 'Enter' || event.key === 'Tab') && active >= 0) {
          event.preventDefault();
          accept(matches[active]);
          return true;
        }
        return false;
      } })}
    {expanded && <div className="hint-panel">
      <p id="question-hints-label">{label}</p>
      <div id="question-hints" role="listbox" aria-labelledby="question-hints-label">
        {matches.map((hint, index) => <button key={hint} id={`question-hint-${index}`} type="button" role="option"
          aria-selected={index === active} onMouseDown={event => event.preventDefault()} onClick={() => accept(hint)}>{hint}</button>)}
      </div>
    </div>}
  </div>;
}
