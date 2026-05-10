import { useEffect, useState } from "react";

export function Pagination({
	currentPage,
	totalPages,
	onJump,
}: {
	currentPage: number;
	totalPages: number;
	onJump: (page: number) => void;
}) {
	const [draft, setDraft] = useState(String(currentPage));

	useEffect(() => {
		setDraft(String(currentPage));
	}, [currentPage]);

	function commit() {
		const parsed = Number.parseInt(draft, 10);
		if (Number.isNaN(parsed)) {
			setDraft(String(currentPage));
			return;
		}
		const clamped = Math.min(Math.max(parsed, 1), totalPages);
		setDraft(String(clamped));
		if (clamped !== currentPage) onJump(clamped);
	}

	return (
		<div className="border-t border-border p-2 flex items-center justify-between gap-1 text-xs text-text-muted">
			<button
				type="button"
				disabled={currentPage <= 1}
				onClick={() => onJump(currentPage - 1)}
				className="px-2 py-1 rounded hover:bg-bg-elevated disabled:opacity-30 transition-colors"
			>
				←
			</button>
			<div className="flex items-center gap-1">
				<input
					type="text"
					inputMode="numeric"
					value={draft}
					onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
					onBlur={commit}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							e.currentTarget.blur();
						}
					}}
					className="w-10 bg-bg-elevated border border-border rounded px-1 py-0.5 text-center text-text-primary outline-none focus:border-accent"
				/>
				<span>/ {totalPages}</span>
			</div>
			<button
				type="button"
				disabled={currentPage >= totalPages}
				onClick={() => onJump(currentPage + 1)}
				className="px-2 py-1 rounded hover:bg-bg-elevated disabled:opacity-30 transition-colors"
			>
				→
			</button>
		</div>
	);
}
