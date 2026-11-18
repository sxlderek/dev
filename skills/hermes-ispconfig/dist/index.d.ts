export { ISPConfigError, ISPConfigErrorCode, normalizeError } from "./errors";
import { ISPConfigPluginConfig, JsonMap } from "./types";
export interface OpenClawRuntimeLike {
    registerTool: (name: string, definition: {
        description: string;
        parameters?: Record<string, unknown>;
        run: (params: JsonMap) => Promise<unknown>;
    }) => void;
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
    content: Array<{
        type: "text";
        text: string;
    }>;
    details: unknown;
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
export declare function buildToolset(config: Partial<ISPConfigPluginConfig>): BoundTool[];
export declare function registerAllTools(runtime: OpenClawRuntimeLike, config: Partial<ISPConfigPluginConfig>): void;
export declare function registerViaApi(api: OpenClawPluginApiLike): void;
declare const plugin: {
    manifest: {
        name: string;
        id: string;
        version: string;
        description: string;
        contracts: {
            tools: string[];
        };
        configSchema: {
            $schema: string;
            type: string;
            additionalProperties: boolean;
            required: string[];
            properties: {
                apiUrl: {
                    type: string;
                    description: string;
                };
                username: {
                    type: string;
                    description: string;
                };
                password: {
                    type: string;
                    description: string;
                    secret: boolean;
                };
                serverId: {
                    type: string;
                    description: string;
                    default: number;
                };
                defaultServerIp: {
                    type: string;
                    description: string;
                };
                readOnly: {
                    type: string;
                    description: string;
                    default: boolean;
                };
                allowedOperations: {
                    type: string;
                    description: string;
                    default: never[];
                    items: {
                        type: string;
                    };
                };
                verifySsl: {
                    type: string;
                    description: string;
                    default: boolean;
                };
            };
        };
    };
    register: typeof registerViaApi;
};
export default plugin;
//# sourceMappingURL=index.d.ts.map