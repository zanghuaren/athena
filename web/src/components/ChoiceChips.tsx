import styles from './Field.module.css';

type Option<T> = { value: T; label: string };

type Props<T> = {
  label: string;
  options: Option<T>[];
  value: T[];
  onChange: (value: T[]) => void;
  multiple?: boolean;
  error?: string;
};

/** 原型里的 chips：单选时点击即替换，多选时点击切换。 */
export function ChoiceChips<T extends string | number>({
  label,
  options,
  value,
  onChange,
  multiple = false,
  error,
}: Props<T>) {
  function toggle(v: T) {
    if (!multiple) onChange([v]);
    else onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  }

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.label}>{label}</legend>
      <div className={styles.chips}>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            className={styles.chip}
            aria-pressed={value.includes(o.value)}
            onClick={() => toggle(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {error && <p className={styles.error}>{error}</p>}
    </fieldset>
  );
}
