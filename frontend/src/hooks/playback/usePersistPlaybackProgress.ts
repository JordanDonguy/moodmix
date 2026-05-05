import { useEffect, useRef } from "react";
import { PLAYBACK_STATE_URL } from "../../api/playback";
import { localPlaybackRepo } from "../../lib/playback/localPlaybackRepo";
import { useAuthStore } from "../../store/authStore";
import { usePlayerStore } from "../../store/playerStore";
import { usePlaybackRepo } from "./usePlaybackRepo";

const THROTTLE_MS = 30 * 1000; // every 30s

/**
 * Persist the user's playback progress so they can resume on next visit.
 *
 * Three triggers:
 *   1. Throttled — every ~30s while a mix is playing (background drift).
 *   2. Mix change — write the previous mix's final seconds before swapping
 *      so we never lose context across track skips.
 *   3. Pagehide — final flush. Authenticated users use `navigator.sendBeacon`
 *      so the request survives the unload; anonymous users write to
 *      localStorage synchronously.
 *
 * State A (`hydratedFromResume`) is skipped — that's the user looking at
 * a saved pointer they haven't acted on; rewriting it would just re-stamp
 * the same value with a new `updated_at`.
 */
export function usePersistPlaybackProgress() {
	const repo = usePlaybackRepo();
	const isAuthenticated = useAuthStore((s) => s.user !== null);
	const lastWriteRef = useRef(0);
	const lastMixIdRef = useRef<string | null>(null);

	// Throttled background write while playing.
	useEffect(() => {
		const interval = window.setInterval(() => {
			const { currentMix, currentTime, isPlaying, hydratedFromResume } =
				usePlayerStore.getState();
			if (!currentMix || !isPlaying || hydratedFromResume) return;
			if (Date.now() - lastWriteRef.current < THROTTLE_MS) return;

			void repo.put({
				mix_id: currentMix.id,
				seconds_listened: Math.floor(currentTime),
			});
			lastWriteRef.current = Date.now();
			lastMixIdRef.current = currentMix.id;
		}, 5000); // poll every 5s; the THROTTLE_MS gate decides when to actually write

		return () => window.clearInterval(interval);
	}, [repo]);

	// Immediate write on mix change. The resume pointer follows "what the
	// user is listening to now" — the moment a new mix takes over, the
	// pointer should reflect it, even if the throttle window hasn't elapsed.
	useEffect(() => {
		const unsub = usePlayerStore.subscribe((state, prev) => {
			if (state.hydratedFromResume) return;
			if (state.currentMix && prev.currentMix?.id !== state.currentMix.id) {
				void repo.put({
					mix_id: state.currentMix.id,
					seconds_listened: Math.floor(state.currentTime),
				});
				lastWriteRef.current = Date.now();
				lastMixIdRef.current = state.currentMix.id;
			}
		});
		return unsub;
	}, [repo]);

	// Final flush on pagehide.
	useEffect(() => {
		const handlePageHide = () => {
			const { currentMix, currentTime, hydratedFromResume } =
				usePlayerStore.getState();
			if (!currentMix || hydratedFromResume) return;

			const payload = {
				mix_id: currentMix.id,
				seconds_listened: Math.floor(currentTime),
			};

			if (isAuthenticated) {
				// `fetch({ keepalive: true })` survives page unload AND honours
				// CORS preflight — unlike `sendBeacon`, which silently drops
				// non-CORS-simple bodies (application/json triggers preflight,
				// which sendBeacon can't do, so the request never goes out
				// cross-origin in dev).
				fetch(PLAYBACK_STATE_URL, {
					method: "PUT",
					credentials: "include",
					keepalive: true,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(payload),
				}).catch(() => {
					// Best-effort — a failed pagehide flush only loses the last
					// ~30s of progress; throttled writes already saved earlier
					// values during the session.
				});
			} else {
				// Anonymous — synchronous localStorage write always succeeds.
				localPlaybackRepo.put(payload);
			}
		};

		window.addEventListener("pagehide", handlePageHide);
		return () => window.removeEventListener("pagehide", handlePageHide);
	}, [isAuthenticated]);
}
