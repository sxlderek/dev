"use strict";
// ---------------------------------------------------------------------------
// Structured error types for ISPConfig plugin
// ---------------------------------------------------------------------------
Object.defineProperty(exports, "__esModule", { value: true });
exports.ISPConfigError = void 0;
exports.classifyApiMessage = classifyApiMessage;
exports.normalizeError = normalizeError;
class ISPConfigError extends Error {
    code;
    retryable;
    statusCode;
    constructor(code, message, options) {
        super(message, { cause: options?.cause });
        this.name = "ISPConfigError";
        this.code = code;
        this.retryable = options?.retryable ?? false;
        this.statusCode = options?.statusCode;
    }
}
exports.ISPConfigError = ISPConfigError;
// ---------------------------------------------------------------------------
// Classify raw ISPConfig API error messages into error codes
// ---------------------------------------------------------------------------
const INVALID_METHOD_PATTERNS = [
    "invalid function",
    "unknown method",
    "method not found",
    "function not found",
    "not a valid method",
];
const PERMISSION_PATTERNS = [
    "permission denied",
    "access denied",
    "not allowed",
    "forbidden",
    "no permission",
    "not permitted",
    "authorization required",
];
const AUTH_PATTERNS = [
    "session",
    "login failed",
    "authentication",
    "auth failed",
    "invalid credentials",
    "expired",
    "no session",
];
function matchesAny(msg, patterns) {
    const lower = msg.toLowerCase();
    return patterns.some((p) => lower.includes(p));
}
function classifyApiMessage(message) {
    if (matchesAny(message, INVALID_METHOD_PATTERNS))
        return "invalid_method";
    if (matchesAny(message, PERMISSION_PATTERNS))
        return "permission_denied";
    if (matchesAny(message, AUTH_PATTERNS))
        return "auth_error";
    return "api_error";
}
// ---------------------------------------------------------------------------
// Normalize any thrown value into an ISPConfigError
// ---------------------------------------------------------------------------
function normalizeError(err) {
    if (err instanceof ISPConfigError)
        return err;
    const message = err instanceof Error ? err.message : String(err);
    const cause = err instanceof Error ? err : undefined;
    // Network / timeout
    if (message.includes("timeout") ||
        message.includes("ECONNREFUSED") ||
        message.includes("ECONNRESET") ||
        message.includes("ENOTFOUND") ||
        message.includes("socket hang up")) {
        return new ISPConfigError("network_error", message, {
            retryable: true,
            cause,
        });
    }
    // HTTP status errors from rawCall
    const httpMatch = message.match(/^ISPConfig HTTP (\d+)/);
    if (httpMatch) {
        const status = Number(httpMatch[1]);
        if (status === 401 || status === 403) {
            return new ISPConfigError(status === 401 ? "auth_error" : "permission_denied", message, { statusCode: status, retryable: status === 401, cause });
        }
        return new ISPConfigError("api_error", message, {
            statusCode: status,
            retryable: status >= 500,
            cause,
        });
    }
    // Non-JSON
    if (message.includes("non-JSON response")) {
        return new ISPConfigError("parse_error", message, { cause });
    }
    // ISPConfig API envelope errors
    if (message.startsWith("ISPConfig API ")) {
        const code = classifyApiMessage(message);
        return new ISPConfigError(code, message, {
            retryable: code === "auth_error",
            cause,
        });
    }
    // Login failure
    if (message.includes("login failed")) {
        return new ISPConfigError("auth_error", message, { cause });
    }
    // Validation errors (from validateParams or tool-level checks)
    if (message.includes("Validation failed") ||
        message.includes("Missing required") ||
        message.includes("must not be empty") ||
        message.includes("must be a valid number") ||
        message.includes("must be one of")) {
        return new ISPConfigError("validation_error", message, {
            statusCode: 400,
            cause,
        });
    }
    // Guard/policy errors
    if (message.includes("readOnly=true") || message.includes("blocked by allowedOperations")) {
        return new ISPConfigError("permission_denied", message, {
            statusCode: 403,
            cause,
        });
    }
    // Fallback
    return new ISPConfigError("api_error", message, { cause });
}
//# sourceMappingURL=errors.js.map