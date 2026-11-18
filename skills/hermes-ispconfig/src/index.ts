import { URL } from "node:url";
import pluginManifest from "../openclaw.plugin.json";
export { ISPConfigError, ISPConfigErrorCode, normalizeError } from "./errors";
import { createTools } from "./tools";
import { ISPConfigPluginConfig, JsonMap } from "./types";

export interface OpenClawRuntimeLike {
  registerTool: (name: string, definition: { description: string; parameters?: Record<string, unknown>; run: (params: JsonMap) => Promise<unknown> }) => void;
}

export interface OpenClawPluginApiLike {
  pluginConfig?: Record<string, unknown>;
  registerTool: (tool: {
    name: string;
    label: string;
    description: string;
    parameters: NonNullable<BoundTool["parameters"]>;
    execute: (toolCallId: string, params: JsonMap, signal?: AbortSignal) => Promise<AgentToolResult>;
  }) => void;
  registerCommand: (command: Record<string, unknown>) => void;
}

export interface AgentToolResult {
  content: Array<{ type: "text"; text: string }>;
  details: unknown;
}

function ensureConfig(config: Partial<ISPConfigPluginConfig>): ISPConfigPluginConfig {
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

export interface BoundTool {
  name: string;
  description: string;
  parameters?: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
  run: (params: JsonMap) => Promise<unknown>;
}

export function buildToolset(config: Partial<ISPConfigPluginConfig>): BoundTool[] {
  const safeConfig = ensureConfig(config);
  const context = { config: safeConfig };
  return createTools().map((tool) => ({
    name: tool.name,
    description: tool.description,
    parameters: tool.parameters ?? { type: "object" as const, properties: {} },
    run: (params: JsonMap) => tool.run(params, context),
  }));
}

export function registerAllTools(runtime: OpenClawRuntimeLike, config: Partial<ISPConfigPluginConfig>): void {
  const tools = buildToolset(config);
  for (const tool of tools) {
    runtime.registerTool(tool.name, {
      description: tool.description,
      parameters: tool.parameters,
      run: (params: JsonMap) => tool.run(params),
    });
  }
}

function formatToolResult(value: unknown): AgentToolResult {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return {
    content: [{ type: "text", text }],
    details: value,
  };
}

// OpenClaw PluginApi adapter for the current native AgentTool contract.
export function registerViaApi(api: OpenClawPluginApiLike): void {
  const config = (api.pluginConfig ?? {}) as Partial<ISPConfigPluginConfig>;
  const tools = buildToolset(config);
  for (const tool of tools) {
    api.registerTool({
      name: tool.name,
      label: tool.name,
      description: tool.description,
      parameters: tool.parameters ?? { type: "object", properties: {} },
      execute: async (_toolCallId: string, params: JsonMap = {}, _signal?: AbortSignal) => {
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
      const rawUrl: string = (config.apiUrl ?? "").trim();
      // Extract hostname only - never expose credentials
      let displayHost = "(not configured)";
      try {
        if (rawUrl) {
          displayHost = new URL(rawUrl).hostname;
        }
      } catch {
        displayHost = rawUrl.replace(/^https?:\/\//, "").split("/")[0] ?? rawUrl;
      }

      const version: string = (pluginManifest as { version?: string }).version ?? "0.3.0";

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
  manifest: pluginManifest,
  register: registerViaApi,
};

export default plugin;
