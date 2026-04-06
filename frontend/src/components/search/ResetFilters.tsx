import { RotateCcw } from "lucide-react";
import { useSearchStore } from "../../store/searchStore";

export default function ResetFilters({
	size = 16,
	divider = false,
}: {
	size?: number;
	divider?: boolean;
}) {
	const { mood, energy, instrumentation, genres, instrumental, resetAll } =
		useSearchStore();

	const hasFilters =
		mood !== null ||
		energy !== null ||
		instrumentation !== null ||
		genres.length > 0 ||
		instrumental;

	if (!hasFilters) return null;

	return (
		<>
			{divider && <div className="w-px h-6 bg-border shrink-0" />}
			<button
				type="button"
				onClick={resetAll}
				aria-label="Reset all filters"
				className="text-text-primary hover:opacity-80 transition cursor-pointer shrink-0"
			>
				<RotateCcw size={size} />
			</button>
		</>
	);
}
