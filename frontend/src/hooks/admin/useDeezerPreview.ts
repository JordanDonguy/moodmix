import { useRef, useState } from "react";
import { getFreshPreview } from "../../api/admin";
import type { TrackItem } from "../../types/catalog";

/**
 * Manage a single audio element + the currently-previewing track.
 *
 * Deezer preview URLs are signed CDN links that expire (~24h), so we don't
 * persist them — every play fetches a fresh URL from the backend.
 */
export function useDeezerPreview(apiKey: string) {
	const audioRef = useRef<HTMLAudioElement>(null);
	const [track, setTrack] = useState<TrackItem | null>(null);

	async function play(next: TrackItem | null) {
		const audio = audioRef.current;
		if (!next) {
			audio?.pause();
			setTrack(null);
			return;
		}
		audio?.pause();
		setTrack(next);
		if (!audio || !next.deezer_id) return;

		try {
			const fresh = await getFreshPreview(apiKey, next.id);
			if (fresh.preview_url) {
				audio.src = fresh.preview_url;
				audio.load();
				await audio.play();
			}
		} catch {
			// Fetch or playback failed — user can click again.
		}
	}

	function clear() {
		audioRef.current?.pause();
		setTrack(null);
	}

	return { audioRef, track, play, clear };
}
