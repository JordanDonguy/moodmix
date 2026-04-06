import { useInfiniteQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { searchMixes } from "../../api/mixes";
import { useDebounce } from "../../hooks/useDebounce";
import { useSearchStore } from "../../store/searchStore";
import { MixCard } from "./MixCard";

const PAGE_SIZE = 20;

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

	const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
		useInfiniteQuery({
			queryKey: ["mixes", debouncedParams],
			queryFn: ({ pageParam = 0 }) =>
				searchMixes({
					...debouncedParams,
					limit: PAGE_SIZE,
					offset: pageParam,
				}),
			getNextPageParam: (lastPage, allPages) =>
				lastPage.mixes.length === PAGE_SIZE
					? allPages.length * PAGE_SIZE
					: undefined,
			initialPageParam: 0,
		});

	const allMixes = data?.pages.flatMap((p) => p.mixes) ?? [];

	// Infinite scroll sentinel
	const sentinelRef = useRef<HTMLDivElement>(null);
	const handleIntersect = useCallback(
		(entries: IntersectionObserverEntry[]) => {
			if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
				fetchNextPage();
			}
		},
		[fetchNextPage, hasNextPage, isFetchingNextPage],
	);

	useEffect(() => {
		const el = sentinelRef.current;
		if (!el) return;
		const observer = new IntersectionObserver(handleIntersect, {
			rootMargin: "400px",
		});
		observer.observe(el);
		return () => observer.disconnect();
	}, [handleIntersect]);

	return (
		<div>
			{isLoading && (
				<p className="text-text-muted text-sm text-center py-8">Loading...</p>
			)}
			{error && (
				<div className="text-center py-20 text-text-muted text-lg">
					<img
						src="/oops_emoji.png"
						alt="Oops emoji"
						className="mx-auto mb-4 w-16 h-16"
					/>
					<p>Couldn't reach the server...</p>
					<p>Check your connection and try again.</p>
				</div>
			)}

			{!isLoading && allMixes.length === 0 && data && (
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

			{allMixes.length > 0 && (
				<>
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
						{allMixes.map((m, i) => (
							<MixCard key={m.id} mix={m} queue={allMixes} priority={i < 4} />
						))}
					</div>

					{/* Sentinel + loading indicator */}
					<div ref={sentinelRef} className="py-8 flex justify-center">
						{isFetchingNextPage && (
							<Loader2
								size={24}
								className="text-text-muted animate-spin"
							/>
						)}
						{!hasNextPage && allMixes.length > PAGE_SIZE && (
							<p className="text-text-muted text-sm">
								{allMixes.length} mixes loaded
							</p>
						)}
					</div>
				</>
			)}
		</div>
	);
}
