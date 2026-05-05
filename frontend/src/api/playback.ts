import { ApiError, apiFetch } from "./client";

export interface PlaybackState {
	mix_id: string;
	seconds_listened: number;
	updated_at: string;
}

export interface PlaybackStatePayload {
	mix_id: string;
	seconds_listened: number;
}

/** Fetch the user's resume-playback pointer. Returns null on 404 (no state). */
export async function getPlaybackState(): Promise<PlaybackState | null> {
	try {
		return await apiFetch<PlaybackState>("/api/playback/state");
	} catch (err) {
		if (err instanceof ApiError && err.status === 404) return null;
		throw err;
	}
}

/** Upsert the user's resume pointer. */
export function putPlaybackState(
	payload: PlaybackStatePayload,
): Promise<PlaybackState> {
	return apiFetch<PlaybackState>("/api/playback/state", {
		method: "PUT",
		body: JSON.stringify(payload),
	});
}

/** Clear the user's resume pointer (used when the saved mix has gone unavailable). */
export function clearPlaybackState(): Promise<void> {
	return apiFetch<void>("/api/playback/state", { method: "DELETE" });
}

/** URL the throttled-write `sendBeacon` posts to. Same shape as `putPlaybackState`. */
export const PLAYBACK_STATE_URL =
	(import.meta.env.VITE_API_URL ?? "http://localhost:8000") +
	"/api/playback/state";
