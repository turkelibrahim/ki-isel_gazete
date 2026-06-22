import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ReportService from '../../services/reportService.js';
import RbacService from '../../services/rbacService.js';
import ScheduledReportService from '../../services/scheduledReportService.js';

function dbFixture() {
  return {
    users: [{ id: 'user_demo', name: 'Demo', email: 'demo@example.com' }, { id: 'editor_1', name: 'Editor' }, { id: 'user_2', name: 'User' }],
    articles: [
      { id: 'a1', title: 'Ekonomi haberi', category: 'Ekonomi', source_name: 'Sabah', published_at: new Date().toISOString(), view_count: 7, share_count: 2 },
      { id: 'a2', title: 'Spor haberi', category: 'Spor', source_name: 'TRT Haber', published_at: new Date().toISOString(), view_count: 3, share_count: 1 }
    ],
    userInteractions: [
      { user_id: 'u1', anonymous_id: '', news_id: 'a1', category: 'Ekonomi', source_name: 'Sabah', interaction_type: 'read', duration_seconds: 65, created_at: new Date().toISOString() },
      { user_id: 'u2', anonymous_id: '', news_id: 'a1', category: 'Ekonomi', source_name: 'Sabah', interaction_type: 'view', duration_seconds: 0, created_at: new Date().toISOString() },
      { user_id: 'u2', anonymous_id: '', news_id: 'a2', category: 'Spor', source_name: 'TRT Haber', interaction_type: 'share', duration_seconds: 0, created_at: new Date().toISOString() }
    ]
  };
}

test('RBAC default roles and super admin permissions are seeded', () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  assert.ok(db.roles.some(r => r.slug === 'super_admin'));
  assert.ok(RbacService.getUserPermissions(db, 'user_demo').includes('reports.export_excel'));
});

test('content editor cannot export admin reports', () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  RbacService.assignRole(db, 'editor_1', 'content_editor', { actorUserId: 'user_demo' });
  const req = { headers: { 'x-user-id': 'editor_1' } };
  assert.throws(() => RbacService.requirePermission(db, req, 'reports.export_excel'), /yetkiniz yok/i);
});

test('last super admin role cannot be downgraded', () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  assert.throws(() => RbacService.assignRole(db, 'user_demo', 'standard_user', { actorUserId: 'user_demo' }), /Süper Admin/);
});

test('usage report calculates active users top news and category traffic', () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  const data = ReportService.collectReportData(db, 'full_admin_report', '2026-01-01', '2099-01-01');
  assert.equal(data.summary.daily_active_users, 2);
  assert.equal(data.top_news[0].news_id, 'a1');
  assert.ok(data.category_traffic.some(c => c.category === 'Ekonomi'));
});

test('Excel and PDF report exports write files and audit logs', () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  const req = { headers: { 'x-user-id': 'user_demo' }, socket: {} };
  const excel = ReportService.generateUsageReport(db, { reportType: 'full_admin_report', startDate: '2026-01-01', endDate: '2099-01-01', format: 'excel', req });
  assert.equal(excel.report.status, 'success');
  assert.ok(excel.report.file_url.endsWith('.xlsx'));
  const pdf = ReportService.generateUsageReport(db, { reportType: 'full_admin_report', startDate: '2026-01-01', endDate: '2099-01-01', format: 'pdf', req });
  assert.ok(pdf.report.file_url.endsWith('.pdf'));
  assert.ok(db.auditLogs.length >= 2);
});

test('scheduled report next run and due execution work', async () => {
  const db = dbFixture();
  RbacService.normalizeDb(db);
  const sched = ScheduledReportService.upsertScheduledReport(db, { frequency: 'daily', scheduled_time: '00:00', format: 'excel', recipients: [] }, { id: 'user_demo' });
  sched.next_run_at = new Date(Date.now() - 1000).toISOString();
  const result = await ScheduledReportService.runDueScheduledReports(db, { now: new Date() });
  assert.equal(result.length, 1);
  assert.ok(db.generatedReports.some(r => r.scheduled_report_id === sched.id));
  assert.ok(new Date(sched.next_run_at) > new Date(Date.now() - 1000));
});
