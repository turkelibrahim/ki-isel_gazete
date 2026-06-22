"use strict";
const RbacService = require("../services/rbacService");
function apiError(json, res, error) { return json(res, error.statusCode || 500, { success: false, message: error.message || "Yetki işlemi başarısız oldu." }); }
async function handleAdminRolesRoute(req, res, url, helpers = {}) {
  const { readBody, json, db, writeDb } = helpers;
  RbacService.normalizeDb(db);
  try {
    if (req.method === "GET" && url.pathname === "/api/auth/me/permissions") {
      const user = RbacService.getCurrentUser(db, req);
      if (!user) return json(res, 401, { success: false, message: "Oturum açmanız gerekiyor." });
      return json(res, 200, { success: true, data: { user: { id: user.id, name: user.name || user.email || user.id, email: user.email || "" }, roles: user.roles, permissions: user.permissions } });
    }
    if (!url.pathname.startsWith("/api/admin/roles") && !url.pathname.startsWith("/api/admin/permissions") && !url.pathname.startsWith("/api/admin/users") && !url.pathname.startsWith("/api/admin/audit-logs")) return false;
    if (req.method === "GET" && url.pathname === "/api/admin/roles") {
      RbacService.requirePermission(db, req, "admin.access");
      return json(res, 200, { success: true, count: db.roles.length, data: db.roles });
    }
    if (req.method === "GET" && url.pathname === "/api/admin/permissions") {
      RbacService.requirePermission(db, req, "users.manage_roles");
      return json(res, 200, { success: true, count: db.permissions.length, data: db.permissions });
    }
    if (req.method === "GET" && url.pathname === "/api/admin/users") {
      RbacService.requirePermission(db, req, "users.view");
      const usersList = RbacService.listUsersWithRoles(db).map(u => {
        const originalUser = db.users.find(du => du.id === u.id) || {};
        return {
          ...u,
          role: u.roles[0] || "user",
          createdAt: originalUser.createdAt || new Date().toISOString(),
          interests: db.preferences?.[u.id]?.interests || [],
          bookmarkCount: (db.bookmarks || []).filter(b => b.userId === u.id).length
        };
      });
      return json(res, 200, { success: true, count: usersList.length, data: usersList, users: usersList });
    }
    const roleMatch = url.pathname.match(/^\/api\/admin\/users\/([^/]+)\/role$/);
    if (roleMatch && req.method === "PATCH") {
      const actor = RbacService.requirePermission(db, req, "users.manage_roles");
      const body = await readBody(req).catch(() => ({}));
      const result = RbacService.assignRole(db, decodeURIComponent(roleMatch[1]), body.role || body.role_slug || body.roleSlug, { actorUserId: actor.id });
      writeDb?.(db);
      return json(res, 200, { success: true, message: "Kullanıcı rolü başarıyla güncellendi.", data: result });
    }
    if (req.method === "GET" && url.pathname === "/api/admin/audit-logs") {
      RbacService.requirePermission(db, req, "audit_logs.view");
      return json(res, 200, { success: true, count: db.auditLogs.length, data: [...db.auditLogs].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 200) });
    }
    return false;
  } catch (error) { return apiError(json, res, error); }
}
module.exports = { handleAdminRolesRoute };
