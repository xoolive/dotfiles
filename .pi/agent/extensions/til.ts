/**
 * TIL (Today I Learned) Extension
 *
 * /til <topic>  — create or recall a TIL note
 *
 * Behaviour:
 *  - file doesn't exist → ask the LLM to write it from current session context
 *  - file exists, topic not yet discussed in this session → display the note
 *  - file exists, topic was discussed in this session → display + offer to improve
 *
 * Notes live in ~/.pi/agent/til/<slug>.md
 * /til offers tab-completion for existing notes
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { AutocompleteItem } from "@earendil-works/pi-tui";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const TIL_DIR = join(homedir(), ".pi", "agent", "til");

// ── helpers ────────────────────────────────────────────────────────────────

function ensureDir(): void {
    mkdirSync(TIL_DIR, { recursive: true });
}

function listSlugs(): string[] {
    try {
        ensureDir();
        return readdirSync(TIL_DIR)
            .filter((f) => f.endsWith(".md"))
            .map((f) => f.slice(0, -3))
            .sort();
    } catch {
        return [];
    }
}

/** Slugify a topic name: lowercase, spaces → hyphens */
function slugify(topic: string): string {
    return topic.toLowerCase().replace(/\s+/g, "-");
}

/** Return true if the topic keyword appears anywhere in the current session branch */
function topicMentionedInSession(
    entries: readonly unknown[],
    topic: string,
): boolean {
    const needle = topic.toLowerCase();

    for (const entry of entries as Array<{ type: string; message?: unknown; content?: unknown }>) {
        if (entry.type !== "message") continue;

        const msg = entry.message as {
            role?: string;
            content?: unknown;
            toolName?: string;
        } | undefined;
        if (!msg) continue;

        // Check content: string | TextContent[] | mixed[]
        if (contentContains(msg.content, needle)) return true;
    }
    return false;
}

function contentContains(content: unknown, needle: string): boolean {
    if (typeof content === "string") return content.toLowerCase().includes(needle);
    if (Array.isArray(content)) {
        return content.some((part) => {
            if (typeof part === "string") return part.toLowerCase().includes(needle);
            if (part && typeof part === "object") {
                const t = (part as Record<string, unknown>).text;
                if (typeof t === "string") return t.toLowerCase().includes(needle);
            }
            return false;
        });
    }
    return false;
}

// ── extension ─────────────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
    pi.registerCommand("til", {
        description: "Record or recall a Today I Learned note. Usage: /til <topic>",

        // Tab-completion: existing .md files in TIL_DIR
        getArgumentCompletions: (prefix: string): AutocompleteItem[] | null => {
            const slugs = listSlugs();
            const items: AutocompleteItem[] = slugs.map((s) => ({
                value: s,
                label: s,
                description: `~/.pi/agent/til/${s}.md`,
            }));
            const filtered = items.filter((i) => i.value.startsWith(prefix));
            return filtered.length > 0 ? filtered : null;
        },

        handler: async (args, ctx) => {
            const topic = args?.trim();
            const today = new Date().toISOString().slice(0, 10);

            // /til with no args → list existing notes
            if (!topic) {
                const slugs = listSlugs();
                if (slugs.length === 0) {
                    ctx.ui.notify("No TIL notes yet. Use /til <topic> to create one.", "info");
                } else {
                    ctx.ui.notify(`TIL notes: ${slugs.join("  ·  ")}`, "info");
                }
                return;
            }

            const slug = slugify(topic);
            const filePath = join(TIL_DIR, `${slug}.md`);

            // ── Case 1: note doesn't exist yet ────────────────────────────
            if (!existsSync(filePath)) {
                ensureDir();
                pi.sendUserMessage(
                    `Write a TIL (Today I Learned) note about **${topic}** ` +
                        `and save it to \`${filePath}\`.\n\n` +
                        `Start the file with exactly:\n` +
                        `\`\`\`\n# TIL: ${topic}\n\n**Date:** ${today}\n\`\`\`\n\n` +
                        `Then write the body from our current conversation. Include:\n` +
                        `- **Background / context** — why we looked into this\n` +
                        `- **What it is** — a clear explanation of ${topic}\n` +
                        `- **Key finding or fix** — the actionable insight\n` +
                        `- **Commands / examples** — anything concrete that came up\n\n` +
                        `Use \`## \` section headers. Keep it dense and practical — ` +
                        `this is a personal reference note, not a tutorial.`,
                );
                return;
            }

            // ── Cases 2 & 3: note already exists ─────────────────────────
            const existing = readFileSync(filePath, "utf-8");
            const discussed = topicMentionedInSession(ctx.sessionManager.getBranch(), topic);

            if (!discussed) {
                // Case 2: topic not in this session — just surface the note
                pi.sendMessage(
                    {
                        customType: "til",
                        content:
                            `📝 **TIL note found:** \`${filePath}\`\n\n` +
                            `---\n\n${existing}`,
                        display: true,
                    },
                    { deliverAs: "followUp" },
                );
                return;
            }

            // Case 3: topic was discussed — show it and offer to improve
            pi.sendMessage(
                {
                    customType: "til",
                    content:
                        `📝 **You already have a TIL note on this topic:** \`${filePath}\`\n\n` +
                        `---\n\n${existing}`,
                    display: true,
                },
                { deliverAs: "followUp" },
            );

            const wantsUpdate = await ctx.ui.confirm(
                `Update TIL: ${slug}`,
                "We discussed this topic in the current session. Improve the note with new context?",
            );

            if (!wantsUpdate) return;

            const hint = await ctx.ui.input(
                "What to add or change?",
                "e.g. add the ufw fix, clarify the root cause…",
            );

            pi.sendUserMessage(
                `Update the TIL note at \`${filePath}\` about **${topic}**.\n\n` +
                    `Existing content:\n\`\`\`markdown\n${existing}\n\`\`\`\n\n` +
                    `Based on our current session discussion: ` +
                    `${hint || "add anything relevant we discovered"}.\n\n` +
                    `Rules:\n` +
                    `- Keep the \`# TIL:\` header and \`**Date:**\` line unchanged\n` +
                    `- Expand or correct sections as needed\n` +
                    `- You may add a \`## Updates\` section if it keeps things cleaner\n` +
                    `- Stay dense and practical`,
            );
        },
    });
}
