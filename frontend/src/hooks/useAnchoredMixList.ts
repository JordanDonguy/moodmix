import { useRef } from "react";
import type { Mix } from "../types/mix";

/**
 * Composes the displayed mix list from the currently playing mix + the fetched
 * search results, keeping card positions stable across search transitions.
 *
 * Behavior:
 * - If `currentMix` isn't in `fetchedMixes`, it's prepended at position 0
 *   (so the user can always see/control what's playing).
 * - When the playing mix stops being prepended (user plays a mix that *is* in
 *   the results), dropping it from position 0 would shift every card up by one.
 *   Instead, the last fetched mix gets "anchored" at position 0 — positions
 *   1..N stay stable, and the anchor mix is normally off-screen in the
 *   infinite-scroll list.
 * - Once set, the anchor persists across re-renders and pagination. It's
 *   cleared when the user starts prepending again, when the anchor falls out
 *   of the fetched results, or when the user plays the anchor itself.
 */
export function useAnchoredMixList(
	currentMix: Mix | null,
	fetchedMixes: Mix[],
): Mix[] {
	const anchorRef = useRef<Mix | null>(null);
	const wasPrependingRef = useRef(false);

	const isCurrentInFetched = currentMix
		? fetchedMixes.some((m) => m.id === currentMix.id)
		: false;
	const shouldPrepend = !!currentMix && !isCurrentInFetched;

	// Capture the anchor on the prepending → not-prepending transition.
	if (wasPrependingRef.current && !shouldPrepend && fetchedMixes.length > 0) {
		anchorRef.current = fetchedMixes[fetchedMixes.length - 1];
	}
	// Clear the anchor when we start prepending again (stale).
	if (shouldPrepend) anchorRef.current = null;
	// Drop the anchor if it's no longer available or would duplicate currentMix.
	if (
		anchorRef.current &&
		(!fetchedMixes.some((m) => m.id === anchorRef.current?.id) ||
			anchorRef.current.id === currentMix?.id)
	) {
		anchorRef.current = null;
	}
	wasPrependingRef.current = shouldPrepend;

	if (shouldPrepend && currentMix) {
		return [currentMix, ...fetchedMixes];
	}
	if (anchorRef.current) {
		const anchor = anchorRef.current;
		return [anchor, ...fetchedMixes.filter((m) => m.id !== anchor.id)];
	}
	return fetchedMixes;
}
