export function AdminHeader({ onSignOut }: { onSignOut: () => void }) {
	return (
		<header className="border-b border-border bg-bg-secondary px-6 py-3 flex items-center justify-between shrink-0">
			<span className="text-text-primary font-semibold">MoodMix Admin — Catalog</span>
			<button
				type="button"
				onClick={onSignOut}
				className="text-xs text-text-muted hover:text-text-primary transition-colors"
			>
				Sign out
			</button>
		</header>
	);
}
