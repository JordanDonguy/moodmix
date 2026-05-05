import { create } from "zustand";
import type { Mix } from "../types/mix";

interface PlayerState {
	currentMix: Mix | null;
	queue: Mix[];
	queueIndex: number;
	isPlaying: boolean;
	currentTime: number;
	duration: number;

	/**
	 * True when `currentMix` has been hydrated from the resume-playback
	 * pointer but the user hasn't pressed play yet ("State A"). The iframe
	 * stays idle, the mix card isn't prepended to the grid, and the
	 * PlayerBar shows the saved progress as if the player were paused.
	 *
	 * Flips to false on any explicit play action — `playMix`, `next`, `prev`,
	 * or `resume()` — at which point the iframe loads the video at the saved
	 * seconds and the card is anchored normally ("State B").
	 */
	hydratedFromResume: boolean;

	playMix: (mix: Mix, queue?: Mix[]) => void;
	pause: () => void;
	resume: () => void;
	next: () => void;
	prev: () => void;
	skipChapter: (dir: "next" | "prev") => void;
	volume: number;
	muted: boolean;
	pendingSeek: number | null;
	seekTo: (time: number) => void;
	setProgress: (currentTime: number, duration: number) => void;
	setIsPlaying: (v: boolean) => void;
	setVolume: (v: number) => void;
	toggleMute: () => void;
	playerContainer: HTMLDivElement | null;
	setPlayerContainer: (el: HTMLDivElement | null) => void;

	/**
	 * Hydrate the player from a saved resume pointer. Sets `currentMix`,
	 * seeds `currentTime`, leaves `isPlaying` false, and flags
	 * `hydratedFromResume` so the iframe-load and grid-anchoring effects
	 * stay quiet until the user hits play.
	 */
	hydrateFromResume: (mix: Mix, secondsListened: number) => void;
}

export const usePlayerStore = create<PlayerState>()((set, get) => ({
	currentMix: null,
	queue: [],
	queueIndex: 0,
	isPlaying: false,
	currentTime: 0,
	duration: 0,
	hydratedFromResume: false,

	playMix: (mix, queue) => {
		const q = queue ?? [mix];
		const idx = q.findIndex((m) => m.id === mix.id);
		set({
			currentMix: mix,
			queue: q,
			queueIndex: idx >= 0 ? idx : 0,
			isPlaying: true,
			currentTime: 0,
			duration: mix.duration_seconds,
			hydratedFromResume: false,
		});
	},

	pause: () => set({ isPlaying: false }),
	resume: () => set({ isPlaying: true, hydratedFromResume: false }),

	next: () => {
		const { queue, queueIndex } = get();
		const nextIdx = queueIndex + 1;
		if (nextIdx < queue.length) {
			const mix = queue[nextIdx];
			set({
				currentMix: mix,
				queueIndex: nextIdx,
				isPlaying: true,
				currentTime: 0,
				duration: mix.duration_seconds,
				hydratedFromResume: false,
			});
		}
	},

	prev: () => {
		const { queue, queueIndex } = get();
		const prevIdx = queueIndex - 1;
		if (prevIdx >= 0) {
			const mix = queue[prevIdx];
			set({
				currentMix: mix,
				queueIndex: prevIdx,
				isPlaying: true,
				currentTime: 0,
				duration: mix.duration_seconds,
				hydratedFromResume: false,
			});
		}
	},

	skipChapter: (dir) => {
		const { currentMix, currentTime, duration } = get();
		if (!currentMix) return;
		const chapters = currentMix.chapters;

		if (dir === "next") {
			if (chapters && chapters.length > 0) {
				const next = chapters.find((c) => c.time > currentTime + 1);
				if (next) {
					set({ currentTime: next.time, pendingSeek: next.time });
				} else {
					get().next();
				}
			} else {
				const t = Math.min(currentTime + 180, duration);
				set({ currentTime: t, pendingSeek: t });
			}
		} else {
			if (chapters && chapters.length > 0) {
				const currentChapterIdx = chapters.reduce(
					(best, c, i) => (c.time <= currentTime ? i : best),
					-1,
				);
				if (
					currentChapterIdx >= 0 &&
					currentTime - chapters[currentChapterIdx].time > 3
				) {
					const t = chapters[currentChapterIdx].time;
					set({ currentTime: t, pendingSeek: t });
				} else if (currentChapterIdx > 0) {
					const t = chapters[currentChapterIdx - 1].time;
					set({ currentTime: t, pendingSeek: t });
				} else {
					set({ currentTime: 0, pendingSeek: 0 });
				}
			} else {
				const t = Math.max(currentTime - 180, 0);
				set({ currentTime: t, pendingSeek: t });
			}
		}
	},

	volume: 80,
	muted: false,
	pendingSeek: null,
	seekTo: (time) => set({ currentTime: time, pendingSeek: time }),
	setProgress: (currentTime, duration) => set({ currentTime, duration }),
	setIsPlaying: (v) => set({ isPlaying: v }),
	setVolume: (v) => set({ volume: v, muted: v === 0 }),
	toggleMute: () => set((s) => ({ muted: !s.muted })),
	playerContainer: null,
	setPlayerContainer: (el) => set({ playerContainer: el }),

	hydrateFromResume: (mix, secondsListened) =>
		set({
			currentMix: mix,
			queue: [mix],
			queueIndex: 0,
			isPlaying: false,
			currentTime: secondsListened,
			duration: mix.duration_seconds,
			hydratedFromResume: true,
		}),
}));
