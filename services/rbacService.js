"use strict";

const crypto = require("crypto");

const PERMISSIONS = Object.freeze([
  "admin.access",
  "users.view", "users.create", "users.update", "users.delete", "users.manage_roles",
  "content.view", "content.create", "content.update", "content.delete", "content.publish", "content.set_editor_pick",
  "reports.view", "reports.export_excel", "reports.export_pdf", "reports.schedule", "reports.email",
  "analytics.view", "system_metrics.view", "audit_logs.view",
  "notifications.manage", "settings.manage",
  "profile.view_own", "profile.update_own", "dashboard.view_own", "recommendations.view_own"
]);

const ROLE_DEFINITIONS = Object.freeze({
  super_admin: {
    name: "Süper Admin",
    description: "Tüm sistem, rapor, RBAC ve audit log yetkilerine sahiptir.",
    permissions: [...PERMISSIONS]
  },
  content_editor: {
    name: "İçerik Editörü",
    description: "İçerik yönetimi ve sınırlı analitik erişimi olan editör rolüdür.",
    permissions: [
      "admin.access", "content.view", "content.create", "content.update", "content.delete", "content.publish", "content.set_editor_pick", "analytics.view"
    ]
  },
  standard_user: {
    name: "Standart Kullanıcı",
    description: "Kendi profil, dashboard ve öneri verilerine erişebilen normal kullanıcıdır.",
    permissions: ["profile.view_own", "profile.update_own", "dashboard.view_own", "recommendations.view_own"]
  }
});

