/**
 * Remote session sync.
 *
 * `/sync <remote>` finds the newest Pi session on an SSH host whose cwd is
 * the remote-home equivalent of the current local cwd, copies it into a local
 * cache, forks it into the current project's session directory, and loads it.
 *
 * Example:
 *   local  /Users/me/Documents/code/project
 *   remote /home/me/Documents/code/project
 *
 * Requirements:
 *   - Key-based SSH authentication
 *   - `node` available to non-interactive SSH commands on the remote host
 */

import { SessionManager, getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { link, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, relative, resolve, sep } from "node:path";

const SSH_TIMEOUT_MS = 60_000;
const MAX_SESSION_BYTES = 100 * 1024 * 1024;
const MAX_STDERR_BYTES = 64 * 1024;
const META_MARKER = "PI_SYNC_META_V1 ";

interface RemoteSessionMetadata {
	remoteCwd: string;
	sourcePath: string;
	modifiedMs: number;
}

interface DownloadedSession {
	metadata: RemoteSessionMetadata;
	content: Buffer;
}

interface SessionHeader {
	type: "session";
	id: string;
	cwd: string;
	version?: number;
}

function parseRemote(value: string): string {
	const remote = value.trim();
	if (!remote) throw new Error("Usage: /sync <remote>");
	if (remote.startsWith("-") || /[\s\0]/.test(remote)) {
		throw new Error("Remote must be a single SSH host or user@host without options");
	}
	return remote;
}

function homeRelativeCwd(cwd: string): string {
	const localHome = resolve(homedir());
	const localCwd = resolve(cwd);
	const mapped = relative(localHome, localCwd);
	if (mapped === ".." || mapped.startsWith(`..${sep}`) || isAbsolute(mapped)) {
		throw new Error(`Current directory is outside the local home directory: ${localCwd}`);
	}
	return mapped.split(sep).join("/");
}

function remoteHelper(relativeCwd: string): string {
	return String.raw`
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const relativeCwd = ${JSON.stringify(relativeCwd)};
const marker = ${JSON.stringify(META_MARKER)};
const home = os.homedir();

function expandPath(value, base = process.cwd()) {
  if (value === "~") return home;
  if (value.startsWith("~/")) return path.join(home, value.slice(2));
  return path.resolve(base, value);
}

function readSettingsFile(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return {};
  }
}

function collectJsonl(root) {
  const files = [];
  const pending = [root];
  while (pending.length > 0) {
    const dir = pending.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) pending.push(file);
      else if (entry.isFile() && entry.name.endsWith(".jsonl")) files.push(file);
    }
  }
  return files;
}

function readHeader(file) {
  let fd;
  try {
    fd = fs.openSync(file, "r");
    const buffer = Buffer.alloc(64 * 1024);
    const count = fs.readSync(fd, buffer, 0, buffer.length, 0);
    const newline = buffer.indexOf(10, 0);
    if (newline < 0 || newline >= count) return null;
    const header = JSON.parse(buffer.subarray(0, newline).toString("utf8"));
    if (header.type !== "session" || typeof header.id !== "string" || typeof header.cwd !== "string") return null;
    return header;
  } catch {
    return null;
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}

function fail(message, code) {
  process.stderr.write("pi-sync: " + message + "\n");
  process.exit(code);
}

const remoteCwd = path.resolve(home, relativeCwd);
const agentDir = expandPath(process.env.PI_CODING_AGENT_DIR || path.join(home, ".pi", "agent"), remoteCwd);
const globalSettings = readSettingsFile(path.join(agentDir, "settings.json"));
const projectSettings = readSettingsFile(path.join(remoteCwd, ".pi", "settings.json"));
const configuredSessionDir = process.env.PI_CODING_AGENT_SESSION_DIR || projectSettings.sessionDir || globalSettings.sessionDir;
const sessionsRoot = expandPath(configuredSessionDir || path.join(agentDir, "sessions"), remoteCwd);

let newest = null;
for (const file of collectJsonl(sessionsRoot)) {
  const header = readHeader(file);
  if (!header || path.resolve(header.cwd) !== remoteCwd) continue;
  let stat;
  try {
    stat = fs.statSync(file);
  } catch {
    continue;
  }
  if (!newest || stat.mtimeMs > newest.modifiedMs) {
    newest = { sourcePath: file, modifiedMs: stat.mtimeMs };
  }
}

if (!newest) fail("no Pi session found for " + remoteCwd, 4);

const maxSessionBytes = ${MAX_SESSION_BYTES};
let content;
for (let attempt = 0; attempt < 3; attempt++) {
  const before = fs.statSync(newest.sourcePath);
  if (before.size > maxSessionBytes) fail("session exceeds the " + (maxSessionBytes / 1024 / 1024) + " MiB limit", 6);
  content = fs.readFileSync(newest.sourcePath);
  const after = fs.statSync(newest.sourcePath);
  if (
    before.size === after.size &&
    before.mtimeMs === after.mtimeMs &&
    content.length === after.size &&
    content.length <= maxSessionBytes &&
    content.length > 0 &&
    content[content.length - 1] === 10
  ) break;
  content = undefined;
}
if (!content) fail("session changed while being copied: " + newest.sourcePath, 5);

process.stdout.write(marker + JSON.stringify({
  remoteCwd,
  sourcePath: newest.sourcePath,
  modifiedMs: newest.modifiedMs,
}) + "\n");
process.stdout.write(content);
`;
}

function downloadLatestSession(remote: string, relativeCwd: string): Promise<DownloadedSession> {
	return new Promise((resolvePromise, rejectPromise) => {
		const child = spawn(
			"ssh",
			["-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--", remote, "node", "-"],
			{ stdio: ["pipe", "pipe", "pipe"] },
		);
		const stdout: Buffer[] = [];
		const stderr: Buffer[] = [];
		let stdoutBytes = 0;
		let stderrBytes = 0;
		let stderrTruncated = false;
		let settled = false;
		let overflow = false;
		let killTimer: ReturnType<typeof setTimeout> | undefined;

		const finish = (error?: Error, result?: DownloadedSession) => {
			if (settled) return;
			settled = true;
			clearTimeout(timer);
			if (error) rejectPromise(error);
			else resolvePromise(result!);
		};

		const timer = setTimeout(() => {
			child.kill("SIGTERM");
			killTimer = setTimeout(() => child.kill("SIGKILL"), 2_000);
			finish(new Error(`SSH timed out after ${SSH_TIMEOUT_MS / 1000} seconds`));
		}, SSH_TIMEOUT_MS);

		child.stdout.on("data", (chunk: Buffer) => {
			stdoutBytes += chunk.length;
			if (stdoutBytes > MAX_SESSION_BYTES + 64 * 1024) {
				overflow = true;
				child.kill("SIGTERM");
				return;
			}
			stdout.push(chunk);
		});
		child.stderr.on("data", (chunk: Buffer) => {
			const remaining = MAX_STDERR_BYTES - stderrBytes;
			if (remaining > 0) {
				const kept = chunk.subarray(0, remaining);
				stderr.push(kept);
				stderrBytes += kept.length;
			}
			if (chunk.length > remaining) stderrTruncated = true;
		});
		child.on("error", (error) => finish(error));
		child.stdin.on("error", () => {
			// The close/error handler reports the useful SSH failure.
		});
		child.on("close", (code) => {
			if (killTimer) clearTimeout(killTimer);
			if (settled) return;
			if (overflow) {
				finish(new Error(`Remote session exceeds the ${MAX_SESSION_BYTES / 1024 / 1024} MiB limit`));
				return;
			}
			if (code !== 0) {
				let detail = Buffer.concat(stderr).toString("utf8").trim();
				if (stderrTruncated) detail += `${detail ? "\n" : ""}[stderr truncated at ${MAX_STDERR_BYTES} bytes]`;
				finish(new Error(`SSH failed (${code ?? "signal"})${detail ? `: ${detail}` : ""}`));
				return;
			}

			try {
				const output = Buffer.concat(stdout);
				const marker = Buffer.from(META_MARKER);
				const markerIndex = output.indexOf(marker);
				if (markerIndex < 0 || (markerIndex > 0 && output[markerIndex - 1] !== 10)) {
					throw new Error("Remote helper returned no session metadata (is node available remotely?)");
				}
				const metadataEnd = output.indexOf(10, markerIndex);
				if (metadataEnd < 0) throw new Error("Remote helper returned incomplete metadata");
				const metadata = JSON.parse(output.subarray(markerIndex + marker.length, metadataEnd).toString("utf8"));
				if (
					typeof metadata?.remoteCwd !== "string" ||
					typeof metadata?.sourcePath !== "string" ||
					typeof metadata?.modifiedMs !== "number"
				) {
					throw new Error("Remote helper returned invalid metadata");
				}
				const content = output.subarray(metadataEnd + 1);
				finish(undefined, { metadata, content });
			} catch (error) {
				finish(error instanceof Error ? error : new Error(String(error)));
			}
		});

		child.stdin.end(remoteHelper(relativeCwd));
	});
}

function validateSession(download: DownloadedSession): SessionHeader {
	if (download.content.length === 0 || download.content.length > MAX_SESSION_BYTES) {
		throw new Error("Downloaded session is empty or too large");
	}
	const newline = download.content.indexOf(10);
	if (newline < 0) throw new Error("Downloaded session has no JSONL header");

	let header: unknown;
	try {
		header = JSON.parse(download.content.subarray(0, newline).toString("utf8"));
	} catch {
		throw new Error("Downloaded session has an invalid JSON header");
	}
	if (
		typeof header !== "object" ||
		header === null ||
		(header as Partial<SessionHeader>).type !== "session" ||
		typeof (header as Partial<SessionHeader>).id !== "string" ||
		typeof (header as Partial<SessionHeader>).cwd !== "string"
	) {
		throw new Error("Downloaded file is not a valid Pi session");
	}
	const sessionHeader = header as SessionHeader;
	if (resolve(sessionHeader.cwd) !== resolve(download.metadata.remoteCwd)) {
		throw new Error("Downloaded session cwd does not match the requested remote directory");
	}
	return sessionHeader;
}

async function cacheSession(remote: string, download: DownloadedSession): Promise<string> {
	const remoteKey = createHash("sha256").update(remote).digest("hex").slice(0, 16);
	const contentKey = createHash("sha256").update(download.content).digest("hex").slice(0, 16);
	const sourceStem = basename(download.metadata.sourcePath).replace(/\.jsonl$/i, "");
	const cachePath = resolve(getAgentDir(), "sync-cache", remoteKey, `${sourceStem}-${contentKey}.jsonl`);
	const temporaryPath = `${cachePath}.tmp-${process.pid}-${randomUUID()}`;
	await mkdir(dirname(cachePath), { recursive: true });
	try {
		await writeFile(temporaryPath, download.content, { flag: "wx", mode: 0o600 });
		try {
			await link(temporaryPath, cachePath);
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
			const existing = await readFile(cachePath);
			if (!existing.equals(download.content)) throw new Error("Session cache hash collision or corruption");
		}
	} finally {
		await rm(temporaryPath, { force: true });
	}
	return cachePath;
}

export default function syncExtension(pi: ExtensionAPI) {
	pi.registerCommand("sync", {
		description: "Copy and load the latest matching Pi session from an SSH host",
		handler: async (args, ctx) => {
			await ctx.waitForIdle();

			let remote: string;
			let relativeCwd: string;
			try {
				remote = parseRemote(args);
				relativeCwd = homeRelativeCwd(ctx.cwd);
			} catch (error) {
				ctx.ui.notify(error instanceof Error ? error.message : String(error), "warning");
				return;
			}

			ctx.ui.setStatus("sync", `Syncing from ${remote}…`);
			let localSessionPath: string;
			let remoteCwd: string;
			try {
				const download = await downloadLatestSession(remote, relativeCwd);
				validateSession(download);
				const cachedSource = await cacheSession(remote, download);
				const localSession = SessionManager.forkFrom(
					cachedSource,
					ctx.cwd,
					ctx.sessionManager.getSessionDir() || undefined,
				);
				const sessionFile = localSession.getSessionFile();
				if (!sessionFile) throw new Error("Pi did not create a local session file");
				localSessionPath = sessionFile;
				remoteCwd = download.metadata.remoteCwd;
			} catch (error) {
				ctx.ui.setStatus("sync", undefined);
				ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
				return;
			}
			ctx.ui.setStatus("sync", undefined);

			const result = await ctx.switchSession(localSessionPath, {
				withSession: async (newCtx) => {
					newCtx.ui.notify(`Synced ${remote}:${remoteCwd} into ${newCtx.cwd}`, "info");
					newCtx.ui.setTitle(`pi - ${newCtx.cwd}`);
				},
			});
			if (result.cancelled) {
				await rm(localSessionPath, { force: true });
				ctx.ui.notify("Session sync cancelled", "info");
			}
		},
	});
}
