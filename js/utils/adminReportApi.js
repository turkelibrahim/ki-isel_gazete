export async function fetchPermissions() {
  const res = await fetch('/api/auth/me/permissions');
  return res.json();
}
export async function fetchUsageReport(filters = {}) {
  const params = new URLSearchParams();
  if (filters.reportType) params.set('reportType', filters.reportType);
  if (filters.startDate) params.set('startDate', filters.startDate);
  if (filters.endDate) params.set('endDate', filters.endDate);
  const res = await fetch(`/api/admin/reports/usage?${params.toString()}`);
  return res.json();
}
export async function exportReport(format, payload = {}) {
  const res = await fetch(`/api/admin/reports/export/${format}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  return res.json();
}
export async function fetchGeneratedReports() { const res = await fetch('/api/admin/reports/generated'); return res.json(); }
export async function fetchRoles() { const res = await fetch('/api/admin/roles'); return res.json(); }
export async function fetchUsers() { const res = await fetch('/api/admin/users'); return res.json(); }
export async function updateUserRole(userId, role) { const res = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/role`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) }); return res.json(); }
export async function fetchAuditLogs() { const res = await fetch('/api/admin/audit-logs'); return res.json(); }
