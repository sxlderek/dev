"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.shellQuote = shellQuote;
exports.isValidIssueRepoSlug = isValidIssueRepoSlug;
exports.resolveIssueRepo = resolveIssueRepo;
exports.buildGhIssueCreateCommand = buildGhIssueCreateCommand;
const ISSUE_REPO_SLUG_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
function shellQuote(value) {
    return `'${String(value).replace(/'/g, `"'"'`)}'`;
}
function isValidIssueRepoSlug(value) {
    return ISSUE_REPO_SLUG_RE.test(value.trim());
}
function resolveIssueRepo(configValue, envValue, defaultRepo) {
    const candidates = [configValue, envValue, defaultRepo];
    for (const candidate of candidates) {
        if (typeof candidate !== "string")
            continue;
        const trimmed = candidate.trim();
        if (trimmed && isValidIssueRepoSlug(trimmed)) {
            return trimmed;
        }
    }
    return defaultRepo;
}
function buildGhIssueCreateCommand(args) {
    const repo = args.repo.trim();
    if (!isValidIssueRepoSlug(repo)) {
        throw new Error(`Invalid issue repository slug: ${args.repo}`);
    }
    const labels = (args.labels ?? []).map((label) => label.trim()).filter(Boolean);
    const parts = [
        "gh issue create",
        `-R ${shellQuote(repo)}`,
        `--title ${shellQuote(args.title)}`,
        `--body ${shellQuote(args.body)}`,
    ];
    if (labels.length > 0) {
        parts.push(`--label ${shellQuote(labels.join(","))}`);
    }
    return parts.join(" ");
}
//# sourceMappingURL=github-issue-helper.js.map