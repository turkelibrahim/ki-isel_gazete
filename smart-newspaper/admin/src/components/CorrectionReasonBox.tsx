type Props = { value: string; onChange: (value: string) => void };

export function CorrectionReasonBox({ value, onChange }: Props) {
  return <textarea value={value} onChange={(event) => onChange(event.target.value)} maxLength={1000} placeholder="Düzeltme nedeni" />;
}
