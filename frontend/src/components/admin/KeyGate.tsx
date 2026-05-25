import { useState } from "react";
import { checkAdminKey } from "../../api/admin";
import { ApiError } from "../../api/client";

export function KeyGate({ onKey }: { onKey: (k: string) => void }) {
	const [value, setValue] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	async function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		const trimmed = value.trim();
		if (!trimmed || submitting) return;
		setSubmitting(true);
		setError(null);
		try {
			await checkAdminKey(trimmed);
			onKey(trimmed);
		} catch (err) {
			// 401/403 → invalid key; anything else → backend/network problem.
			// Either way, don't let the caller into the admin UI.
			if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
				setError("Invalid API key");
			} else {
				setError("Could not verify key. Try again.");
			}
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<div className="min-h-screen bg-bg-primary flex items-center justify-center">
			<form
				onSubmit={handleSubmit}
				className="bg-bg-secondary border border-border rounded-lg p-8 w-80 space-y-4"
			>
				<h1 className="text-text-primary font-semibold text-lg">Admin access</h1>
				<input
					type="password"
					value={value}
					onChange={(e) => setValue(e.target.value)}
					placeholder="API key"
					autoFocus
					disabled={submitting}
					className="w-full bg-bg-elevated border border-border rounded px-3 py-2 text-text-primary placeholder-text-muted text-sm outline-none focus:border-accent disabled:opacity-50"
				/>
				{error && (
					<p className="text-sm text-red-500" role="alert">
						{error}
					</p>
				)}
				<button
					type="submit"
					disabled={submitting || !value.trim()}
					className="w-full bg-accent hover:bg-accent-hover text-white rounded py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{submitting ? "Verifying…" : "Enter"}
				</button>
			</form>
		</div>
	);
}
