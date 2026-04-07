import { useRef } from "react";

/**
 * Pointer-driven drag interaction for horizontal sliders.
 *
 * Returns a ref to attach to the track element, plus pointer handlers.
 * The `onChange` callback receives an integer 0-100 representing the
 * pointer position along the track.
 *
 * Used by both the reactive `Slider` component and by performance-
 * sensitive consumers (e.g. ProgressBar) that render their own JSX with
 * imperative DOM updates.
 */
export function useSliderDrag(onChange: (value: number) => void) {
	const ref = useRef<HTMLDivElement>(null);

	const updateFromEvent = (e: React.PointerEvent) => {
		const bar = ref.current;
		if (!bar) return;
		const rect = bar.getBoundingClientRect();
		const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
		onChange(Math.round(ratio * 100));
	};

	const onPointerDown = (e: React.PointerEvent) => {
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		updateFromEvent(e);
	};

	const onPointerMove = (e: React.PointerEvent) => {
		if (e.buttons > 0) updateFromEvent(e);
	};

	return { ref, onPointerDown, onPointerMove };
}
