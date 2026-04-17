import { useState } from "react";

type FormState = {
	name: string;
	email: string;
	message: string;
	website: string;
};

const INITIAL: FormState = { name: "", email: "", message: "", website: "" };

const MAX_MESSAGE = 2000;

export default function ContactPage() {
	const [form, setForm] = useState<FormState>(INITIAL);
	const [submitting, setSubmitting] = useState(false);
	const [sent, setSent] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function update<K extends keyof FormState>(key: K, value: FormState[K]) {
		setForm((f) => ({ ...f, [key]: value }));
	}

	async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
		e.preventDefault();
		setError(null);

		// Honeypot — bots fill hidden fields, humans don't
		if (form.website) {
			setSent(true);
			return;
		}

		setSubmitting(true);
		try {
			// TODO(sprint-7 PR 4): POST to /api/contact via Resend
			await new Promise((r) => setTimeout(r, 400));
			setSent(true);
			setForm(INITIAL);
		} catch {
			setError("Could not send your message. Please try again later.");
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<>
			<h1>Contact</h1>

			<p>
				Happy to hear from you, whether it's feedback, a bug you'd like to
				report, a GDPR request, or just a thought about the project. Drop a
				message below and we'll reply by email.
			</p>

			{sent ? (
				<div className="rounded-md border border-accent/40 bg-accent/10 px-4 py-3 text-text-primary">
					Thanks — your message has been sent. You'll get a reply by email.
				</div>
			) : (
				<form onSubmit={handleSubmit} className="space-y-4" noValidate>
					{/* Honeypot field — visually hidden, ignored by humans */}
					<div aria-hidden="true" className="hidden">
						<label>
							Leave this field empty
							<input
								type="text"
								name="website"
								tabIndex={-1}
								autoComplete="off"
								value={form.website}
								onChange={(e) => update("website", e.target.value)}
							/>
						</label>
					</div>

					<div>
						<label
							htmlFor="contact-name"
							className="block text-sm text-text-primary mb-1"
						>
							Name
						</label>
						<input
							id="contact-name"
							type="text"
							required
							maxLength={100}
							value={form.name}
							onChange={(e) => update("name", e.target.value)}
							className="w-full rounded-md bg-bg-secondary border border-border px-3 py-2 text-text-primary focus:outline-none focus:border-accent"
						/>
					</div>

					<div>
						<label
							htmlFor="contact-email"
							className="block text-sm text-text-primary mb-1"
						>
							Email
						</label>
						<input
							id="contact-email"
							type="email"
							required
							maxLength={200}
							value={form.email}
							onChange={(e) => update("email", e.target.value)}
							className="w-full rounded-md bg-bg-secondary border border-border px-3 py-2 text-text-primary focus:outline-none focus:border-accent"
						/>
					</div>

					<div>
						<label
							htmlFor="contact-message"
							className="block text-sm text-text-primary mb-1"
						>
							Message
						</label>
						<textarea
							id="contact-message"
							required
							rows={7}
							maxLength={MAX_MESSAGE}
							value={form.message}
							onChange={(e) => update("message", e.target.value)}
							className="w-full rounded-md bg-bg-secondary border border-border px-3 py-2 text-text-primary focus:outline-none focus:border-accent resize-y"
						/>
						<p className="mt-1 text-xs text-text-muted text-right">
							{form.message.length} / {MAX_MESSAGE}
						</p>
					</div>

					{error && <p className="text-sm text-accent">{error}</p>}

					<button
						type="submit"
						disabled={submitting}
						className="px-4 py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
					>
						{submitting ? "Sending…" : "Send message"}
					</button>
				</form>
			)}
		</>
	);
}
