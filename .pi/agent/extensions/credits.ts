import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

type UsageStatus = {
	github?: GitHubUsage;
	gpt?: GptUsage;
	updatedAt?: number;
	error?: string;
};

type GitHubUsage = {
	used?: number;
	limit?: number;
	additionalUsed?: number;
	additionalLimit?: number;
	resetsAt?: string;
	error?: string;
};

type GptUsage = {
	/** Short rolling window, from x-codex-primary-* headers. */
	shortPercent?: number;
	shortResetsAt?: string;
	/** Weekly rolling window, from x-codex-secondary-* headers. */
	weeklyPercent?: number;
	weeklyResetsAt?: string;
	/** Backward compatibility for command/page parsers. */
	percent?: number;
	resetsAt?: string;
	error?: string;
};

type UiContext = Parameters<Parameters<ExtensionAPI["on"]>[1]>[1];

const REFRESH_MS = numberEnv("PI_CREDITS_REFRESH_MS", numberEnv("PI_USAGE_REFRESH_MS", 15 * 60 * 1000));
const GITHUB_URL = process.env.PI_CREDITS_GITHUB_URL ?? process.env.PI_USAGE_GITHUB_URL ?? "https://github.com/settings/billing/ai_usage";
const GPT_URL = process.env.PI_CREDITS_GPT_URL ?? process.env.PI_USAGE_GPT_URL ?? "https://chatgpt.com/codex/cloud/settings/analytics#usage";

export default function (pi: ExtensionAPI) {
	let status: UsageStatus = {};
	let timer: ReturnType<typeof setInterval> | undefined;
	let lastCtx: UiContext | undefined;

	async function refresh(ctx?: UiContext) {
		const next: UsageStatus = { updatedAt: Date.now() };
		const [github, gpt] = await Promise.all([loadGitHub(pi, ctx ?? lastCtx), loadGpt(pi, ctx ?? lastCtx)]);
		next.github = github;
		next.gpt = gpt;
		status = next;
		if (ctx ?? lastCtx) installHeader(ctx ?? lastCtx!);
	}

	async function refreshGitHubOnly(ctx?: UiContext) {
		const github = await loadGitHub(pi, ctx ?? lastCtx);
		status = { ...status, github, updatedAt: Date.now() };
		if (ctx ?? lastCtx) installHeader(ctx ?? lastCtx!);
	}

	function installHeader(ctx: UiContext) {
		lastCtx = ctx;
		if (ctx.mode !== "tui") return;
		// Use Pi's existing footer status line. This preserves the built-in footer
		// and avoids custom-footer regressions.
		ctx.ui.setHeader(undefined);
		ctx.ui.setWidget("credits", undefined);
		// Do not call setFooter(undefined): that restores Pi's built-in footer and
		// can make credits appear twice when another extension (e.g. powerline)
		// owns the footer and also renders extension statuses.
		const theme = ctx.ui.theme;
		const provider = ctx.model?.provider;
		const line = provider === "github-copilot"
			? renderGitHub(status.github, theme, 96)
			: provider === "openai-codex"
				? renderGpt(status.gpt, theme, 96)
				: `${renderGitHub(status.github, theme, 96)}${theme.fg("dim", " │ ")}${renderGpt(status.gpt, theme, 96)}`;
		// Footer status sanitization trims leading normal spaces. ZWSP + NBSPs
		// keep a small visual gap after Pi's footer separator.
		ctx.ui.setStatus("credits", `\u200B\u00A0\u00A0${line}`);
	}

	pi.on("session_start", async (_event, ctx) => {
		installHeader(ctx);
		void refresh(ctx);
		// GitHub exposes a zero-cost usage endpoint. ChatGPT/Codex usage is refreshed
		// from normal provider responses, or by /credit-refresh's tiny probe.
		if (!timer) timer = setInterval(() => void refreshGitHubOnly(lastCtx), REFRESH_MS);
	});

	pi.on("after_provider_response", async (event, ctx) => {
		const gpt = parseGptHeaders(event.headers);
		if (!gpt) return;
		status = { ...status, gpt, updatedAt: Date.now() };
		installHeader(ctx);
	});

	pi.on("model_select", async (_event, ctx) => installHeader(ctx));
	pi.on("thinking_level_select", async (_event, ctx) => installHeader(ctx));

	pi.on("session_shutdown", async () => {
		if (timer) clearInterval(timer);
		timer = undefined;
	});

	pi.registerCommand("credit-refresh", {
		description: "Refresh GitHub Copilot and ChatGPT/Codex credits in the header",
		handler: async (_args, ctx) => {
			await refresh(ctx);
			ctx.ui.notify("Credits refreshed", "info");
		},
	});

	pi.registerCommand("credit", {
		description: "Refresh credits in the footer",
		handler: async (_args, ctx) => {
			await refresh(ctx);
			// No notification: the persistent footer is the display. This avoids
			// duplicating the credits in the transcript/console area.
		},
	});
}

