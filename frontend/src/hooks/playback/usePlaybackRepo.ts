import { useMemo } from "react";
import {
	anonPlaybackRepo,
	type PlaybackRepo,
	serverPlaybackRepo,
} from "../../lib/playback/repo";
import { useAuthStore } from "../../store/authStore";

/**
 * Pick the right resume-playback backend based on the user's auth state.
 *
 * Authenticated → server (cross-device).
 * Anonymous → localStorage (single-device, migrates to server on sign-in).
 *
 * The hook returns a stable reference per backend so consumers can safely
 * include it in dependency arrays.
 */
export function usePlaybackRepo(): PlaybackRepo {
	const isAuthenticated = useAuthStore((s) => s.user !== null);
	return useMemo(
		() => (isAuthenticated ? serverPlaybackRepo : anonPlaybackRepo),
		[isAuthenticated],
	);
}
