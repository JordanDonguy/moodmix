import type { ArtistListItem } from "../../types/catalog";

export function ArtistRow({
	artist,
	selected,
	onClick,
}: {
	artist: ArtistListItem;
	selected: boolean;
	onClick: () => void;
}) {
	return (
		<button
			type="button"
			onClick={onClick}
			className={`w-full text-left px-3 py-2.5 rounded transition-colors ${
				selected
					? "bg-accent/20 text-text-primary"
					: "hover:bg-bg-elevated text-text-secondary hover:text-text-primary"
			}`}
		>
			<div className="flex items-center justify-between gap-2">
				<span className="truncate text-sm">{artist.name}</span>
				<span className="text-xs text-text-muted shrink-0">{artist.track_count}</span>
			</div>
			{artist.resolution_tier && (
				<div className="text-xs text-text-muted mt-0.5">{artist.resolution_tier}</div>
			)}
		</button>
	);
}
