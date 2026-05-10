import { useEffect } from "react";
import { AdminHeader } from "../../components/admin/AdminHeader";
import { ArtistSidebar } from "../../components/admin/ArtistSidebar";
import { ArtistTracksPanel } from "../../components/admin/ArtistTracksPanel";
import { DeezerPlayerBar } from "../../components/admin/DeezerPlayerBar";
import { KeyGate } from "../../components/admin/KeyGate";
import { useAdminAuth } from "../../hooks/admin/useAdminAuth";
import { useArtistList } from "../../hooks/admin/useArtistList";
import { useArtistTracks } from "../../hooks/admin/useArtistTracks";
import { useDeezerPreview } from "../../hooks/admin/useDeezerPreview";

export default function AdminPage() {
	const { apiKey, setKey, signOut } = useAdminAuth();
	const list = useArtistList(apiKey);
	const tracks = useArtistTracks(apiKey);
	const preview = useDeezerPreview(apiKey);

	// When the search term changes, the visible artist set changes — drop any
	// selection / preview that may no longer make sense.
	// biome-ignore lint/correctness/useExhaustiveDependencies: we only want to reset when the search changes.
	useEffect(() => {
		tracks.clear();
		preview.clear();
	}, [list.search]);

	if (!apiKey) return <KeyGate onKey={setKey} />;

	return (
		<div className="h-screen bg-bg-primary flex flex-col overflow-hidden">
			<AdminHeader onSignOut={signOut} />

			<div className="flex flex-1 overflow-hidden">
				<ArtistSidebar
					search={list.search}
					onSearchChange={list.setSearch}
					artists={list.artists}
					loading={list.loading}
					error={list.error}
					total={list.total}
					totalPages={list.totalPages}
					currentPage={list.currentPage}
					selectedArtistId={tracks.selectedArtist?.id ?? null}
					onSelect={tracks.select}
					onPageJump={list.goToPage}
				/>

				<ArtistTracksPanel
					artist={tracks.selectedArtist}
					tracks={tracks.tracks}
					totalTracks={tracks.total}
					loading={tracks.loading}
					previewTrackId={preview.track?.id ?? null}
					onPreview={preview.play}
				/>
			</div>

			<DeezerPlayerBar
				audioRef={preview.audioRef}
				track={preview.track}
				artistName={tracks.selectedArtist?.name ?? ""}
				onClose={preview.clear}
			/>
		</div>
	);
}
