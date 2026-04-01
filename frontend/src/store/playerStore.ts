import { create } from "zustand";
import type { Mix } from "../types/mix";

interface PlayerState {
	currentMix: Mix | null;
	queue: Mix[];
	queueIndex: number;
	isPlaying: boolean;
	currentTime: number;
	duration: number;

	playMix: (mix: Mix, queue?: Mix[]) => void;
	pause: () => void;
	resume: () => void;
	next: () => void;
	prev: () => void;
	setProgress: (currentTime: number, duration: number) => void;
	setIsPlaying: (v: boolean) => void;
}

export const usePlayerStore = create<PlayerState>()((set, get) => ({
	currentMix: null,
	queue: [],
	queueIndex: 0,
	isPlaying: false,
	currentTime: 0,
	duration: 0,

	playMix: (mix, queue) => {
		const q = queue ?? [mix];
		const idx = q.findIndex((m) => m.id === mix.id);
		set({
			currentMix: mix,
			queue: q,
			queueIndex: idx >= 0 ? idx : 0,
			isPlaying: true,
			currentTime: 0,
		});
	},

	pause: () => set({ isPlaying: false }),
	resume: () => set({ isPlaying: true }),

	next: () => {
		const { queue, queueIndex } = get();
		const nextIdx = queueIndex + 1;
		if (nextIdx < queue.length) {
			set({
				currentMix: queue[nextIdx],
				queueIndex: nextIdx,
				isPlaying: true,
				currentTime: 0,
			});
		}
	},

	prev: () => {
		const { queue, queueIndex, currentTime } = get();
		// If more than 3s in, restart current; otherwise go to previous
		if (currentTime > 3) {
			set({ currentTime: 0 });
			return;
		}
		const prevIdx = queueIndex - 1;
		if (prevIdx >= 0) {
			set({
				currentMix: queue[prevIdx],
				queueIndex: prevIdx,
				isPlaying: true,
				currentTime: 0,
			});
		}
	},

	setProgress: (currentTime, duration) => set({ currentTime, duration }),
	setIsPlaying: (v) => set({ isPlaying: v }),
}));
