"use strict";

function isAdminUser(user, users = []) {
  if (!user) return false;
  const role = String(user.role || "").toLowerCase();
  return role === "admin" || role === "administrator" || users.indexOf(user) === 0;
}

module.exports = { isAdminUser };
