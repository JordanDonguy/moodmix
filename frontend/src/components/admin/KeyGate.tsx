import { useState } from "react";

export function KeyGate({ onKey }: { onKey: (k: string) => void }) {
	const [value, setValue] = useState("");

	return (
		<div className="min-h-screen bg-bg-primary flex items-center justify-center">
			<form
				onSubmit={(e) => {
					e.preventDefault();
					if (value.trim()) onKey(value.trim());
				}}
				className="bg-bg-secondary border border-border rounded-lg p-8 w-80 space-y-4"
			>
				<h1 className="text-text-primary font-semibold text-lg">Admin access</h1>
				<input
					type="password"
					value={value}
					onChange={(e) => setValue(e.target.value)}
					placeholder="API key"
					autoFocus
					className="w-full bg-bg-elevated border border-border rounded px-3 py-2 text-text-primary placeholder-text-muted text-sm outline-none focus:border-accent"
				/>
				<button
					type="submit"
					className="w-full bg-accent hover:bg-accent-hover text-white rounded py-2 text-sm font-medium transition-colors"
				>
					Enter
				</button>
			</form>
		</div>
	);
}
