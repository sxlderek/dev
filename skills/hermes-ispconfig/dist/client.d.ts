import { ISPConfigPluginConfig, JsonMap } from "./types";
export declare class ISPConfigClient {
    private readonly config;
    private readonly url;
    private readonly timeoutMs;
    private readonly verifySsl;
    private sessionId;
    private isLoggingIn;
    constructor(config: ISPConfigPluginConfig);
    login(): Promise<string>;
    logout(): Promise<unknown>;
    call<T>(method: string, params?: JsonMap): Promise<T>;
    private shouldRetrySession;
    private rawCall;
}
//# sourceMappingURL=client.d.ts.map