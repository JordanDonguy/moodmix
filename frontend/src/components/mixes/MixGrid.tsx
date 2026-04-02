import { useQuery } from "@tanstack/react-query";
import { searchMixes } from "../../api/mixes";
import { useDebounce } from "../../hooks/useDebounce";
import { useSearchStore } from "../../store/searchStore";
import { MixCard } from "./MixCard";

export default function MixGrid() {
	const { mood, energy, instrumentation, genres, instrumental, seed } =
		useSearchStore();
	const debouncedParams = useDebounce({
		mood,
		energy,
		instrumentation,
		genres,
		instrumental,
		seed,
	});

	const { data, isLoading, error } = useQuery({
		queryKey: ["mixes", debouncedParams],
		queryFn: () =>
			searchMixes({
				...debouncedParams,
				limit: 20,
			}),
	});

	return (
		<div>
			{isLoading && (
				<p className="text-text-muted text-sm text-center py-8">Loading...</p>
			)}
			{error && (
				<p className="text-accent text-sm text-center py-8">
					Error: {String(error)}
				</p>
			)}

			{data && data.mixes.length === 0 && (
				<div className="text-center py-20 text-text-muted text-lg">
					<img
						src="/oops_emoji.png"
						alt="Oops emoji"
						className="mx-auto mb-4 w-16 h-16"
					/>
					<p>No mixes found for this combination...</p>
					<p>Try adjusting the sliders or removing a genre filter.</p>
				</div>
			)}

			{data && data.mixes.length > 0 && (
				<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{data.mixes.map((m) => (
						<MixCard key={m.id} mix={m} />
					))}
				</div>
			)}
		</div>
	);
}
