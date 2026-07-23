import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EXTENSION_DIR = path.dirname(fileURLToPath(import.meta.url));

/**
 * python-uv
 *
 * Forces Python to run through `uv` instead of the global `python`/`python3`
 * interpreter:
 *   - `before_agent_start` injects a one-line standing policy each turn so the
 *     model sees the rule *before* it writes a command (proactive).
 *   - `tool_call` / `user_bash` block any command that executes `python`/
 *     `python3` as a program — in command position OR as the program passed to
 *     `uv run` (e.g. `uv run python …`, `uv run --with X python …`). The model
 *     must use `uv run script.py` (PEP 723 inline deps), `uv run --with pkg
 *     script.py`, or `uv run --with pkg - <<'PY'`.
 *   - `resources_discover` registers the co-located `SKILL.md` so the skill is
 *     discovered alongside this extension (same layout as chatgpt-web-review).
 *
 * Detection is command-position based so `grep python`, `cat python-uv.ts`,
 * `which python`, `echo python` etc. are NOT blocked.
 */

const STANDING_RULE = `## Python execution policy
Run Python only through \`uv\`. Never invoke \`python\` or \`python3\` directly (those calls are blocked) — including under \`uv run … python\`, which is redundant.
- Script with inline deps (preferred): add a PEP 723 \`# /// script\` block and run \`uv run ./script.py\`.
- One-off deps: \`uv run --with <pkg> ./script.py\`.
- Stdin snippet: \`uv run --with <pkg> - <<'PY' … PY\`.
Load the \`python-uv\` skill for templates and details.`;

const BLOCK_REASON = `Python must run through \`uv\`, not \`python\`/\`python3\` (including \`uv run … python\`).
Use \`uv run ./script.py\` (PEP 723 \`# /// script\` deps header), \`uv run --with <pkg> ./script.py\`, or \`uv run --with <pkg> - <<'PY'\`.
Load the \`python-uv\` skill for the exact forms.`;

// Words that, when preceding `python` (possibly with flags/numbers between),
// mean python is the *invoked program*: `sudo python`, `env … python`,
// `timeout 10 python`, `… | python`, `&& python`, etc.
const COMMAND_PREFIXES = new Set([
	"sudo",
	"env",
	"time",
	"timeout",
	"nice",
	"ionice",
	"nohup",
	"command",
	"exec",
	"xargs",
	"strace",
	"perf",
	"do",
	"then",
	"catch",
	"pi",
]);

// Standalone separator tokens that mark command position within a segment
// (single `|`, `&`, redirects). Multi-char `&&`/`||` and `;`/newline/`()`
// are handled by the segment split below.
const SEPARATOR_TOKENS = new Set([
	"|",
	"&",
	"<",
	">",
	"<<",
	">>",
	"|&",
]);

/**
 * Walk backwards from index i over "skip-worthy" tokens (numeric args or
 * `-`-flags like `-E`, `--no-sync`, `10`) and return the first real word.
 * Returns null at the start of the segment.
 *
 * This lets `timeout 10 python`, `sudo -E python`, `grep -r python` classify
 * correctly: the first two invoke python (the real word behind the flags is
 * `timeout`/`sudo`), the third does not (`grep`).
 */
function prevCommandWord(tokens: string[], i: number): string | null {
	let j = i - 1;
	while (j >= 0) {
		const t = tokens[j];
		const skipWorthy =
			t.length > 0 &&
			(t[0] === "-" || /^[0-9]+$/.test(t) || /^[A-Za-z_][A-Za-z0-9_]*=/.test(t));
		if (!skipWorthy) return t;
		j--;
	}
	return null;
}

/**
 * True if `command` executes `python`/`python3` as a program:
 *   - in command position (segment start, or after a separator / known
 *     command-prefix like sudo/timeout/env/…), or
 *   - as the program passed to `uv run` (any `python` token after a
 *     `uv run` in the same segment — forces the script-file form).
 *
 * False for bare-argument uses: `grep python`, `cat python-uv.ts`,
 * `which python`, `echo python`, `uv run ./script.py`.
 *
 * Quote/escape handling is deliberately light. Agent commands put spaces
 * around tokens in practice, and quoted strings like `"python"` or `'python'`
 * don't match the exact `python3?` token, so they are naturally ignored.
 */
function pythonInvoked(command: string): boolean {
	// Split into pipeline/list segments on top-level separators.
	// Single `|` and `&` stay inside a segment as tokens so we can detect
	// `echo x | python` (python after a pipe == command position).
	const segments = command.split(/&&|\|\||[;\n()]/);
	for (const seg of segments) {
		const tokens = seg.trim().split(/\s+/).filter(Boolean);
		if (tokens.length === 0) continue;

		// Does this segment contain `uv … run`? If so, any `python` token
		// after `run` is the program handed to uv → block (force script form).
		let uvRunAt = -1;
		for (let k = 1; k < tokens.length; k++) {
			if (tokens[k] === "run" && tokens[k - 1] === "uv") {
				uvRunAt = k;
				break;
			}
		}

		for (let i = 0; i < tokens.length; i++) {
			const t = tokens[i];
			if (t !== "python" && t !== "python3") continue;

			// Program under `uv run` in this segment.
			if (uvRunAt >= 0 && i > uvRunAt) return true;

			// Command position: start of segment, or behind only flags/numbers.
			const pw = prevCommandWord(tokens, i);
			if (pw === null) return true;

			// After a pipe / redirect / background separator.
			if (SEPARATOR_TOKENS.has(pw)) return true;

			// After a command prefix that chains to a new command.
			if (COMMAND_PREFIXES.has(pw)) return true;

			// Otherwise python is an argument (grep, cat, which, echo, …).
		}
	}
	return false;
}

export default function (pi: ExtensionAPI) {
	// Register the co-located skill so it is discovered alongside this
	// extension (mirrors extensions/chatgpt-web-review/index.ts).
	pi.on("resources_discover", () => ({
		skillPaths: [path.join(EXTENSION_DIR, "SKILL.md")],
	}));

	// Proactive: inject the standing policy into the system prompt each turn,
	// before the model writes any command.
	pi.on("before_agent_start", (event) => {
		return {
			systemPrompt: event.systemPrompt + "\n\n" + STANDING_RULE,
		};
	});

	// Reactive backstop: block agent bash tool calls that execute python.
	pi.on("tool_call", (event) => {
		if (!isToolCallEventType("bash", event)) return;
		if (pythonInvoked(event.input.command)) {
			return { block: true, reason: BLOCK_REASON };
		}
	});

	// Reactive backstop: block user-entered ! / !! bash commands that execute python.
	pi.on("user_bash", (event) => {
		if (!pythonInvoked(event.command)) return;
		return {
			result: {
				output: BLOCK_REASON,
				exitCode: 1,
				cancelled: false,
				truncated: false,
			},
		};
	});
}
