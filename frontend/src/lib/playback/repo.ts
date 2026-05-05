import {
	clearPlaybackState,
	getPlaybackState,
	type PlaybackState,
	type PlaybackStatePayload,
	putPlaybackState,
} from "../../api/playback";
import { localPlaybackRepo } from "./localPlaybackRepo";

/**
 * Common surface for both backends. The auth-aware hook below resolves
 * to one or the other so consumers (hydrate-on-mount, throttled writer,
 * pagehide flusher) never branch on auth state themselves.
 */
export interface PlaybackRepo {
	get(): Promise<PlaybackState | null>;
	put(payload: PlaybackStatePayload): Promise<PlaybackState>;
	clear(): Promise<void>;
}

/** Server-backed repo — used for authenticated users. */
export const serverPlaybackRepo: PlaybackRepo = {
	get: getPlaybackState,
	put: putPlaybackState,
	clear: clearPlaybackState,
};

/** Local-storage-backed repo wrapped to match the async interface. */
export const anonPlaybackRepo: PlaybackRepo = {
	async get() {
		return localPlaybackRepo.get();
	},
	async put(payload) {
		return localPlaybackRepo.put(payload);
	},
	async clear() {
		localPlaybackRepo.clear();
	},
};
