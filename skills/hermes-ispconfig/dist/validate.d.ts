import { JsonMap } from "./types";
interface ParamRule {
    /** Expected value type */
    type?: "string" | "number" | "boolean";
    /** Field must be present and non-null */
    required?: boolean;
    /** String value must not be empty/whitespace-only */
    notEmpty?: boolean;
    /** Allowed values (compared case-insensitively for strings) */
    enum?: string[];
}
interface ToolParamSchema {
    /** Per-field validation rules */
    fields?: Record<string, ParamRule>;
    /** At least one key from each group must be present (OR logic within group) */
    anyOf?: string[][];
}
export declare const TOOL_SCHEMAS: Record<string, ToolParamSchema>;
export declare function validateParams(toolName: string, params: JsonMap): void;
export {};
//# sourceMappingURL=validate.d.ts.map