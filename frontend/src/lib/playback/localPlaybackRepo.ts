import type { PlaybackState } from "../../api/playback";

const STORAGE_KEY = "moodmix:playback";
const TTL_MS = 5 * 24 * 60 * 60 * 1000; // 5 days, matches backend

/**
 * localStorage-backed copy of the resume-playback pointer for anonymous
 * users. Same shape as the server response so the resolver hook can swap
 * backends without consumers caring.
 */
export const localPlaybackRepo = {
	get(): PlaybackState | null {
		if (typeof window === "undefined") return null;
		const raw = window.localStorage.getItem(STORAGE_KEY);
		if (!raw) return null;
		try {
			const parsed = JSON.parse(raw) as PlaybackState;
			if (!parsed.mix_id || !parsed.updated_at) return null;
			// Read-time TTL filter — same policy as the server.
			const updatedMs = Date.parse(parsed.updated_at);
			if (Number.isNaN(updatedMs) || Date.now() - updatedMs > TTL_MS) {
				return null;
			}
			return parsed;
		} catch {
			return null;
		}
	},

	put(payload: { mix_id: string; seconds_listened: number }): PlaybackState {
		const state: PlaybackState = {
			mix_id: payload.mix_id,
			seconds_listened: payload.seconds_listened,
			updated_at: new Date().toISOString(),
		};
		if (typeof window !== "undefined") {
			window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		}
		return state;
	},

	clear(): void {
		if (typeof window === "undefined") return;
		window.localStorage.removeItem(STORAGE_KEY);
	},
} as const;
