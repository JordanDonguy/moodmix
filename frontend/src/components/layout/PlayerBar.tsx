import {
	FastForward,
	Pause,
	Play,
	Rewind,
	SkipBack,
	SkipForward,
	Volume2,
	VolumeOff,
} from "lucide-react";
import { useRef } from "react";
import { usePlayerStore } from "../../store/playerStore";
import ProgressBar from "../player/ProgressBar";

export default function PlayerBar() {
	const currentMix = usePlayerStore((s) => s.currentMix);
	const isPlaying = usePlayerStore((s) => s.isPlaying);
	const volume = usePlayerStore((s) => s.volume);
	const muted = usePlayerStore((s) => s.muted);
	const pause = usePlayerStore((s) => s.pause);
	const resume = usePlayerStore((s) => s.resume);
	const next = usePlayerStore((s) => s.next);
	const prev = usePlayerStore((s) => s.prev);
	const skipChapter = usePlayerStore((s) => s.skipChapter);
	const setVolume = usePlayerStore((s) => s.setVolume);
	const toggleMute = usePlayerStore((s) => s.toggleMute);
	const progressRef = useRef<HTMLDivElement>(null);
	const mobileProgressRef = useRef<HTMLDivElement>(null);
	const volumeRef = useRef<HTMLDivElement>(null);

	const handleSeek =
		(ref: React.RefObject<HTMLDivElement | null>) =>
		(e: React.PointerEvent) => {
			const bar = ref.current;
			if (!bar) return;
			const { duration } = usePlayerStore.getState();
			if (!duration) return;
			const rect = bar.getBoundingClientRect();
			const ratio = Math.max(
				0,
				Math.min(1, (e.clientX - rect.left) / rect.width),
			);
			usePlayerStore.getState().seekTo(ratio * duration);
		};

	const volumeFromEvent = (e: React.PointerEvent) => {
		const bar = volumeRef.current;
		if (!bar) return;
		const rect = bar.getBoundingClientRect();
		const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
		setVolume(Math.round(ratio * 100));
	};

	const onVolumePointerDown = (e: React.PointerEvent) => {
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		volumeFromEvent(e);
	};

	const effectiveVolume = muted ? 0 : volume;

	const thumbnail = currentMix
		? (currentMix.thumbnail_url ??
			`https://i.ytimg.com/vi/${currentMix.youtube_id}/hqdefault.jpg`)
		: null;

	const btnSm =
		"text-text-secondary hover:text-text-primary transition-colors cursor-pointer disabled:opacity-30";

	const controls = (
		<div className="flex items-center gap-3">
			<button type="button" onClick={prev} disabled={!currentMix} className={btnSm} aria-label="Previous mix">
				<SkipBack size={18} />
			</button>
			<button
				type="button"
				onClick={() => skipChapter("prev")}
				disabled={!currentMix}
				className={btnSm}
				aria-label="Previous chapter"
			>
				<Rewind size={18} />
			</button>
			<button
				type="button"
				onClick={isPlaying ? pause : resume}
				disabled={!currentMix}
				className="w-8 h-8 flex items-center justify-center rounded-full bg-text-primary text-bg-primary hover:scale-105 transition-transform cursor-pointer disabled:opacity-30"
				aria-label={isPlaying ? "Pause" : "Play"}
			>
				{isPlaying ? (
					<Pause size={16} />
				) : (
					<Play size={16} className="ml-0.5" />
				)}
			</button>
			<button
				type="button"
				onClick={() => skipChapter("next")}
				disabled={!currentMix}
				className={btnSm}
				aria-label="Next chapter"
			>
				<FastForward size={18} />
			</button>
			<button type="button" onClick={next} disabled={!currentMix} className={btnSm} aria-label="Next mix">
				<SkipForward size={18} />
			</button>
		</div>
	);

	return (
		<div className="fixed bottom-0 left-0 right-0 z-50 bg-bg-primary/91 backdrop-blur-[3px] border-t border-border animate-slide-up">
			{/* ── Desktop ── */}
			<div className="hidden sm:flex items-center gap-4 px-4 h-18">
				{/* Left: Thumbnail + info */}
				<div className="flex items-center gap-3 w-1/4 min-w-0">
					<div className="w-12 h-12 rounded overflow-hidden bg-bg-elevated shrink-0">
						{thumbnail && (
							<img
								src={thumbnail}
								alt={currentMix?.title}
								className="w-full h-full object-cover"
							/>
						)}
					</div>
					<div className="min-w-0">
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

				{/* Center: Controls + progress */}
				<div className="flex-1 flex flex-col items-center gap-1 max-w-xl mx-auto">
					{controls}
					<ProgressBar
						progressRef={progressRef}
						onSeek={handleSeek(progressRef)}
					/>
				</div>

				{/* Right: Volume */}
				<div className="flex items-center gap-2 w-1/4 justify-end">
					<button
						type="button"
						onClick={toggleMute}
						aria-label={muted ? "Unmute" : "Mute"}
						className="text-text-primary/80 hover:text-text-primary transition-colors cursor-pointer"
					>
						{muted || volume === 0 ? (
							<VolumeOff size={18} />
						) : (
							<Volume2 size={18} />
						)}
					</button>
					<div
						ref={volumeRef}
						role="slider"
						tabIndex={0}
						aria-label="Volume"
						aria-valuemin={0}
						aria-valuemax={100}
						aria-valuenow={effectiveVolume}
						onPointerDown={onVolumePointerDown}
						onPointerMove={(e) => e.buttons > 0 && volumeFromEvent(e)}
						className="h-3 w-24 flex items-center cursor-pointer group touch-none"
					>
						<div className="h-1 w-full rounded-full bg-bg-elevated relative">
							<div
								className="h-full rounded-full bg-text-secondary group-hover:bg-text-primary transition-colors"
								style={{ width: `${effectiveVolume}%` }}
							/>
						</div>
					</div>
				</div>
			</div>

			{/* ── Mobile ── */}
			<div className="sm:hidden px-3 py-2 space-y-1.5">
				{/* Row 1: Thumbnail + title + controls */}
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded overflow-hidden bg-bg-elevated shrink-0">
						{thumbnail && (
							<img
								src={thumbnail}
								alt={currentMix?.title}
								className="w-full h-full object-cover"
							/>
						)}
					</div>
					<div className="flex-1 min-w-0">
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
					{controls}
				</div>

				{/* Row 2: Progress bar */}
				<ProgressBar
					progressRef={mobileProgressRef}
					onSeek={handleSeek(mobileProgressRef)}
				/>
			</div>
		</div>
	);
}
