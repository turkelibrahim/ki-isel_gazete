"use strict";

module.exports = {
  prefix: "/api/admin/feedback",
  endpoints: [
    "GET /api/admin/feedback",
    "GET /api/admin/feedback/:id",
    "PATCH /api/admin/feedback/:id/status",
    "POST /api/admin/feedback/:id/reply",
    "PATCH /api/admin/feedback/:id/archive"
  ]
};
