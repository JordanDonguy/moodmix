export interface ArtistListItem {
	id: string;
	name: string;
	image_url: string | null;
	spotify_id: string | null;
	deezer_id: string | null;
	resolution_tier: string | null;
	genres: string[] | null;
	track_count: number;
}

export interface ArtistListResponse {
	artists: ArtistListItem[];
	total: number;
	limit: number;
	offset: number;
}

export interface TrackItem {
	id: string;
	title: string;
	isrc: string | null;
	deezer_id: string | null;
	duration_ms: number | null;
	release_date: string | null;
	preview_url: string | null;
	status: string;
	raw_genres: string[] | null;
}

export interface ArtistTracksResponse {
	artist_id: string;
	artist_name: string;
	tracks: TrackItem[];
	total: number;
}

export interface FreshPreviewResponse {
	track_id: string;
	preview_url: string | null;
}
