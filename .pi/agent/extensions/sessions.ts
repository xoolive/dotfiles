/**
 * Sessions extension.
 *
 * Adds /sessions: list all pi sessions, reload one with Enter, remove one with x.
 * Switching uses pi's session switch flow, so the replacement session restores its
 * recorded cwd from the session header.
 */

import { SessionManager, type ExtensionAPI, type ExtensionCommandContext, type SessionInfo } from "@earendil-works/pi-coding-agent";
import { DynamicBorder } from "@earendil-works/pi-coding-agent";
import { Container, Key, matchesKey, SelectList, type SelectItem, truncateToWidth } from "@earendil-works/pi-tui";
import { mkdir, rename, rm } from "node:fs/promises";
import { basename, join } from "node:path";
import { homedir } from "node:os";

interface SessionChoice {
	action: "open" | "delete";
	session: SessionInfo;
	filter: string;
	cursorIndex: number;
}

function formatRelativeDate(date: Date): string {
	const elapsed = Date.now() - date.getTime();
	const minute = 60 * 1000;
	const hour = 60 * minute;
	const day = 24 * hour;

	if (elapsed < minute) return "just now";
	if (elapsed < hour) return `${Math.floor(elapsed / minute)}m ago`;
	if (elapsed < day) return `${Math.floor(elapsed / hour)}h ago`;
	if (elapsed < 7 * day) return `${Math.floor(elapsed / day)}d ago`;

	return date.toLocaleString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function oneLine(text: string | undefined, fallback = "Untitled session"): string {
	const cleaned = (text ?? "").replace(/\s+/g, " ").trim();
	return cleaned || fallback;
}

function displayName(session: SessionInfo): string {
	return oneLine(session.name ?? session.firstMessage);
}

function formatExactDate(date: Date): string {
	return date.toLocaleString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function sessionDescription(session: SessionInfo): string {
	const parts = [
		`${formatExactDate(session.modified)} (${formatRelativeDate(session.modified)})`,
		`${session.messageCount} msg${session.messageCount === 1 ? "" : "s"}`,
		session.cwd || "unknown cwd",
	];
	return parts.join(" • ");
}

async function listSessions(): Promise<SessionInfo[]> {
	const sessions = await SessionManager.listAll();
	return sessions.sort((a, b) => b.modified.getTime() - a.modified.getTime());
}

async function moveSessionToTrash(file: string): Promise<void> {
	const trashDir = join(homedir(), ".Trash");
	try {
		await mkdir(trashDir, { recursive: true });
		await rename(file, join(trashDir, `${Date.now()}-${basename(file)}`));
	} catch {
		// Fall back to permanent removal when ~/.Trash is unavailable (non-macOS,
		// cross-device rename, permissions, etc.).
		await rm(file, { force: true });
	}
}

async function chooseSession(
	ctx: ExtensionCommandContext,
	sessions: SessionInfo[],
	initialFilter = "",
	initialCursorIndex = 0,
): Promise<SessionChoice | null> {
	const byPath = new Map(sessions.map((session) => [session.path, session]));
	const items: SelectItem[] = sessions.map((session) => ({
		value: session.path,
		label: displayName(session),
		description: sessionDescription(session),
	}));

	return await ctx.ui.custom<SessionChoice | null>((tui, theme, _keybindings, done) => {
		const container = new Container();
		container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));
		let filterMode = false;
		let filter = initialFilter;

		container.addChild({
			render(width: number) {
				const filterText = filterMode || filter ? ` • filter: /${filter}${filterMode ? "_" : ""}` : "";
				return [
					truncateToWidth(theme.fg("accent", theme.bold("Sessions")) + theme.fg("muted", filterText), width),
					truncateToWidth(theme.fg("dim", "j/k or ↑↓ navigate • / filter • enter reload/cd • x remove • esc close"), width),
				];
			},
			invalidate() {},
		});

		const selectList = new SelectList(
			items,
			Math.min(Math.max(items.length, 1), 18),
			{
				selectedPrefix: (text: string) => theme.fg("accent", text),
				selectedText: (text: string) => theme.fg("accent", text),
				description: (text: string) => theme.fg("muted", text),
				scrollInfo: (text: string) => theme.fg("dim", text),
				noMatch: (text: string) => theme.fg("warning", text),
			},
			{
				minPrimaryColumnWidth: 20,
				maxPrimaryColumnWidth: 56,
			},
		);

		const getMutableSelectList = () =>
			selectList as unknown as { items: SelectItem[]; filteredItems: SelectItem[]; selectedIndex: number };

		const getCursorIndex = () => getMutableSelectList().selectedIndex;

		const applyFilter = (cursorIndex = 0) => {
			const query = filter.trim().toLowerCase();
			const filteredItems = query
				? items.filter((item) => {
						const session = byPath.get(item.value);
						if (!session) return false;
						return [displayName(session), session.cwd, session.path, session.firstMessage]
							.join(" ")
							.toLowerCase()
							.includes(query);
					})
				: items;

			const mutableSelectList = getMutableSelectList();
			mutableSelectList.items = filteredItems;
			mutableSelectList.filteredItems = filteredItems;
			selectList.setSelectedIndex(cursorIndex);
			selectList.invalidate();
		};

		const moveSelection = (delta: number) => {
			const mutableSelectList = getMutableSelectList();
			const count = mutableSelectList.filteredItems.length;
			if (count === 0) return;
			mutableSelectList.selectedIndex = (mutableSelectList.selectedIndex + delta + count) % count;
			selectList.invalidate();
		};

		applyFilter(initialCursorIndex);

		selectList.onSelect = (item) => {
			const session = byPath.get(item.value);
			if (session) done({ action: "open", session, filter, cursorIndex: getCursorIndex() });
		};
		selectList.onCancel = () => done(null);
		container.addChild(selectList);
		container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));

		return {
			render(width: number) {
				return container.render(width);
			},
			invalidate() {
				container.invalidate();
			},
			handleInput(data: string) {
				if (filterMode) {
					if (matchesKey(data, Key.enter)) {
						filterMode = false;
						tui.requestRender();
						return;
					}
					if (matchesKey(data, Key.escape)) {
						if (filter) {
							filter = "";
							applyFilter();
						} else {
							filterMode = false;
						}
						tui.requestRender();
						return;
					}
					if (matchesKey(data, Key.backspace)) {
						filter = filter.slice(0, -1);
						applyFilter();
						tui.requestRender();
						return;
					}
					if (data.length === 1 && data >= " ") {
						filter += data;
						applyFilter();
						tui.requestRender();
						return;
					}
				}

				if (matchesKey(data, "/")) {
					filterMode = true;
					filter = "";
					applyFilter();
					tui.requestRender();
					return;
				}
				if (matchesKey(data, Key.enter)) {
					const selected = selectList.getSelectedItem();
					const session = selected ? byPath.get(selected.value) : undefined;
					if (session) done({ action: "open", session, filter, cursorIndex: getCursorIndex() });
					return;
				}
				if (matchesKey(data, "x")) {
					const selected = selectList.getSelectedItem();
					const session = selected ? byPath.get(selected.value) : undefined;
					if (session) done({ action: "delete", session, filter, cursorIndex: getCursorIndex() });
					return;
				}
				if (data === "j") {
					moveSelection(1);
					tui.requestRender();
					return;
				}
				if (data === "k") {
					moveSelection(-1);
					tui.requestRender();
					return;
				}
				selectList.handleInput(data);
				tui.requestRender();
			},
		};
	});
}