async function loadGitHub(pi: ExtensionAPI, ctx?: UiContext): Promise<GitHubUsage> {
	try {
		const fromCommand = await loadJsonFromCommand<GitHubUsage>(pi, process.env.PI_CREDITS_GITHUB_CMD ?? process.env.PI_USAGE_GITHUB_CMD);
		if (fromCommand) return fromCommand;

		const stored = ctx?.modelRegistry.authStorage.get("github-copilot");
		if (stored?.type === "oauth" && typeof stored.refresh === "string") {
			return await loadGitHubFromCopilotOAuth(stored.refresh);
		}

		const cookie = process.env.PI_CREDITS_GITHUB_COOKIE ?? process.env.PI_USAGE_GITHUB_COOKIE;
		const bearer = await ctx?.modelRegistry.getApiKeyForProvider("github-copilot");
		if (!cookie && !bearer) return { error: "not signed in to github-copilot; or set PI_CREDITS_GITHUB_COOKIE / PI_CREDITS_GITHUB_CMD" };
		const text = await fetchText(GITHUB_URL, { cookie, bearer });
		return parseGitHub(text);
	} catch (error) {
		return { error: errorMessage(error) };
	}
}

async function loadGpt(pi: ExtensionAPI, ctx?: UiContext): Promise<GptUsage> {
	try {
		const fromCommand = await loadJsonFromCommand<GptUsage>(pi, process.env.PI_CREDITS_GPT_CMD ?? process.env.PI_USAGE_GPT_CMD);
		if (fromCommand) return fromCommand;

		const codexBearer = await ctx?.modelRegistry.getApiKeyForProvider("openai-codex");
		if (codexBearer) return await loadGptFromCodexOAuth(codexBearer);

		const cookie = process.env.PI_CREDITS_GPT_COOKIE ?? process.env.PI_USAGE_GPT_COOKIE;
		const bearer = await ctx?.modelRegistry.getApiKeyForProvider("openai");
		if (!cookie && !bearer) return { error: "not signed in to openai-codex/openai; or set PI_CREDITS_GPT_COOKIE / PI_CREDITS_GPT_CMD" };
		const text = await fetchText(GPT_URL, { cookie, bearer });
		return parseGpt(text);
	} catch (error) {
		return { error: errorMessage(error) };
	}
}

async function loadJsonFromCommand<T>(pi: ExtensionAPI, command: string | undefined): Promise<T | undefined> {
	if (!command) return undefined;
	const result = await pi.exec("bash", ["-lc", command], { timeout: 30_000 });
	if (result.code !== 0) throw new Error(result.stderr || result.stdout || `command failed with ${result.code}`);
	return JSON.parse(result.stdout.trim()) as T;
}

