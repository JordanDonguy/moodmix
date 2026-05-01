import { usePlayerStore } from "../../store/playerStore";

export default function NowPlayingInfo({ compact = false }: { compact?: boolean }) {
	const currentMix = usePlayerStore((s) => s.currentMix);

	const thumbnail = currentMix
		? (currentMix.thumbnail_url ??
			`https://i.ytimg.com/vi/${currentMix.youtube_id}/hqdefault.jpg`)
		: null;

	const imageSize = compact ? "w-12" : "w-14";

	const scrollToActiveCard = () => {
		const target = usePlayerStore.getState().playerContainer;
		target?.scrollIntoView({ behavior: "smooth", block: "center" });
	};

	return (
		<div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
			{currentMix ? (
				<button
					type="button"
					onClick={scrollToActiveCard}
					aria-label="Scroll to playing mix"
					className={`${imageSize} relative aspect-video rounded overflow-hidden bg-bg-elevated shrink-0 cursor-pointer`}
				>
					{thumbnail && (
						<img
							src={thumbnail}
							alt={currentMix.title}
							className="w-full h-full object-cover"
						/>
					)}
				</button>
			) : (
				<div
					className={`${imageSize} relative aspect-video rounded overflow-hidden bg-bg-elevated shrink-0`}
				/>
			)}
			<div className="min-w-0 flex-1">
				{currentMix ? (
					<>
						<p className="text-sm text-text-primary truncate">
							{currentMix.title}
						</p>
						<p className="text-xs text-text-muted truncate">
							{currentMix.channel_name}
						</p>
					</>
				) : (
					<p className="text-sm text-text-muted">Select a mix to play</p>
				)}
			</div>
		</div>
	);
}
