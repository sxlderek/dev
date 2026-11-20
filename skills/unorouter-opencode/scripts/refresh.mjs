#!/usr/bin/env node
// Refresh the UnoRouter model list in the OpenCode global configuration.
//
// Usage:
//   node refresh.mjs [--dry-run] [--json]
//
// What it does:
//   1. Reads the UnoRouter API key (UNOROUTER_API_KEY, else OpenCode auth.json).
//   2. GET https://api.unorouter.com/v1/models (live inventory).
//   3. Keeps text/chat models only:
//      - drops every id ending in ":free"
//      - drops models whose endpoint types are purely non-text
//        (image-generation / aihorde / typesafe-decisions / embedding-* / aihorde)
//      - drops models whose id signals image / video / audio / embedding / tts
//   4. Enriches each model with metadata from https://models.dev/api.json
//      (name, limits, capabilities, cost, family, release date).
//   5. Rewrites providers.unorouter.models in ~/.config/opencode/opencode.jsonc
//      (a .bak-<timestamp> copy is taken first). Everything else in the file is
//      preserved.
//
// The resulting models are selectable in OpenCode as  unorouter/<modelID>.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const PROVIDER = "unorouter";
const MODELS_URL = "https://api.unorouter.com/v1/models";
const CATALOG_URL = "https://models.dev/api.json";

// Endpoint types that make a model non-text at the UnoRouter layer.
const NON_TEXT_TYPES = ["image-generation", "aihorde", "typesafe-decisions"];
// Ids that are image/video/audio/embedding/tts despite sometimes advertising "openai".
const NON_TEXT_ID = /(embedding|image|nano-banana|video|tts|speech|audio|diffusion|sdxl|inpaint)/i;

const args = new Set(process.argv.slice(2));
const DRY_RUN = args.has("--dry-run");
const AS_JSON = args.has("--json");

const out = (msg) => console.log(msg);
const fail = (msg) => {
  console.error("ERROR: " + msg);
  process.exit(1);
};

// --- paths -----------------------------------------------------------------
const home = os.homedir();
const configCandidates = [
  path.join(process.env.XDG_CONFIG_HOME || path.join(home, ".config"), "opencode", "opencode.jsonc"),
  path.join(process.env.XDG_CONFIG_HOME || path.join(home, ".config"), "opencode", "opencode.json"),
  path.join(home, ".config", "opencode", "opencode.jsonc"),
  path.join(home, ".config", "opencode", "opencode.json"),
];
const configPath = configCandidates.find((p) => fs.existsSync(p));
if (!configPath) fail("OpenCode config not found. Looked in:\n  " + configCandidates.join("\n  "));

const authCandidates = [
  path.join(process.env.XDG_DATA_HOME || path.join(home, ".local", "share"), "opencode", "auth.json"),
  path.join(process.env.LOCALAPPDATA || "", "opencode", "auth.json"),
];

// --- credential ------------------------------------------------------------
async function apiKey() {
  if (process.env.UNOROUTER_API_KEY) return process.env.UNOROUTER_API_KEY;
  for (const p of authCandidates) {
    if (!p || !fs.existsSync(p)) continue;
    try {
      const auth = JSON.parse(fs.readFileSync(p, "utf8"));
      const key = auth?.[PROVIDER]?.key;
      if (key) return key;
    } catch {
      /* ignore unreadable auth file */
    }
  }
  fail(
    `No UnoRouter API key. Set UNOROUTER_API_KEY, or connect the provider in OpenCode (/connect -> UnoRouter), ` +
      `so a key is stored in auth.json.`,
  );
}

// --- JSONC handling --------------------------------------------------------
function stripJsonc(text) {
  let result = "";
  let i = 0;
  let inStr = false;
  let inLineComment = false;
  let inBlockComment = false;
  while (i < text.length) {
    const c = text[i];
    const n = text[i + 1];
    if (inLineComment) {
      if (c === "\n") {
        inLineComment = false;
        result += c;
      }
      i++;
      continue;
    }
    if (inBlockComment) {
      if (c === "*" && n === "/") {
        inBlockComment = false;
        i += 2;
        continue;
      }
      if (c === "\n") result += c;
      i++;
      continue;
    }
    if (inStr) {
      result += c;
      if (c === "\\") {
        result += n ?? "";
        i += 2;
        continue;
      }
      if (c === '"') inStr = false;
      i++;
      continue;
    }
    if (c === '"') {
      inStr = true;
      result += c;
      i++;
      continue;
    }
    if (c === "/" && n === "/") {
      inLineComment = true;
      i += 2;
      continue;
    }
    if (c === "/" && n === "*") {
      inBlockComment = true;
      i += 2;
      continue;
    }
    result += c;
    i++;
  }
  return result.replace(/,(\s*[}\]])/g, "$1");
}

// --- model selection -------------------------------------------------------
function isTextModel(m) {
  const types = m.supported_endpoint_types || [];
  if (m.id.endsWith(":free")) return false;
  if (types.some((t) => NON_TEXT_TYPES.includes(t) || /^embedding/i.test(t))) return false;
  if (NON_TEXT_ID.test(m.id)) return false;
  return true;
}