async function loadGitHubFromCopilotOAuth(githubToken: string): Promise<GitHubUsage> {
	const response = await fetch("https://api.github.com/copilot_internal/user", {
		headers: {
			Authorization: `Bearer ${githubToken}`,
			Accept: "application/json",
			"User-Agent": "GitHubCopilotChat/0.35.0",
		},
	});
	if (!response.ok) throw new Error(`GitHub Copilot user API: ${response.status} ${response.statusText}`);
	const json = await response.json() as {
		quota_reset_date_utc?: string;
		quota_reset_date?: string;
		quota_snapshots?: {
			premium_interactions?: {
				remaining?: number;
				entitlement?: number;
				overage_count?: number;
				overage_entitlement?: number;
				overage_permitted?: boolean;
			};
		};
	};
	const premium = json.quota_snapshots?.premium_interactions;
	const limit = premium?.entitlement;
	const remaining = premium?.remaining;
	const used = limit !== undefined && remaining !== undefined ? Math.max(0, limit - Math.max(0, remaining)) : undefined;
	return {
		used,
		limit,
		additionalUsed: premium?.overage_permitted ? premium?.overage_count : 0,
		additionalLimit: premium?.overage_permitted ? premium?.overage_entitlement : 0,
		resetsAt: formatReset(json.quota_reset_date_utc ?? json.quota_reset_date),
	};
}

async function loadGptFromCodexOAuth(token: string): Promise<GptUsage> {
	const accountId = getOpenAIAccountId(token);
	if (!accountId) throw new Error("OpenAI Codex token has no ChatGPT account id");
	const response = await fetch("https://chatgpt.com/backend-api/codex/responses", {
		method: "POST",
		headers: {
			Authorization: `Bearer ${token}`,
			"chatgpt-account-id": accountId,
			originator: "pi",
			"User-Agent": "pi-credits-extension",
			Accept: "text/event-stream",
			"content-type": "application/json",
			"OpenAI-Beta": "responses=experimental",
		},
		body: JSON.stringify({
			model: process.env.PI_CREDITS_GPT_PROBE_MODEL ?? "gpt-5.5",
			instructions: "Reply with ok.",
			input: [{ role: "user", content: [{ type: "input_text", text: "ok" }] }],
			stream: true,
			store: false,
		}),
	});
	const headers = Object.fromEntries(response.headers.entries());
	// Drain the body so the HTTP connection can close cleanly. The usage data is in headers.
	await response.text().catch(() => undefined);
	const parsed = parseGptHeaders(headers);
	if (parsed) return parsed;
	if (!response.ok) throw new Error(`OpenAI Codex usage probe: ${response.status} ${response.statusText}`);
	throw new Error("OpenAI Codex usage probe returned no x-codex usage headers");
}

function parseGptHeaders(headers: Record<string, string>): GptUsage | undefined {
	const shortPercent = toNumber(headers["x-codex-primary-used-percent"]);
	const shortResetAt = toNumber(headers["x-codex-primary-reset-at"]);
	const shortResetAfter = toNumber(headers["x-codex-primary-reset-after-seconds"]);
	const weeklyPercent = toNumber(headers["x-codex-secondary-used-percent"]);
	const weeklyResetAt = toNumber(headers["x-codex-secondary-reset-at"]);
	const weeklyResetAfter = toNumber(headers["x-codex-secondary-reset-after-seconds"]);
	if (
		shortPercent === undefined &&
		shortResetAt === undefined &&
		shortResetAfter === undefined &&
		weeklyPercent === undefined &&
		weeklyResetAt === undefined &&
		weeklyResetAfter === undefined
	) return undefined;
	return {
		shortPercent,
		shortResetsAt: formatCodexReset(shortResetAt, shortResetAfter),
		weeklyPercent,
		weeklyResetsAt: formatCodexReset(weeklyResetAt, weeklyResetAfter),
		// Keep old renderers/config command output working.
		percent: weeklyPercent ?? shortPercent,
		resetsAt: formatCodexReset(weeklyResetAt, weeklyResetAfter) ?? formatCodexReset(shortResetAt, shortResetAfter),
	};
}

