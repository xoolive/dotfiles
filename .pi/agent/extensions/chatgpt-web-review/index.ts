import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EXTENSION_DIR = path.dirname(fileURLToPath(import.meta.url));
// Default: the robust browser path. Env override keeps the (broken) replay
// experiment reachable for diagnosis.
const UV = process.env["CHATGPT_WEB_REVIEW_UV"] ?? "uv";
const REVIEW_SCRIPT =
  process.env["CHATGPT_WEB_REVIEW_SCRIPT"] ??
  path.join(EXTENSION_DIR, "scripts", "browser_review.py");
const HISTORY_SCRIPT = path.join(EXTENSION_DIR, "scripts", "history.py");

export default function (pi: ExtensionAPI) {
  pi.on("resources_discover", () => ({
    skillPaths: [path.join(EXTENSION_DIR, "SKILL.md")],
  }));

  pi.registerTool({
    name: "chatgpt_web_review",
    label: "ChatGPT web repo review",
    description:
      "Request a repository review through the logged-in ChatGPT web UI, or list/fetch " +
      "existing review conversations after a local timeout. Repository uploads include " +
      "git-tracked files only and pass a secret pre-scan. Authentication is seeded from " +
      "the user's real Firefox profile.",
    parameters: Type.Object({
      action: Type.Optional(
        StringEnum(["review", "list-history", "fetch-history"] as const),
      ),
      repoPath: Type.Optional(Type.String({
        description: "Absolute repository path (required for action=review).",
      })),
      conversation: Type.Optional(Type.String({
        description: "Conversation URL, /c/path, or ID for action=fetch-history.",
      })),
      prompt: Type.Optional(
        Type.String({
          description: "Custom review prompt. Defaults to a structured security/bugs/arch/maint review.",
        }),
      ),
      headless: Type.Optional(
        Type.Boolean({
          description:
            "Run the browser headless. Default false (headed is more reliable against bot detection). " +
            "Headed requires a display; the agent typically runs headless — set true for in-session runs.",
        }),
      ),
      setup: Type.Optional(
        Type.Boolean({
          description:
            "One-time: open a headed browser so you can log into ChatGPT and persist the profile. " +
            "Needs a display; run this yourself in a terminal, not via the agent.",
        }),
      ),
      dryRun: Type.Optional(
        Type.Boolean({
          description: "Open the profile, report whether logged in, and exit without sending.",
        }),
      ),
      maxWaitSeconds: Type.Optional(
        Type.Integer({
          minimum: 1,
          description: "Local wait for a new review before history recovery is required.",
        }),
      ),
    }),
    // Signature must match ExtensionAPI.ToolDefinition.execute:
    //   (toolCallId, params, signal, onUpdate, ctx)
    // A previous version used (toolCallId, params, onUpdate, _ctx, signal), so pi
    // passed the AbortSignal into `onUpdate` and the call below threw
    // "onUpdate is not a function". onUpdate is also optional (| undefined),
    // so calls are guarded with optional chaining.
    async execute(toolCallId, params, signal, onUpdate, _ctx) {
      const action = params.action ?? "review";
      const args = [UV, "run", action === "review" ? REVIEW_SCRIPT : HISTORY_SCRIPT];

      if (action === "list-history") {
        args.push("--list");
      } else if (action === "fetch-history") {
        if (!params.conversation) {
          throw new Error("conversation is required for action=fetch-history");
        }
        args.push("--conversation", params.conversation);
      } else if (params.setup) {
        args.push("--setup");
      } else {
        if (!params.repoPath && !params.dryRun) {
          throw new Error("repoPath is required for action=review");
        }
        if (params.repoPath) args.push("--repo", path.resolve(params.repoPath));
        if (params.prompt) args.push("--prompt", params.prompt);
        if (params.headless) args.push("--headless");
        if (params.maxWaitSeconds) {
          args.push("--max-wait", String(params.maxWaitSeconds));
        }
      }
      if (params.dryRun && action === "review" && !params.setup) args.push("--dry-run");

      onUpdate?.({ content: [{ type: "text", text: `▶ ${args.join(" ")}` }] });

      const stdoutChunks: Buffer[] = [];
      let stderrBuf = "";
      let lastProgress = 0;

      const child = spawn(args[0]!, args.slice(1), {
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
      });

      signal?.addEventListener("abort", () => {
        try {
          child.kill("SIGTERM");
        } catch {
          /* ignore */
        }
      });

      child.stdout.on("data", (c: Buffer) => stdoutChunks.push(c));
      child.stderr.on("data", (c: Buffer) => {
        stderrBuf += c.toString("utf8");
        const now = Date.now();
        if (now - lastProgress > 200) {
          lastProgress = now;
          const lastLine = stderrBuf.split("\n").filter(Boolean).slice(-1)[0] ?? "";
          if (lastLine) {
            onUpdate?.({ content: [{ type: "text", text: lastLine }] });
          }
        }
      });

      const code: number | null = await new Promise((resolve) =>
        child.on("close", (c) => resolve(c)),
      );
      const stdout = Buffer.concat(stdoutChunks).toString("utf8");

      if (code === 0) {
        const text = stdout.trim();
        return {
          content: [
            {
              type: "text",
              text:
                text ||
                "[chatgpt_web_review] completed but produced no output. " +
                "Re-run with a manual `uv run scripts/browser_review.py --repo <p> --dump-dom` to inspect.",
            },
          ],
          details: { dryRun: !!params.dryRun, setup: !!params.setup },
        };
      }

      const tail = stderrBuf.trim().split("\n").slice(-14).join("\n");
      return {
        content: [
          {
            type: "text",
            text:
              `[chatgpt_web_review] exited with code ${code}.\n` +
              `--- stderr (tail) ---\n${tail || "(empty)"}`,
          },
        ],
        details: { error: true, code },
      };
    },
  });
}
