import type { TrackItem } from "../../types/catalog";
import { formatDurationMs } from "../../utils/time";

export function TrackTable({
	tracks,
	previewTrackId,
	onPreview,
}: {
	tracks: TrackItem[];
	previewTrackId: string | null;
	onPreview: (track: TrackItem | null) => void;
}) {
	if (tracks.length === 0) {
		return (
			<p className="text-text-muted text-sm py-8 text-center">No tracks found.</p>
		);
	}

	return (
		<div className="overflow-x-auto">
			<table className="w-full text-sm border-collapse">
				<thead>
					<tr className="border-b border-border text-text-muted text-left">
						<th className="py-2 pr-4 font-medium">Title</th>
						<th className="py-2 pr-4 font-medium">Duration</th>
						<th className="py-2 pr-4 font-medium">Status</th>
						<th className="py-2 pr-4 font-medium">Genres</th>
						<th className="py-2 font-medium">Preview</th>
					</tr>
				</thead>
				<tbody>
					{tracks.map((t) => {
						const hasPreview = !!(t.deezer_id || t.preview_url);
						const isPlaying = previewTrackId === t.id;
						return (
							<tr
								key={t.id}
								onClick={hasPreview ? () => onPreview(isPlaying ? null : t) : undefined}
								className={`border-b border-border/50 transition-colors ${
									hasPreview ? "cursor-pointer hover:bg-bg-elevated" : ""
								} ${isPlaying ? "bg-accent/10" : ""}`}
							>
								<td className="py-2 pr-4 text-text-primary max-w-xs truncate">
									{t.title}
								</td>
								<td className="py-2 pr-4 text-text-secondary tabular-nums">
									{formatDurationMs(t.duration_ms)}
								</td>
								<td className="py-2 pr-4">
									<span
										className={`text-xs px-1.5 py-0.5 rounded ${
											t.status === "active"
												? "bg-green-900/50 text-green-400"
												: t.status === "excluded"
													? "bg-red-900/50 text-red-400"
													: "bg-bg-elevated text-text-muted"
										}`}
									>
										{t.status}
									</span>
								</td>
								<td className="py-2 pr-4 text-text-muted text-xs max-w-xs truncate">
									{t.raw_genres?.join(", ") ?? "—"}
								</td>
								<td className="py-2">
									{hasPreview ? (
										<span
											className={`text-xs px-2 py-0.5 rounded ${
												isPlaying
													? "bg-accent/20 text-accent"
													: "bg-bg-elevated text-text-secondary"
											}`}
										>
											{isPlaying ? "■ stop" : "▶ play"}
										</span>
									) : (
										<span className="text-text-muted text-xs">—</span>
									)}
								</td>
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
}