function getOpenAIAccountId(token: string): string | undefined {
	try {
		const payload = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString("utf8"));
		const accountId = payload?.["https://api.openai.com/auth"]?.chatgpt_account_id;
		return typeof accountId === "string" ? accountId : undefined;
	} catch {
		return undefined;
	}
}

async function fetchText(url: string, auth: { cookie?: string; bearer?: string }): Promise<string> {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), 30_000);
	try {
		const headers: Record<string, string> = {
			"user-agent": "Mozilla/5.0 pi-credits-extension",
			accept: "text/html,application/json;q=0.9,*/*;q=0.8",
		};
		if (auth.cookie) headers.cookie = auth.cookie;
		if (auth.bearer) headers.authorization = `Bearer ${auth.bearer}`;
		const response = await fetch(url, {
			headers,
			signal: controller.signal,
		});
		if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
		return await response.text();
	} finally {
		clearTimeout(timeout);
	}
}

function parseGitHub(text: string): GitHubUsage {
	const plain = normalize(text);
	const allFractions = [...plain.matchAll(/(\d[\d,]*)\s*\/\s*(\d[\d,]*)/g)]
		.map((m) => ({ used: toNumber(m[1]), limit: toNumber(m[2]), index: m.index ?? 0 }))
		.filter((x) => x.used !== undefined && x.limit !== undefined);
	const main = allFractions.find((x) => x.limit === 7000) ?? allFractions[0];
	const additional = findMoneyPair(plain);
	return {
		used: main?.used,
		limit: main?.limit,
		additionalUsed: additional?.used,
		additionalLimit: additional?.limit,
		resetsAt: formatReset(findReset(plain)),
		error: main ? undefined : "could not parse GitHub usage page; use PI_USAGE_GITHUB_CMD",
	};
}

function parseGpt(text: string): GptUsage {
	const plain = normalize(text);
	const percent = firstNumber(plain.match(/(\d{1,3}(?:\.\d+)?)\s*%/));
	return {
		percent,
		resetsAt: formatReset(findReset(plain)),
		error: percent === undefined ? "could not parse GPT usage page; use PI_USAGE_GPT_CMD" : undefined,
	};
}

function findMoneyPair(text: string): { used: number; limit: number } | undefined {
	const labeled = text.match(/additional.{0,120}?\$\s*([\d,.]+)\s*\/\s*\$\s*([\d,.]+)/i);
	const generic = text.match(/\$\s*([\d,.]+)\s*\/\s*\$\s*([\d,.]+)/);
	const match = labeled ?? generic;
	if (!match) return undefined;
	return { used: Number(match[1].replaceAll(",", "")), limit: Number(match[2].replaceAll(",", "")) };
}

function findReset(text: string): string | undefined {
	const reset = text.match(/(?:reset|resets|restart|restarts|renews|renewal).{0,80}?(?:on|in|at)?\s*([A-Z][a-z]{2,9}\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}\/\d{1,2}(?:\/\d{2,4})?|\d+\s+(?:hours?|days?|minutes?))/i);
	return reset?.[1]?.trim();
}

function renderGitHub(data: GitHubUsage | undefined, theme: UiContext["ui"]["theme"], width: number): string {
	if (!data) return theme.fg("dim", "GitHub loading…");
	if (data.error) return `${theme.fg("warning", "GitHub ?")} ${theme.fg("dim", data.error)}`;
	const used = data.used ?? 0;
	const limit = data.limit ?? 0;
	const ratio = limit > 0 ? used / limit : 0;
	const add = data.additionalUsed !== undefined && data.additionalLimit !== undefined
		? theme.fg("dim", ` extra $${data.additionalUsed}/$${data.additionalLimit}`)
		: "";
	const barWidth = Math.min(10, Math.max(6, Math.floor(width / 12)));
	return `${theme.fg("muted", "GitHub")} ${bar(ratio, theme, barWidth)} ${used}/${limit}${add}${data.resetsAt ? theme.fg("dim", ` ↻ ${data.resetsAt}`) : ""}`;
}