function prettyName(id) {
  return id
    .split("/")
    .pop()
    .split(":")
    .map((s) =>
      s.replace(/[-_.]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    )
    .join(":");
}

function buildEntry(id, live, md) {
  const entry = { modelID: id, name: md?.name || prettyName(id) };
  if (md?.family) entry.family = md.family;
  if (md?.release_date && /^\d{4}(-\d{2}(-\d{2})?)?$/.test(String(md.release_date)))
    entry.releaseDate = md.release_date;

  const caps = {};
  caps.tools = typeof md?.tool_call === "boolean" ? md.tool_call : true;
  caps.input = md?.modalities?.input?.length ? md.modalities.input : ["text"];
  caps.output = md?.modalities?.output?.length ? md.modalities.output : ["text"];
  if (typeof md?.temperature === "boolean") caps.temperature = md.temperature;
  if (md?.reasoning) {
    const reasoning = { supported: true };
    const efforts = (md.reasoning_options || [])
      .map((o) => {
        if (typeof o === "string") return o;
        return o && (o.value ?? o.name ?? null);
      })
      .filter((v) => typeof v === "string" && v.length > 0);
    if (efforts.length) reasoning.effort = efforts;
    caps.reasoning = reasoning;
  }
  entry.capabilities = caps;

  const limit = {};
  const context = live?.context_length ?? md?.limit?.context;
  const output = live?.max_output_tokens ?? md?.limit?.output;
  const input = md?.limit?.input;
  if (Number.isFinite(context)) limit.context = context;
  if (Number.isFinite(output)) limit.output = output;
  if (Number.isFinite(input)) limit.input = input;
  if (Object.keys(limit).length) entry.limit = limit;

  if (Number.isFinite(md?.cost?.input) && Number.isFinite(md?.cost?.output)) {
    entry.cost = { input: md.cost.input, output: md.cost.output };
  }
  return entry;
}

// --- main ------------------------------------------------------------------
const key = await apiKey();

const liveRes = await fetch(MODELS_URL, { headers: { Authorization: "Bearer " + key } });
if (!liveRes.ok) fail(`GET ${MODELS_URL} -> HTTP ${liveRes.status} (check the UnoRouter API key)`);
const liveJson = await liveRes.json();
const liveModels = Array.isArray(liveJson?.data) ? liveJson.data : fail("Unexpected /v1/models response shape");

let catalog = {};
try {
  const catRes = await fetch(CATALOG_URL);
  if (catRes.ok) catalog = (await catRes.json())?.[PROVIDER]?.models ?? {};
} catch {
  out("warning: models.dev catalog unavailable, writing minimal entries");
}

const selected = liveModels.filter(isTextModel).sort((a, b) => a.id.localeCompare(b.id));
if (!selected.length) fail("No non-free text models returned by UnoRouter");

const models = {};
const minimal = [];
for (const m of selected) {
  const md = catalog[m.id];
  // Live entry lacks context info (e.g. "[1m]" fast variants) and no catalog
  // metadata: keep the model selectable but with only identity fields.
  const hasLimits = Number.isFinite(m.context_length) || Number.isFinite(m.max_output_tokens) || !!md;
  if (!hasLimits) {
    minimal.push(m.id);
    models[m.id] = { modelID: m.id, name: md?.name || prettyName(m.id) };
    continue;
  }
  models[m.id] = buildEntry(m.id, m, md);
}

// --- config update ---------------------------------------------------------
const raw = fs.readFileSync(configPath, "utf8");
let config;
try {
  config = JSON.parse(stripJsonc(raw));
} catch (e) {
  fail(`Could not parse ${configPath}: ${e.message}`);
}

const previous = config?.providers?.[PROVIDER]?.models ?? {};
const prevKeys = Object.keys(previous);
const newKeys = Object.keys(models);
const added = newKeys.filter((k) => !prevKeys.includes(k));
const removed = prevKeys.filter((k) => !newKeys.includes(k));

if (!DRY_RUN) {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "").replace("T", "-");
  const backup = `${configPath}.bak-${stamp}`;
  fs.copyFileSync(configPath, backup);

  config.providers = config.providers ?? {};
  config.providers[PROVIDER] = config.providers[PROVIDER] ?? {};
  if (!config.providers[PROVIDER].name) config.providers[PROVIDER].name = "UnoRouter";
  config.providers[PROVIDER].models = models;
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n", "utf8");
  out(`config:  ${configPath}`);
  out(`backup:  ${backup}`);
}

if (AS_JSON) {
  console.log(
    JSON.stringify(
      {
        configPath,
        liveTotal: liveModels.length,
        freeExcluded: liveModels.filter((m) => m.id.endsWith(":free")).length,
        selected: newKeys.length,
        minimalEntries: minimal.length,
        added: added.length,
        removed: removed.length,
        addedIds: added,
        removedIds: removed,
        minimalIds: minimal,
        models: DRY_RUN ? models : undefined,
      },
      null,
      2,
    ),
  );
} else {
  out(`live models:          ${liveModels.length}`);
  out(`":free" excluded:      ${liveModels.filter((m) => m.id.endsWith(":free")).length}`);
  out(`non-text excluded:     ${liveModels.filter((m) => !m.id.endsWith(":free") && !isTextModel(m)).length}`);
  out(`text models written:${DRY_RUN ? " (dry run)" : ""} ${newKeys.length}`);
  out(`  full entries:        ${newKeys.length - minimal.length}`);
  out(`  minimal (no limits): ${minimal.length}${minimal.length ? " -> " + minimal.join(", ") : ""}`);
  out(`added:   ${added.length}${added.length ? " -> " + added.join(", ") : ""}`);
  out(`removed: ${removed.length}${removed.length ? " -> " + removed.join(", ") : ""}`);
}
