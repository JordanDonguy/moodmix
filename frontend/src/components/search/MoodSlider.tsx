import type { LucideIcon } from "lucide-react";
import { X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface MoodSliderProps {
	value: number | null;
	onChange: (v: number | null) => void;
	leftIcon: LucideIcon;
	rightIcon: LucideIcon;
	leftTooltip: string;
	rightTooltip: string;
	gradientFrom: string;
	gradientTo: string;
	expand?: boolean;
}

export default function MoodSlider({
	value,
	onChange,
	leftIcon: LeftIcon,
	rightIcon: RightIcon,
	leftTooltip,
	rightTooltip,
	gradientFrom,
	gradientTo,
	expand,
}: MoodSliderProps) {
	const active = value !== null;
	const displayValue = value ?? 0;
	const trackRef = useRef<HTMLDivElement>(null);
	const [dragging, setDragging] = useState(false);

	const calcValue = useCallback((clientX: number) => {
		const track = trackRef.current;
		if (!track) return 0;
		const rect = track.getBoundingClientRect();
		const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
		return Math.round((ratio * 2 - 1) * 10) / 10;
	}, []);

	const handlePointerDown = (e: React.PointerEvent) => {
		e.preventDefault();
		setDragging(true);
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		onChange(calcValue(e.clientX));
	};

	const handlePointerMove = (e: React.PointerEvent) => {
		if (!dragging) return;
		onChange(calcValue(e.clientX));
	};

	const handlePointerUp = () => {
		setDragging(false);
	};

	const handleDoubleClick = () => {
		onChange(null);
	};

	const thumbPosition = ((displayValue + 1) / 2) * 100;

	return (
		<div className="flex items-center gap-2 select-none min-w-0">
			<button
				type="button"
				aria-label={leftTooltip}
				onClick={() => onChange(-1)}
				className="text-text-primary hover:opacity-80 transition cursor-pointer shrink-0"
			>
				<LeftIcon size={18} />
			</button>

			<div
				ref={trackRef}
				role="slider"
				tabIndex={0}
				aria-label={`${leftTooltip} to ${rightTooltip}`}
				aria-valuemin={-1}
				aria-valuemax={1}
				aria-valuenow={displayValue}
				onPointerDown={handlePointerDown}
				onPointerMove={handlePointerMove}
				onPointerUp={handlePointerUp}
				onDoubleClick={handleDoubleClick}
				className={`relative h-6 cursor-pointer flex items-center touch-none ${expand ? "flex-1" : "w-28 min-w-16 shrink"}`}
			>
				{/* Track background */}
				<div
					className="h-1 w-full rounded-full"
					style={{
						background: active
							? `linear-gradient(to right, ${gradientFrom}, ${gradientTo})`
							: "var(--color-bg-elevated)",
					}}
				/>
				{/* Thumb */}
				<div
					className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 transition-opacity"
					style={{
						left: `${thumbPosition}%`,
						background: active
							? "var(--color-text-primary)"
							: "var(--color-text-muted)",
						borderColor: active
							? "var(--color-text-primary)"
							: "var(--color-text-muted)",
						opacity: active ? 1 : 0.5,
					}}
				/>
			</div>

			<button
				type="button"
				aria-label={rightTooltip}
				onClick={() => onChange(1)}
				className="text-text-primary hover:opacity-80 transition cursor-pointer"
			>
				<RightIcon size={18} />
			</button>

			{expand ? (
				<button
					type="button"
					aria-label="Reset"
					onClick={() => onChange(null)}
					className={`transition-opacity cursor-pointer text-text-primary ${active ? "opacity-60 hover:opacity-100" : "opacity-0 pointer-events-none"}`}
				>
					<X size={14} />
				</button>
			) : (
				active && (
					<button
						type="button"
						aria-label="Reset"
						onClick={() => onChange(null)}
						className="opacity-60 hover:opacity-100 text-text-primary transition-opacity cursor-pointer"
					>
						<X size={14} />
					</button>
				)
			)}
		</div>
	);
}
