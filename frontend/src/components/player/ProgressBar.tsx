import { useEffect, useRef } from "react";
import { usePlayerStore } from "../../store/playerStore";
import { formatHoursMinutesSeconds } from "../../utils/time";

export default function ProgressBar({
	progressRef,
	onSeek,
}: {
	progressRef: React.RefObject<HTMLDivElement | null>;
	onSeek: (e: React.PointerEvent) => void;
}) {
	const currentTimeRef = useRef<HTMLSpanElement>(null);
	const durationRef = useRef<HTMLSpanElement>(null);
	const fillRef = useRef<HTMLDivElement>(null);

	// Subscribe to the store imperatively and mutate the DOM directly.
	// This avoids React re-renders for high-frequency progress updates.
	useEffect(() => {
		const apply = (currentTime: number, duration: number) => {
			const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
			if (fillRef.current) fillRef.current.style.width = `${progress}%`;
			if (currentTimeRef.current) {
				currentTimeRef.current.textContent =
					duration > 0 ? formatHoursMinutesSeconds(currentTime) : "-:--";
			}
			if (durationRef.current) {
				durationRef.current.textContent =
					duration > 0 ? formatHoursMinutesSeconds(duration) : "-:--";
			}
			const slider = progressRef.current;
			if (slider) {
				slider.setAttribute("aria-valuemax", String(duration));
				slider.setAttribute("aria-valuenow", String(Math.floor(currentTime)));
			}
		};

		const state = usePlayerStore.getState();
		apply(state.currentTime, state.duration);

		return usePlayerStore.subscribe((s) => apply(s.currentTime, s.duration));
	}, [progressRef]);

	return (
		<div className="flex items-center gap-2 w-full">
			<span
				ref={currentTimeRef}
				className="text-[11px] text-text-muted tabular-nums w-8 text-right shrink-0"
			>
				-:--
			</span>
			<div
				ref={progressRef}
				role="slider"
				tabIndex={0}
				aria-label="Seek in track"
				aria-valuemin={0}
				aria-valuemax={0}
				aria-valuenow={0}
				onPointerDown={(e) => {
					(e.target as HTMLElement).setPointerCapture(e.pointerId);
					onSeek(e);
				}}
				onPointerMove={(e) => e.buttons > 0 && onSeek(e)}
				className="flex-1 h-3 flex items-center cursor-pointer group touch-none"
			>
				<div className="h-1 w-full rounded-full bg-bg-elevated relative">
					<div
						ref={fillRef}
						className="h-full rounded-full bg-text-secondary group-hover:bg-text-primary transition-colors"
						style={{ width: "0%" }}
					/>
				</div>
			</div>
			<span
				ref={durationRef}
				className="text-[11px] text-text-muted tabular-nums w-8 shrink-0"
			>
				-:--
			</span>
		</div>
	);
}
