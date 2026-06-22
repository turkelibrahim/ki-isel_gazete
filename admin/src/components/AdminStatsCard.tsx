export function AdminStatsCard({ title, value }: { title: string; value: string | number }) {
  return <div className="admin-stats-card"><span>{title}</span><strong>{value}</strong></div>;
}