function renderGpt(data: GptUsage | undefined, theme: UiContext["ui"]["theme"], width: number): string {
	if (!data) return theme.fg("dim", "Codex loading…");
	if (data.error) return `${theme.fg("warning", "Codex ?")} ${theme.fg("dim", data.error)}`;
	const barWidth = Math.min(10, Math.max(6, Math.floor(width / 12)));
	const shortPct = clamp(data.shortPercent ?? data.percent ?? 0, 0, 100);
	const weeklyPct = clamp(data.weeklyPercent ?? data.percent ?? 0, 0, 100);
	return `${theme.fg("muted", "Codex")} ${bar(shortPct / 100, theme, barWidth)} ${shortPct}%${data.shortResetsAt ? theme.fg("dim", ` ↻ ${data.shortResetsAt}`) : ""} ${theme.fg("muted", "week")} ${bar(weeklyPct / 100, theme, barWidth)} ${weeklyPct}%${data.weeklyResetsAt ? theme.fg("dim", ` ↻ ${data.weeklyResetsAt}`) : ""}`;
}

function bar(ratio: number, theme: UiContext["ui"]["theme"], width: number): string {
	const filled = Math.round(clamp(ratio, 0, 1) * width);
	const empty = Math.max(0, width - filled);
	const color = ratio >= 0.9 ? "error" : ratio >= 0.7 ? "warning" : "success";
	return `${theme.fg("dim", "[")}${theme.fg(color as "error", "█".repeat(filled))}${theme.fg("dim", "░".repeat(empty) + "]")}`;
}

function plainBar(percent: number | undefined, width = 10): string {
	if (percent === undefined) return `[${"░".repeat(width)}]`;
	const filled = Math.round(clamp(percent, 0, 100) / 100 * width);
	return `[${"█".repeat(filled)}${"░".repeat(width - filled)}]`;
}

function percentValue(value: number | undefined): number | undefined {
	return value === undefined ? undefined : clamp(value, 0, 100);
}

function normalize(text: string): string {
	return text
		.replace(/<script[\s\S]*?<\/script>/gi, " ")
		.replace(/<style[\s\S]*?<\/style>/gi, " ")
		.replace(/<[^>]+>/g, " ")
		.replace(/&nbsp;/g, " ")
		.replace(/&amp;/g, "&")
		.replace(/\s+/g, " ")
		.trim();
}

function toNumber(value: string | undefined): number | undefined {
	if (!value) return undefined;
	const parsed = Number(value.replaceAll(",", ""));
	return Number.isFinite(parsed) ? parsed : undefined;
}

function firstNumber(match: RegExpMatchArray | null): number | undefined {
	if (!match?.[1]) return undefined;
	const value = Number(match[1]);
	return Number.isFinite(value) ? value : undefined;
}

function clamp(value: number, min: number, max: number): number {
	return Math.max(min, Math.min(max, value));
}

function numberEnv(name: string, fallback: number): number {
	const raw = process.env[name];
	if (!raw) return fallback;
	const value = Number(raw);
	return Number.isFinite(value) ? value : fallback;
}

function formatTime(timestamp: number): string {
	return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatCodexReset(resetAtSeconds: number | undefined, resetAfterSeconds: number | undefined): string | undefined {
	if (resetAtSeconds !== undefined) return formatReset(new Date(resetAtSeconds * 1000).toISOString());
	if (resetAfterSeconds !== undefined) return `${Math.ceil(resetAfterSeconds / 60)} min`;
	return undefined;
}

function formatReset(value: string | undefined): string | undefined {
	if (!value) return undefined;
	const timestamp = Date.parse(value);
	if (Number.isNaN(timestamp)) return value;
	const date = new Date(timestamp);
	const hoursAway = Math.abs(timestamp - Date.now()) / 3_600_000;
	if (hoursAway > 24) return date.toLocaleDateString([], { month: "short", day: "numeric" });
	return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

function errorMessage(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}
