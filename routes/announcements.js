"use strict";

const AnnouncementService = require("../services/announcementService");

function apiError(json, res, error) {
  return json(res, error.statusCode || 500, { success: false, message: error.message || "Duyuru işlemi başarısız oldu." });
}

async function handleAnnouncementsRoute(req, res, url, helpers = {}) {
  if (!url.pathname.startsWith("/api/announcements")) return false;
  const { readBody, json, db, writeDb } = helpers;
  AnnouncementService.normalizeDb(db);

  try {
    if (req.method === "GET" && url.pathname === "/api/announcements") {
      return json(res, 200, { success: true, count: AnnouncementService.listAnnouncements(db).length, data: AnnouncementService.listAnnouncements(db) });
    }

    if (req.method === "POST" && url.pathname === "/api/announcements") {
      const body = await readBody(req);
      const result = AnnouncementService.createAnnouncement(db, body || {}, { adminId: "admin" });
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 201, result);
    }

    const match = url.pathname.match(/^\/api\/announcements\/([^/]+)$/);
    if (match && req.method === "PATCH") {
      const body = await readBody(req);
      const result = AnnouncementService.updateAnnouncement(db, decodeURIComponent(match[1]), body || {});
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 200, result);
    }

    if (match && req.method === "DELETE") {
      const result = AnnouncementService.deleteAnnouncement(db, decodeURIComponent(match[1]));
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 200, result);
    }

    return false;
  } catch (error) {
    return apiError(json, res, error);
  }
}

module.exports = { handleAnnouncementsRoute };
