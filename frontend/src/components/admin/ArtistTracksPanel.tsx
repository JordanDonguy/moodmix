import type { ArtistListItem, TrackItem } from "../../types/catalog";
import { TrackTable } from "./TrackTable";

export function ArtistTracksPanel({
	artist,
	tracks,
	totalTracks,
	loading,
	previewTrackId,
	onPreview,
}: {
	artist: ArtistListItem | null;
	tracks: TrackItem[];
	totalTracks: number;
	loading: boolean;
	previewTrackId: string | null;
	onPreview: (track: TrackItem | null) => void;
}) {
	if (!artist) {
		return (
			<main className="flex-1 overflow-y-auto p-6">
				<div className="flex items-center justify-center h-full text-text-muted">
					Select an artist to browse tracks
				</div>
			</main>
		);
	}

	return (
		<main className="flex-1 overflow-y-auto p-6">
			<div className="mb-4">
				<h2 className="text-text-primary text-xl font-semibold">{artist.name}</h2>
				<div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
					{artist.resolution_tier && (
						<span className="px-1.5 py-0.5 rounded bg-bg-elevated">
							{artist.resolution_tier}
						</span>
					)}
					{artist.genres?.slice(0, 4).map((g) => (
						<span key={g}>{g}</span>
					))}
					<span className="ml-auto">{totalTracks} tracks</span>
				</div>
			</div>

			{loading ? (
				<p className="text-text-muted text-sm py-8 text-center">Loading tracks…</p>
			) : (
				<TrackTable
					tracks={tracks}
					previewTrackId={previewTrackId}
					onPreview={onPreview}
				/>
			)}
		</main>
	);
}
