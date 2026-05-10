import { useState } from "react";
import { getArtistTracks } from "../../api/admin";
import type { ArtistListItem, TrackItem } from "../../types/catalog";

export function useArtistTracks(apiKey: string) {
	const [selectedArtist, setSelectedArtist] = useState<ArtistListItem | null>(null);
	const [tracks, setTracks] = useState<TrackItem[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function select(artist: ArtistListItem) {
		setSelectedArtist(artist);
		setLoading(true);
		setTracks([]);
		setError(null);
		try {
			const res = await getArtistTracks(apiKey, artist.id);
			setTracks(res.tracks);
			setTotal(res.total);
		} catch {
			setError("Failed to load tracks.");
		} finally {
			setLoading(false);
		}
	}

	function clear() {
		setSelectedArtist(null);
		setTracks([]);
		setTotal(0);
	}

	return { selectedArtist, tracks, total, loading, error, select, clear };
}
