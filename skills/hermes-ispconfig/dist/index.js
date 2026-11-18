"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.normalizeError = exports.ISPConfigError = void 0;
exports.buildToolset = buildToolset;
exports.registerAllTools = registerAllTools;
exports.registerViaApi = registerViaApi;
const node_url_1 = require("node:url");
const openclaw_plugin_json_1 = __importDefault(require("../openclaw.plugin.json"));
var errors_1 = require("./errors");
Object.defineProperty(exports, "ISPConfigError", { enumerable: true, get: function () { return errors_1.ISPConfigError; } });
Object.defineProperty(exports, "normalizeError", { enumerable: true, get: function () { return errors_1.normalizeError; } });
const tools_1 = require("./tools");
function ensureConfig(config) {
    if (!config.apiUrl || !config.username || !config.password) {
        throw new Error("Missing required config: apiUrl, username, password");
    }
    return {
        apiUrl: config.apiUrl,
        username: config.username,
        password: config.password,
        serverId: config.serverId ?? 1,
        defaultServerIp: config.defaultServerIp,
        readOnly: config.readOnly ?? true,
        allowedOperations: config.allowedOperations ?? [],
        verifySsl: config.verifySsl ?? true,
        timeoutMs: config.timeoutMs,
    };
}
function buildToolset(config) {
    const safeConfig = ensureConfig(config);
    const context = { config: safeConfig };
    return (0, tools_1.createTools)().map((tool) => ({
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters ?? { type: "object", properties: {} },
        run: (params) => tool.run(params, context),
    }));
}
function registerAllTools(runtime, config) {
    const tools = buildToolset(config);
    for (const tool of tools) {
        runtime.registerTool(tool.name, {
            description: tool.description,
            parameters: tool.parameters,
            run: (params) => tool.run(params),
        });
    }
}
function formatToolResult(value) {
    const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    return {
        content: [{ type: "text", text }],
        details: value,
    };
}
// OpenClaw PluginApi adapter for the current native AgentTool contract.
function registerViaApi(api) {
    const config = (api.pluginConfig ?? {});
    const tools = buildToolset(config);
    for (const tool of tools) {
        api.registerTool({
            name: tool.name,
            label: tool.name,
            description: tool.description,
            parameters: tool.parameters ?? { type: "object", properties: {} },
            execute: async (_toolCallId, params = {}, _signal) => {
                return formatToolResult(await tool.run(params));
            },
        });
    }
    // Command: /ispconfig - show plugin overview, safe-use guidance, and examples.
    api.registerCommand({
        name: "ispconfig",
        description: "Show ISPConfig tools, safety state, and usage examples.",
        usage: "/ispconfig",
        requireAuth: false,
        acceptsArgs: false,
        handler: async () => {
            const rawUrl = (config.apiUrl ?? "").trim();
            // Extract hostname only - never expose credentials
            let displayHost = "(not configured)";
            try {
                if (rawUrl) {
                    displayHost = new node_url_1.URL(rawUrl).hostname;
                }
            }
            catch {
                displayHost = rawUrl.replace(/^https?:\/\//, "").split("/")[0] ?? rawUrl;
            }
            const version = openclaw_plugin_json_1.default.version ?? "0.3.0";
            const writeState = config.readOnly === false ? "⚠️ Write access enabled" : "🔒 Read-only mode";
            const allowlist = Array.isArray(config.allowedOperations) && config.allowedOperations.length > 0
                ? `🛡️ Allowlist: ${config.allowedOperations.length} tool(s)`
                : "🛡️ Allowlist: unrestricted";
            const text = [
                "🖥️ *ISPConfig Control Center*",
                `🔖 Version ${version} | 🌐 ${displayHost}`,
                `${writeState} | ${allowlist}`,
                "",
                "🧰 *292 API tools*",
                "🔎 Inspect: clients, sites, DNS, mail, databases, quotas, SSL and system state",
                "✍️ Change: create, update, delete, provision, status and lifecycle operations",
                "🚀 Provision: client + website + DNS + optional mail/database resources",
                "",
                "💡 *Examples*",
                "• Show all websites: `isp_sites_list`",
                "• Inspect a site: `isp_site_get` with `primary_id`",
                "• List DNS records: `isp_dns_record_list` with `zone_id`",
                "• Check SSL: `isp_ssl_status`",
                "• Update a site: `isp_site_update` with `client_id`, `primary_id`, and `params`",
                "",
                "🔐 *Write safety*",
                "• Writes require `readOnly: false`.",
                "• A configured allowlist must include each tool you want to use.",
                "• Provisioning with mail or a database requires explicit secret passwords.",
                "",
                "📚 Ask for a specific resource or operation, for example: ‘List all websites’ or ‘Check SSL status’."
            ].join("\n");
            return { text };
        },
    });
}
const plugin = {
    manifest: openclaw_plugin_json_1.default,
    register: registerViaApi,
};
exports.default = plugin;
//# sourceMappingURL=index.js.map