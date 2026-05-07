import type { Mix } from "../../types/mix";

/**
 * Pick the next mix to play after `current`, prioritizing genre overlap and
 * mood-vector closeness.
 *
 * Three-tier fallback:
 *   1. Exact genre set match (same genres, same count). If multiple, the
 *      candidate closest to `current` in mood-vector space (Euclidean) wins.
 *   2. At least one genre in common. Ranked by overlap count first (more
 *      shared genres = better), then by mood-vector closeness as tie-breaker.
 *   3. No genre overlap (or current has no genres) — pick the mood-vector
 *      closest from anything available.
 *
 * Excluded from candidates: the current mix itself, anything in `playedIds`,
 * and unclassified mixes (mood/energy/instrumentation null). Returns null
 * when no eligible candidate exists.
 */
export function computeNextMix(
	current: Mix,
	available: Mix[],
	playedIds: ReadonlySet<string>,
): Mix | null {
	const eligible = available.filter(
		(m) =>
			m.id !== current.id &&
			!playedIds.has(m.id) &&
			m.mood !== null &&
			m.energy !== null &&
			m.instrumentation !== null,
	);
	if (eligible.length === 0) return null;

	const currentGenreIds = new Set(current.genres.map((g) => g.id));
	const currentSize = currentGenreIds.size;

	// Tier 1: exact set match (same genres, same count).
	if (currentSize > 0) {
		const exact = eligible.filter(
			(m) =>
				m.genres.length === currentSize &&
				m.genres.every((g) => currentGenreIds.has(g.id)),
		);
		if (exact.length > 0) return pickClosest(current, exact);
	}

	// Tier 2: any overlap, ranked by overlap count (then closeness).
	if (currentSize > 0) {
		const withOverlap: { mix: Mix; overlap: number }[] = [];
		for (const m of eligible) {
			const overlap = m.genres.reduce(
				(n, g) => n + (currentGenreIds.has(g.id) ? 1 : 0),
				0,
			);
			if (overlap > 0) withOverlap.push({ mix: m, overlap });
		}
		if (withOverlap.length > 0) {
			const max = withOverlap.reduce(
				(m, x) => (x.overlap > m ? x.overlap : m),
				0,
			);
			const top = withOverlap
				.filter((x) => x.overlap === max)
				.map((x) => x.mix);
			return pickClosest(current, top);
		}
	}

	// Tier 3: genre-agnostic fallback.
	return pickClosest(current, eligible);
}

function pickClosest(current: Mix, candidates: Mix[]): Mix {
	let best = candidates[0];
	let bestDist = distance(current, best);
	for (let i = 1; i < candidates.length; i++) {
		const d = distance(current, candidates[i]);
		if (d < bestDist) {
			best = candidates[i];
			bestDist = d;
		}
	}
	return best;
}

/**
 * Euclidean (L2) distance in 3D mood space — same metric the backend uses
 * for slider-driven search. Treats unclassified axes as 0; in practice,
 * `eligible` filters those out before we get here.
 */
function distance(a: Mix, b: Mix): number {
	const dm = (a.mood ?? 0) - (b.mood ?? 0);
	const de = (a.energy ?? 0) - (b.energy ?? 0);
	const di = (a.instrumentation ?? 0) - (b.instrumentation ?? 0);
	return Math.sqrt(dm * dm + de * de + di * di);
}
