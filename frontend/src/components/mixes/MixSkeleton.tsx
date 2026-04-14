/**
 * Loading placeholder that mirrors MixCard's structure.
 * Uses `bg-bg-secondary` / `bg-bg-elevated` so it adapts to light/dark themes
 * automatically via the CSS variables in index.css.
 */
export function MixSkeleton({ className = "" }: { className?: string }) {
	return (
		<div
			className={`flex flex-col h-full animate-pulse ${className}`}
			aria-hidden="true"
		>
			{/* Thumbnail placeholder */}
			<div className="relative aspect-video rounded-xl bg-bg-secondary w-full" />

			<div className="mt-2 px-0.5 flex flex-col flex-1">
				{/* Title - 2 lines */}
				<div className="space-y-1.5">
					<div className="h-3.5 rounded bg-bg-secondary w-11/12" />
					<div className="h-3.5 rounded bg-bg-secondary w-3/5" />
				</div>

				{/* Channel name + genre pills */}
				<div className="flex justify-between items-center mt-auto pt-2 pb-2">
					<div className="h-3 rounded bg-bg-secondary w-1/3" />
					<div className="flex gap-1">
						<div className="h-4 w-12 rounded-full bg-bg-elevated" />
						<div className="h-4 w-10 rounded-full bg-bg-elevated" />
					</div>
				</div>
			</div>
		</div>
	);
}
