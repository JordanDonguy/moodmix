import type { RefObject } from "react";
import type { TrackItem } from "../../types/catalog";

/**
 * Persistent player bar pinned to the bottom of the admin layout.
 *
 * The audio element is *always mounted* (just hidden when no track is loaded)
 * so the parent's audioRef is populated before the first click — letting
 * play() run synchronously inside the user-gesture context.
 */
export function DeezerPlayerBar({
	audioRef,
	track,
	artistName,
	onClose,
}: {
	audioRef: RefObject<HTMLAudioElement | null>;
	track: TrackItem | null;
	artistName: string;
	onClose: () => void;
}) {
	return (
		<div
			className={`border-t border-border bg-bg-secondary px-4 py-2 flex items-center gap-4 shrink-0 ${
				track ? "" : "hidden"
			}`}
		>
			<div className="flex flex-col min-w-0 w-48 shrink-0">
				<span className="text-text-primary text-sm truncate">{track?.title ?? ""}</span>
				<span className="text-text-muted text-xs truncate">{artistName}</span>
			</div>

			<div className="flex-1">
				{/* biome-ignore lint/a11y/useMediaCaption: 30s preview clip */}
				<audio ref={audioRef} controls className="w-full h-8" />
			</div>

			<button
				type="button"
				onClick={onClose}
				className="text-text-muted hover:text-text-primary transition-colors shrink-0 text-lg leading-none"
				aria-label="Close player"
			>
				✕
			</button>
		</div>
	);
}
