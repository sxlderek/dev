export declare function shellQuote(value: string): string;
export declare function isValidIssueRepoSlug(value: string): boolean;
export declare function resolveIssueRepo(configValue: unknown, envValue: unknown, defaultRepo: string): string;
export declare function buildGhIssueCreateCommand(args: {
    repo: string;
    title: string;
    body: string;
    labels?: string[];
}): string;
//# sourceMappingURL=github-issue-helper.d.ts.map