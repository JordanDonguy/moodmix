import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { QUICK_TAGS } from "../../data/quickTags";
import { useSearchStore } from "../../store/searchStore";

const SCROLL_AMOUNT = 200;

function shuffled<T>(arr: T[]): T[] {
	const copy = [...arr];
	for (let i = copy.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[copy[i], copy[j]] = [copy[j], copy[i]];
	}
	return copy;
}

export default function QuickTags() {
	const [canScrollLeft, setCanScrollLeft] = useState(false);
	const [canScrollRight, setCanScrollRight] = useState(false);
	const scrollRef = useRef<HTMLDivElement>(null);
	const tags = useMemo(() => shuffled(QUICK_TAGS), []);
	const applyAiInferred = useSearchStore((s) => s.applyAiInferred);

	const checkScroll = useCallback(() => {
		const el = scrollRef.current;
		if (!el) return;
		setCanScrollLeft(el.scrollLeft > 0);
		setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
	}, []);

	useEffect(() => {
		checkScroll();
		window.addEventListener("resize", checkScroll);
		return () => window.removeEventListener("resize", checkScroll);
	}, [checkScroll]);

	const scroll = (direction: "left" | "right") => {
		scrollRef.current?.scrollBy({
			left: direction === "left" ? -SCROLL_AMOUNT : SCROLL_AMOUNT,
			behavior: "smooth",
		});
	};

	const handleClick = (tag: (typeof QUICK_TAGS)[number]) => {
		applyAiInferred({
			mood: tag.mood,
			energy: tag.energy,
			instrumentation: tag.instrumentation,
			genres: tag.genres,
			instrumental: tag.instrumental,
		});
	};

	return (
		<div className="relative z-30 bg-bg-primary border-b border-border">
			{/* Left arrow */}
			{canScrollLeft && (
				<button
					type="button"
					onClick={() => scroll("left")}
					className="absolute left-0 top-0 bottom-0 z-10 flex items-center pl-3 pr-3 bg-linear-to-r from-bg-primary from-60% to-transparent cursor-pointer"
				>
					<ChevronLeft size={18} className="text-text-primary" />
				</button>
			)}

			{/* Tags row */}
			<div
				ref={scrollRef}
				onScroll={checkScroll}
				className="flex gap-2 px-4 py-2.5 overflow-x-auto scrollbar-hide"
			>
				{tags.map((tag) => (
					<button
						key={tag.label}
						type="button"
						onClick={() => handleClick(tag)}
						className="shrink-0 px-3 py-1 rounded-lg text-xs transition-colors cursor-pointer bg-bg-elevated text-text-primary hover:text-text-secondary hover:bg-bg-secondary"
					>
						{tag.label}
					</button>
				))}
			</div>

			{/* Right arrow */}
			{canScrollRight && (
				<button
					type="button"
					onClick={() => scroll("right")}
					className="absolute right-0 top-0 bottom-0 z-10 flex items-center pr-5 pl-3 bg-linear-to-l from-bg-primary from-60% to-transparent cursor-pointer"
				>
					<ChevronRight size={18} className="text-text-primary" />
				</button>
			)}
		</div>
	);
}
