export type ISPConfigErrorCode = "validation_error" | "permission_denied" | "invalid_method" | "auth_error" | "api_error" | "network_error" | "parse_error";
export declare class ISPConfigError extends Error {
    readonly code: ISPConfigErrorCode;
    readonly retryable: boolean;
    readonly statusCode?: number;
    constructor(code: ISPConfigErrorCode, message: string, options?: {
        retryable?: boolean;
        statusCode?: number;
        cause?: unknown;
    });
}
export declare function classifyApiMessage(message: string): ISPConfigErrorCode;
export declare function normalizeError(err: unknown): ISPConfigError;
//# sourceMappingURL=errors.d.ts.map