function nowIso() { return new Date().toISOString(); }
function id(prefix) { return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(5).toString("hex")}`; }
function hash(value = "") { return crypto.createHash("sha256").update(String(value || "")).digest("hex"); }

function normalizeDb(db = {}) {
  db.roles = Array.isArray(db.roles) ? db.roles : [];
  db.permissions = Array.isArray(db.permissions) ? db.permissions : [];
  db.rolePermissions = Array.isArray(db.rolePermissions) ? db.rolePermissions : [];
  db.userRoles = Array.isArray(db.userRoles) ? db.userRoles : [];
  db.auditLogs = Array.isArray(db.auditLogs) ? db.auditLogs : (Array.isArray(db.auditLog) ? db.auditLog : []);

  for (const slug of PERMISSIONS) {
    if (!db.permissions.some((p) => p.slug === slug)) {
      db.permissions.push({ id: id("perm"), name: slug, slug, description: slug, created_at: nowIso(), updated_at: nowIso() });
    }
  }
  for (const [slug, def] of Object.entries(ROLE_DEFINITIONS)) {
    let role = db.roles.find((r) => r.slug === slug);
    if (!role) {
      role = { id: id("role"), name: def.name, slug, description: def.description, created_at: nowIso(), updated_at: nowIso() };
      db.roles.push(role);
    }
    for (const permissionSlug of def.permissions) {
      const perm = db.permissions.find((p) => p.slug === permissionSlug);
      if (perm && !db.rolePermissions.some((rp) => String(rp.role_id) === String(role.id) && String(rp.permission_id) === String(perm.id))) {
        db.rolePermissions.push({ id: id("roleperm"), role_id: role.id, permission_id: perm.id, created_at: nowIso() });
      }
    }
  }
  if (Array.isArray(db.users) && db.users.length) {
    const hasSuper = db.userRoles.some((ur) => {
      const role = db.roles.find((r) => String(r.id) === String(ur.role_id));
      return role?.slug === "super_admin";
    });
    const firstUser = db.users.find((u) => String(u.id) === "user_demo") || db.users[0];
    function seedRole(userId, slug) {
      const role = db.roles.find((r) => r.slug === slug) || db.roles.find((r) => r.slug === "standard_user");
      if (role && !db.userRoles.some((ur) => String(ur.user_id) === String(userId))) {
        db.userRoles.push({ id: id("userrole"), user_id: userId, role_id: role.id, assigned_by: "system", created_at: nowIso() });
      }
    }
    if (!hasSuper && firstUser) seedRole(firstUser.id, "super_admin");
    for (const user of db.users) {
      if (!db.userRoles.some((ur) => String(ur.user_id) === String(user.id))) seedRole(user.id, user.role || "standard_user");
    }
  }
  return db;
}

function roleBySlug(db, slug) {
  normalizeDb(db);
  return db.roles.find((r) => r.slug === slug) || null;
}

function permissionBySlug(db, slug) {
  normalizeDb(db);
  return db.permissions.find((p) => p.slug === slug) || null;
}

function getUserRoleSlugs(db, userId) {
  normalizeDb(db);
  const roleIds = db.userRoles.filter((ur) => String(ur.user_id) === String(userId)).map((ur) => String(ur.role_id));
  const roles = db.roles.filter((r) => roleIds.includes(String(r.id))).map((r) => r.slug);
  return roles.length ? roles : ["standard_user"];
}

function getUserPermissions(db, userId) {
  normalizeDb(db);
  const roles = new Set(getUserRoleSlugs(db, userId));
  if (roles.has("super_admin")) return [...PERMISSIONS];
  const roleIds = db.roles.filter((r) => roles.has(r.slug)).map((r) => String(r.id));
  const permIds = db.rolePermissions.filter((rp) => roleIds.includes(String(rp.role_id))).map((rp) => String(rp.permission_id));
  return [...new Set(db.permissions.filter((p) => permIds.includes(String(p.id))).map((p) => p.slug))];
}

function getCurrentUser(db, req) {
  normalizeDb(db);
  if (String(req?.headers?.["x-force-unauthenticated"] || "") === "1") return null;
  const idFromHeader = req?.headers?.["x-user-id"] || req?.headers?.["x-admin-user-id"] || req?.headers?.["x-demo-user-id"];
  let user = idFromHeader ? db.users.find((u) => String(u.id) === String(idFromHeader)) : null;
  if (!user && process.env.NODE_ENV !== "production") user = db.users.find((u) => String(u.id) === "user_demo") || db.users[0] || null;
  if (!user) return null;
  const roleSlugs = getUserRoleSlugs(db, user.id);
  return { ...user, role: roleSlugs[0], roles: roleSlugs, permissions: getUserPermissions(db, user.id) };
}

function makeHttpError(statusCode, message) {
  const error = new Error(message);
  error.statusCode = statusCode;
  return error;
}

function requirePermission(db, req, permission) {
  const user = getCurrentUser(db, req);
  if (!user) throw makeHttpError(401, "Oturum açmanız gerekiyor.");
  if (!user.permissions.includes(permission)) throw makeHttpError(403, "Bu işlem için yetkiniz yok.");
  return user;
}

function listUsersWithRoles(db) {
  normalizeDb(db);
  return (db.users || []).map((user) => ({
    id: user.id,
    name: user.name || user.username || user.email || user.id,
    email: user.email || "",
    roles: getUserRoleSlugs(db, user.id),
    permissions: getUserPermissions(db, user.id)
  }));
}

function countSuperAdmins(db) {
  normalizeDb(db);
  return db.userRoles.filter((ur) => {
    const role = db.roles.find((r) => String(r.id) === String(ur.role_id));
    return role?.slug === "super_admin";
  }).length;
}

function assignRole(db, userId, roleSlug, { actorUserId = "system", skipAudit = false } = {}) {
  normalizeDb(db);
  const role = roleBySlug(db, roleSlug);
  if (!role) throw makeHttpError(422, "Geçersiz rol.");
  const user = (db.users || []).find((u) => String(u.id) === String(userId));
  if (!user) throw makeHttpError(404, "Kullanıcı bulunamadı.");
  const oldRoles = getUserRoleSlugs(db, userId);
  if (oldRoles.includes("super_admin") && roleSlug !== "super_admin" && countSuperAdmins(db) <= 1) {
    throw makeHttpError(409, "Sistemde en az bir Süper Admin kalmalıdır.");
  }
  db.userRoles = db.userRoles.filter((ur) => String(ur.user_id) !== String(userId));
  db.userRoles.push({ id: id("userrole"), user_id: userId, role_id: role.id, assigned_by: actorUserId, created_at: nowIso() });
  user.role = roleSlug;
  if (!skipAudit) {
    createAuditLog(db, {
      actor_user_id: actorUserId,
      action: "user.role.updated",
      target_type: "user",
      target_id: userId,
      old_value_json: { roles: oldRoles },
      new_value_json: { roles: [roleSlug] }
    });
  }
  return { user_id: userId, old_roles: oldRoles, new_roles: [roleSlug] };
}

function createAuditLog(db, entry = {}, req = null) {
  normalizeDb(db);
  const ip = req?.headers?.["x-forwarded-for"] || req?.socket?.remoteAddress || "";
  const record = {
    id: id("audit"),
    actor_user_id: entry.actor_user_id || entry.actorUserId || "system",
    action: entry.action || "unknown",
    target_type: entry.target_type || entry.targetType || "system",
    target_id: entry.target_id || entry.targetId || "",
    old_value_json: entry.old_value_json || entry.oldValue || null,
    new_value_json: entry.new_value_json || entry.newValue || null,
    ip_hash: ip ? hash(ip) : "",
    user_agent: String(req?.headers?.["user-agent"] || "").slice(0, 240),
    created_at: nowIso()
  };
  db.auditLogs.push(record);
  db.auditLog = db.auditLogs;
  return record;
}

module.exports = {
  PERMISSIONS,
  ROLE_DEFINITIONS,
  normalizeDb,
  getCurrentUser,
  getUserPermissions,
  getUserRoleSlugs,
  listUsersWithRoles,
  requirePermission,
  assignRole,
  createAuditLog,
  hash,
  nowIso
};
