import { ALLOWED_CATEGORIES } from "../services/adminApi";

type Props = { value: string[]; onChange: (labels: string[]) => void };

export function CategorySelector({ value, onChange }: Props) {
  function toggle(label: string) {
    onChange(value.includes(label) ? value.filter((item) => item !== label) : [...value, label]);
  }
  return <div className="admin-category-selector">{ALLOWED_CATEGORIES.map((label) => <button key={label} type="button" className={value.includes(label) ? "selected" : ""} onClick={() => toggle(label)}>{label}</button>)}</div>;
}
