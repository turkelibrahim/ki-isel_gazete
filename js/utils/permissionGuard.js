export function hasPermission(permissions = [], permission) { return Array.isArray(permissions) && permissions.includes(permission); }
export function requireAnyPermission(permissions = [], list = []) { return list.some((p) => hasPermission(permissions, p)); }
export function permissionLabel(permission = '') { return String(permission).replaceAll('_', ' ').replaceAll('.', ' › '); }
