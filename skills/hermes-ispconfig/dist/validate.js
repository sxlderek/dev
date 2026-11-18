"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TOOL_SCHEMAS = void 0;
exports.validateParams = validateParams;
const errors_1 = require("./errors");
// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------
const DNS_TYPES = ["A", "AAAA", "MX", "TXT", "CNAME", "SRV", "CAA", "NS", "PTR"];
exports.TOOL_SCHEMAS = {
    isp_provision_site: {
        fields: {
            domain: { type: "string", required: true, notEmpty: true },
            clientName: { type: "string", required: true, notEmpty: true },
            clientEmail: { type: "string", required: true, notEmpty: true },
            serverIp: { type: "string" },
            createMail: { type: "boolean" },
            createDb: { type: "boolean" },
            serverId: { type: "number" },
        },
    },
    isp_client_get: {
        anyOf: [["client_id", "clientId"]],
    },
    isp_site_get: {
        anyOf: [["primary_id", "domain_id", "site_id"]],
    },
    isp_dns_record_list: {
        anyOf: [["zone_id", "zoneId"]],
    },
    isp_dns_record_add: {
        fields: {
            type: { type: "string", required: true, notEmpty: true, enum: DNS_TYPES },
        },
    },
    isp_dns_record_delete: {
        fields: {
            type: { type: "string", required: true, notEmpty: true, enum: DNS_TYPES },
        },
    },
    isp_quota_check: {
        anyOf: [["client_id", "clientId"]],
    },
    // v0.3.0 additions
    isp_client_update: {
        anyOf: [["client_id"]],
    },
    isp_client_delete: {
        anyOf: [["client_id"]],
    },
    isp_site_update: {
        anyOf: [["primary_id"]],
    },
    isp_site_delete: {
        anyOf: [["primary_id"]],
    },
    isp_mail_domain_delete: {
        anyOf: [["primary_id"]],
    },
    isp_mail_alias_delete: {
        anyOf: [["primary_id"]],
    },
    isp_mail_forward_delete: {
        anyOf: [["primary_id"]],
    },
    isp_dns_zone_delete: {
        anyOf: [["primary_id"]],
    },
    isp_dns_record_update: {
        fields: {
            type: { type: "string", required: true, notEmpty: true, enum: DNS_TYPES },
        },
        anyOf: [["primary_id"]],
    },
    isp_db_delete: {
        anyOf: [["primary_id"]],
    },
    isp_db_user_delete: {
        anyOf: [["primary_id"]],
    },
    isp_ftp_user_delete: {
        anyOf: [["primary_id"]],
    },
    isp_shell_user_delete: {
        anyOf: [["primary_id"]],
    },
    isp_cron_delete: {
        anyOf: [["primary_id"]],
    },
    isp_cron_update: {
        anyOf: [["primary_id"]],
    },
    // v0.4.0 additions
    isp_dns_zone_get: {
        anyOf: [["primary_id", "zone_id"]],
    },
    isp_dns_zone_update: {
        anyOf: [["primary_id"]],
    },
    isp_mail_domain_update: {
        anyOf: [["primary_id"]],
    },
    isp_mail_user_update: {
        anyOf: [["primary_id"]],
    },
    isp_mail_alias_update: {
        anyOf: [["primary_id"]],
    },
    isp_mail_forward_update: {
        anyOf: [["primary_id"]],
    },
    isp_db_get: {
        anyOf: [["primary_id"]],
    },
    isp_db_update: {
        anyOf: [["primary_id"]],
    },
    isp_db_user_get: {
        anyOf: [["primary_id"]],
    },
    isp_db_user_update: {
        anyOf: [["primary_id"]],
    },
    isp_ftp_user_get: {
        anyOf: [["primary_id"]],
    },
    isp_ftp_user_update: {
        anyOf: [["primary_id"]],
    },
    isp_shell_user_get: {
        anyOf: [["primary_id"]],
    },
    isp_shell_user_update: {
        anyOf: [["primary_id"]],
    },
};
// ---------------------------------------------------------------------------
// Validator
// ---------------------------------------------------------------------------
function validateParams(toolName, params) {
    const schema = exports.TOOL_SCHEMAS[toolName];
    if (!schema)
        return;
    const errors = [];
    if (schema.fields) {
        for (const [key, rule] of Object.entries(schema.fields)) {
            const value = params[key];
            const present = value !== undefined && value !== null;
            if (rule.required && !present) {
                errors.push(`Missing required parameter: ${key}`);
                continue;
            }
            if (!present)
                continue;
            if (rule.notEmpty && String(value).trim() === "") {
                errors.push(`Parameter '${key}' must not be empty`);
            }
            if (rule.type === "number" && !Number.isFinite(Number(value))) {
                errors.push(`Parameter '${key}' must be a valid number, got: ${String(value)}`);
            }
            if (rule.enum) {
                const normalized = String(value).toUpperCase();
                if (!rule.enum.includes(normalized)) {
                    errors.push(`Parameter '${key}' must be one of [${rule.enum.join(", ")}], got: ${String(value)}`);
                }
            }
        }
    }
    if (schema.anyOf) {
        for (const group of schema.anyOf) {
            const found = group.some((key) => params[key] !== undefined && params[key] !== null);
            if (!found) {
                errors.push(`One of [${group.join(", ")}] is required`);
            }
        }
    }
    if (errors.length > 0) {
        throw new errors_1.ISPConfigError("validation_error", `Validation failed for ${toolName}: ${errors.join("; ")}`, { statusCode: 400 });
    }
}
//# sourceMappingURL=validate.js.map