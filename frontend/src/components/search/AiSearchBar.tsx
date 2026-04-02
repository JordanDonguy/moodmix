import { Loader2, Search } from "lucide-react";
import { type FormEvent, useState } from "react";
import { aiSearch } from "../../api/mixes";
import { useSearchStore } from "../../store/searchStore";

export default function AiSearchBar() {
	const [query, setQuery] = useState("");
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [focused, setFocused] = useState(false);
	const applyAiInferred = useSearchStore((s) => s.applyAiInferred);

	const handleSubmit = async (e: FormEvent) => {
		e.preventDefault();
		const trimmed = query.trim();
		if (!trimmed || loading) return;

		setLoading(true);
		setError(null);

		try {
			const res = await aiSearch(trimmed);
			applyAiInferred(res.inferred);
			setQuery("");
		} catch (err) {
			if (err instanceof Error && err.message.includes("429")) {
				setError("Too many requests, please wait");
			} else {
				setError("Search failed");
			}
			setTimeout(() => setError(null), 3000);
		} finally {
			setLoading(false);
		}
	};

	return (
		<form onSubmit={handleSubmit} className="relative">
			<div
				className={`flex items-center gap-2 bg-bg-secondary border border-border rounded-full px-3 py-1.5 transition-all w-full lg:w-45 ${focused ? "lg:w-60!" : ""}`}
			>
				{loading ? (
					<Loader2
						size={16}
						className="text-text-primary animate-spin shrink-0"
					/>
				) : (
					<Search size={16} className="text-text-primary shrink-0" />
				)}
				<input
					type="text"
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					onFocus={() => setFocused(true)}
					onBlur={() => setFocused(false)}
					placeholder="Describe a mood..."
					className="bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none w-full"
				/>
			</div>

			{error && (
				<div className="absolute top-full mt-2 left-0 right-0 bg-accent/15 text-accent text-xs rounded-lg px-3 py-1.5 text-center">
					{error}
				</div>
			)}
		</form>
	);
}
