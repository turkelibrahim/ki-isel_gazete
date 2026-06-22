"use strict";

// Lightweight route contract for the monolithic Node server integration.
// Actual handler is wired in server.js so existing auth/session helpers remain unchanged.
module.exports = {
  prefix: "/api/feedback",
  endpoints: ["POST /api/feedback", "GET /api/feedback/my", "GET /api/feedback/my/:id"]
};
