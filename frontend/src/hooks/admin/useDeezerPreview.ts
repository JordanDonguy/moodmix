import { useRef, useState } from "react";
import { getFreshPreview } from "../../api/admin";
import type { TrackItem } from "../../types/catalog";

/**
 * Manage a single audio element + the currently-previewing track.
 *
 * Deezer preview URLs are signed CDN links that expire (~24h). We optimistically
 * play the cached URL first — when it's fresh that keeps play() inside the
 * user-gesture context and avoids a roundtrip — and on failure fetch a fresh
 * URL from Deezer and retry.
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

		const tryPlay = (url: string) => {
			audio.src = url;
			audio.load();
			return audio.play();
		};

		try {
			if (next.preview_url) {
				await tryPlay(next.preview_url);
				return;
			}
			throw new Error("no cached url");
		} catch {
			try {
				const fresh = await getFreshPreview(apiKey, next.id);
				if (fresh.preview_url) {
					await tryPlay(fresh.preview_url);
				}
			} catch {
				// Both cached and fresh playback failed — user can click again.
			}
		}
	}

	function clear() {
		audioRef.current?.pause();
		setTrack(null);
	}

	return { audioRef, track, play, clear };
}
