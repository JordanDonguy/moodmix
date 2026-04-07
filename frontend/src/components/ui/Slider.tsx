import { useSliderDrag } from "../../hooks/useSliderDrag";

interface SliderProps {
	value: number;
	onChange: (value: number) => void;
	ariaLabel: string;
	className?: string;
}

/**
 * Reactive horizontal slider.
 *
 * Controlled component: render with `value` (0-100) and react to changes
 * through `onChange`. For high-frequency updates (e.g. media playback
 * progress) use `useSliderDrag` directly and mutate the DOM imperatively
 * to avoid re-rendering.
 */
export default function Slider({
	value,
	onChange,
	ariaLabel,
	className = "flex-1",
}: SliderProps) {
	const { ref, onPointerDown, onPointerMove } = useSliderDrag(onChange);

	return (
		<div
			ref={ref}
			role="slider"
			tabIndex={0}
			aria-label={ariaLabel}
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={Math.round(value)}
			onPointerDown={onPointerDown}
			onPointerMove={onPointerMove}
			className={`h-3 flex items-center cursor-pointer group touch-none ${className}`}
		>
			<div className="h-1 w-full rounded-full bg-bg-elevated relative">
				<div
					className="h-full rounded-full bg-text-secondary group-hover:bg-text-primary transition-colors"
					style={{ width: `${value}%` }}
				/>
			</div>
		</div>
	);
}