export default function sessionsExtension(pi: ExtensionAPI) {
	pi.registerCommand("sessions", {
		description: "List, reload, cd to, or remove pi sessions",
		handler: async (_args, ctx) => {
			await ctx.waitForIdle();

			if (!ctx.hasUI) {
				ctx.ui.notify("/sessions requires interactive UI", "warning");
				return;
			}

			let currentFilter = "";
			let currentCursorIndex = 0;
			while (true) {
				const sessions = await listSessions();
				if (sessions.length === 0) {
					ctx.ui.notify("No sessions found", "info");
					return;
				}

				const choice = await chooseSession(ctx, sessions, currentFilter, currentCursorIndex);
				if (!choice) return;
				currentFilter = choice.filter;
				currentCursorIndex = choice.cursorIndex;

				if (choice.action === "delete") {
					const current = ctx.sessionManager.getSessionFile();
					if (current === choice.session.path) {
						ctx.ui.notify("Cannot remove the currently loaded session", "warning");
						continue;
					}

					await moveSessionToTrash(choice.session.path);
					ctx.ui.notify("Session removed", "info");
					continue;
				}

				const result = await ctx.switchSession(choice.session.path, {
					withSession: async (newCtx) => {
						newCtx.ui.notify(`Reloaded session in ${newCtx.cwd}`, "info");
						newCtx.ui.setTitle(`pi - ${newCtx.cwd}`);
					},
				});
				if (result.cancelled) {
					ctx.ui.notify("Session reload cancelled", "info");
				}
				return;
			}
		},
	});
}
