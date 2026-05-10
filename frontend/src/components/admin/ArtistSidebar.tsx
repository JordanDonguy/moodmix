import type { ArtistListItem } from "../../types/catalog";
import { ArtistRow } from "./ArtistRow";
import { Pagination } from "./Pagination";

export function ArtistSidebar({
	search,
	onSearchChange,
	artists,
	loading,
	error,
	total,
	totalPages,
	currentPage,
	selectedArtistId,
	onSelect,
	onPageJump,
}: {
	search: string;
	onSearchChange: (s: string) => void;
	artists: ArtistListItem[];
	loading: boolean;
	error: string | null;
	total: number;
	totalPages: number;
	currentPage: number;
	selectedArtistId: string | null;
	onSelect: (artist: ArtistListItem) => void;
	onPageJump: (page: number) => void;
}) {
	return (
		<aside className="w-64 border-r border-border flex flex-col shrink-0 bg-bg-secondary">
			<div className="p-3 border-b border-border">
				<input
					type="search"
					value={search}
					onChange={(e) => onSearchChange(e.target.value)}
					placeholder="Search artists…"
					className="w-full bg-bg-elevated border border-border rounded px-3 py-1.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent"
				/>
			</div>

			{error && <p className="text-red-400 text-xs px-3 py-2">{error}</p>}

			<div className="flex-1 overflow-y-auto p-2 space-y-0.5">
				{loading ? (
					<p className="text-text-muted text-sm text-center py-4">Loading…</p>
				) : (
					artists.map((a) => (
						<ArtistRow
							key={a.id}
							artist={a}
							selected={selectedArtistId === a.id}
							onClick={() => onSelect(a)}
						/>
					))
				)}
			</div>

			{totalPages > 1 && (
				<Pagination
					currentPage={currentPage}
					totalPages={totalPages}
					onJump={onPageJump}
				/>
			)}

			<div className="border-t border-border px-3 py-1.5 text-xs text-text-muted">
				{total} artist{total !== 1 ? "s" : ""}
			</div>
		</aside>
	);
}
