import { useQuery } from "@tanstack/react-query";
import { ChevronDown, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getGenres } from "../../api/genres";

interface GenreDropdownProps {
	selected: string[];
	onToggle: (slug: string) => void;
	onClear: () => void;
	inline?: boolean;
}

function GenreChips({
	selected,
	onToggle,
	onClear,
}: {
	selected: string[];
	onToggle: (slug: string) => void;
	onClear: () => void;
}) {
	const { data: genres = [] } = useQuery({
		queryKey: ["genres"],
		queryFn: getGenres,
		staleTime: Number.POSITIVE_INFINITY,
	});

	return (
		<div>
			<div className="flex items-center justify-between mb-2">
				<span className="text-xs text-text-muted uppercase tracking-wider">
					Filter by genre
				</span>
				{selected.length > 0 && (
					<button
						type="button"
						onClick={onClear}
						className="text-xs text-text-primary hover:opacity-80 flex items-center gap-1 cursor-pointer"
					>
						<X size={12} />
						Clear
					</button>
				)}
			</div>
			<div className="flex flex-wrap gap-2">
				{genres.map((genre) => {
					const isSelected = selected.includes(genre.slug);
					return (
						<button
							key={genre.id}
							type="button"
							onClick={() => onToggle(genre.slug)}
							className={`px-3 py-1 rounded-full text-sm transition-colors cursor-pointer ${
								isSelected
									? "bg-accent/20 text-accent border border-accent/40"
									: "bg-bg-elevated text-text-secondary border border-transparent hover:text-text-primary"
							}`}
						>
							{genre.name}
						</button>
					);
				})}
			</div>
		</div>
	);
}

export default function GenreDropdown({
	selected,
	onToggle,
	onClear,
	inline,
}: GenreDropdownProps) {
	const [open, setOpen] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

	// Close on click-outside
	useEffect(() => {
		if (!open) return;
		function handleClick(e: MouseEvent) {
			if (
				containerRef.current &&
				!containerRef.current.contains(e.target as Node)
			) {
				setOpen(false);
			}
		}
		document.addEventListener("mousedown", handleClick);
		return () => document.removeEventListener("mousedown", handleClick);
	}, [open]);

	const label = selected.length > 0 ? `Genres (${selected.length})` : "Genres";

	const button = (
		<button
			type="button"
			onClick={() => setOpen((o) => !o)}
			className={`flex items-center gap-1 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors cursor-pointer ${
				selected.length > 0
					? "bg-accent/15 text-accent px-2"
					: "text-text-primary hover:opacity-80"
			}`}
		>
			{label}
			<ChevronDown
				size={14}
				className={`transition-transform ${open ? "rotate-180" : ""}`}
			/>
		</button>
	);

	if (inline) {
		return (
			<div ref={containerRef}>
				{button}
				{open && (
					<div className="pt-3">
						<GenreChips
							selected={selected}
							onToggle={onToggle}
							onClear={onClear}
						/>
					</div>
				)}
			</div>
		);
	}

	return (
		<div ref={containerRef} className="relative">
			{button}
			{open && (
				<div className="absolute top-full mt-2 left-0 z-50 bg-bg-primary/98 border border-border rounded-xl p-3 shadow-lg min-w-70 animate-menu-open-top-left">
					<GenreChips
						selected={selected}
						onToggle={onToggle}
						onClear={onClear}
					/>
				</div>
			)}
		</div>
	);
}
