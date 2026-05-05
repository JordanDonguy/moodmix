import { useEffect, useRef } from "react";
import { ApiError } from "../../api/client";
import { getMix } from "../../api/mixes";
import { putPlaybackState } from "../../api/playback";
import { localPlaybackRepo } from "../../lib/playback/localPlaybackRepo";
import { useAuthStore } from "../../store/authStore";
import { usePlayerStore } from "../../store/playerStore";
import type { Mix } from "../../types/mix";
import { usePlaybackRepo } from "./usePlaybackRepo";

/**
 * On app mount (after auth has hydrated), read the resume-playback pointer
 * from whichever backend applies (server for authed, localStorage for anon)
 * and seed the player store into "State A" — mix metadata + saved seconds,
 * but no iframe load and no card prepended to the grid.
 *
 * Authed users get an extra migration step first: any localStorage state
 * (from a prior anon session, including the one that was active right
 * before an OAuth round-trip) is pushed to the server and cleared locally,
 * then the read happens. This is the only place that handles the
 * post-OAuth-reload migration — by the time this hook fires, the user
 * has already gone null → set during initial auth hydrate, so a separate
 * "transition listener" wouldn't see the change.
 *
 * Edge cases handled:
 *   - No saved state → noop
 *   - Saved mix has been removed / marked unavailable → silently clear the
 *     pointer so the next session starts clean
 *   - Saved seconds > duration → tolerated by the iframe's seek-on-load
 *   - Migration POST fails → localStorage left intact for retry next reload
 */
export function useResumePlaybackOnMount() {
	const repo = usePlaybackRepo();
	const hydrated = useAuthStore((s) => s.hydrated);
	// One-shot: don't re-fire after sign-in or sign-out within the same session
	const ranRef = useRef(false);

	useEffect(() => {
		if (!hydrated || ranRef.current) return;
		ranRef.current = true;

		(async () => {
			// If the user is authed and localStorage has leftover state from
			// a prior anon session (typically from before an OAuth redirect),
			// promote it to the server before we read. We always prefer the
			// localStorage value here — it's the most recent thing this
			// device actually played, and "I just listened to X, sign in,
			// remember X" is the natural user expectation.
			if (useAuthStore.getState().user !== null) {
				const local = localPlaybackRepo.get();
				if (local) {
					try {
						await putPlaybackState({
							mix_id: local.mix_id,
							seconds_listened: local.seconds_listened,
						});
						localPlaybackRepo.clear();
					} catch {
						// Best-effort; leave localStorage intact so a later
						// reload can retry.
					}
				}
			}

			const state = await repo.get();
			if (!state) return;

			let mix: Mix;
			try {
				mix = await getMix(state.mix_id);
			} catch (err) {
				if (
					err instanceof ApiError &&
					(err.status === 404 || err.status === 410)
				) {
					// Mix is gone — clear the stale pointer so we don't keep
					// trying on every reload.
					await repo.clear();
					return;
				}
				// Network or unknown error — leave state alone, try again next reload.
				return;
			}

			usePlayerStore.getState().hydrateFromResume(mix, state.seconds_listened);
		})();
	}, [hydrated, repo]);
}
