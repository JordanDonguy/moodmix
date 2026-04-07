import { useEffect, useRef } from "react";
import { useSliderDrag } from "../../hooks/useSliderDrag";
import { usePlayerStore } from "../../store/playerStore";
import { formatHoursMinutesSeconds } from "../../utils/time";

/**
 * Self-contained playback progress bar.
 *
 * Subscribes to the player store imperatively and mutates the DOM directly,
 * avoiding React re-renders for high-frequency progress ticks. Drag
 * interaction is shared with the reactive Slider component via
 * {@link useSliderDrag}.
 */
export default function ProgressBar() {
	const currentTimeRef = useRef<HTMLSpanElement>(null);
	const durationRef = useRef<HTMLSpanElement>(null);
	const fillRef = useRef<HTMLDivElement>(null);

	const { ref: sliderRef, onPointerDown, onPointerMove } = useSliderDrag(
		(value) => {
			const { duration } = usePlayerStore.getState();
			if (!duration) return;
			usePlayerStore.getState().seekTo((value / 100) * duration);
		},
	);

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
			const slider = sliderRef.current;
			if (slider) {
				slider.setAttribute("aria-valuemax", String(duration));
				slider.setAttribute("aria-valuenow", String(Math.floor(currentTime)));
			}
		};

		const state = usePlayerStore.getState();
		apply(state.currentTime, state.duration);

		return usePlayerStore.subscribe((s) => apply(s.currentTime, s.duration));
	}, [sliderRef]);

	return (
		<div className="flex items-center gap-2 w-full">
			<span
				ref={currentTimeRef}
				className="text-[11px] text-text-muted tabular-nums w-8 text-right shrink-0"
			>
				-:--
			</span>
			<div
				ref={sliderRef}
				role="slider"
				tabIndex={0}
				aria-label="Seek in track"
				aria-valuemin={0}
				aria-valuemax={0}
				aria-valuenow={0}
				onPointerDown={onPointerDown}
				onPointerMove={onPointerMove}
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
