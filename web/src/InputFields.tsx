import type { Locale } from './i18n';
import type { components } from './schema';

type Field = components['schemas']['InputField'];

export function InputFields({ fields, prefix, locale, disabled }: {
  fields: Field[];
  prefix: string;
  locale: Locale;
  disabled: boolean;
}) {
  return <>{fields.map(field => {
    const id = `${prefix}-${field.id}`;
    return <label key={field.id} htmlFor={id}>
      {field.label[locale]}
      {field.kind === 'select' ? <select id={id} name={field.id} required={field.required ?? true} disabled={disabled}>
        {(field.options ?? []).map(option => <option key={option.id} value={option.id}>{option.label[locale]}</option>)}
      </select> : <input id={id} name={field.id} type={field.kind} min={field.minimum ?? undefined}
        max={field.maximum ?? undefined} maxLength={field.max_length ?? undefined}
        step={field.kind === 'number' ? 'any' : undefined} required={field.required ?? true} disabled={disabled} />}
    </label>;
  })}</>;
}
