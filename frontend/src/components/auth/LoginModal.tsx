import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "react-toastify";
import { requestCode, verifyCode } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../store/authStore";
import OtpInput from "./OtpInput";
import ResendCodeButton from "./ResendCodeButton";

type Step = "email" | "code";

export default function LoginModal() {
	const open = useAuthStore((s) => s.loginModalOpen);
	const close = useAuthStore((s) => s.closeLoginModal);
	const setUser = useAuthStore((s) => s.setUser);

	const [step, setStep] = useState<Step>("email");
	const [email, setEmail] = useState("");
	const [code, setCode] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const emailInputRef = useRef<HTMLInputElement>(null);

	// Focus the email input when the modal opens or when stepping back from
	// the code screen. Done programmatically (instead of `autoFocus`) so a11y
	// linters don't trip — same UX, explicit ownership.
	useEffect(() => {
		if (open && step === "email") {
			emailInputRef.current?.focus();
		}
	}, [open, step]);

	// Reset to a clean slate every time the modal opens — never carry stale
	// codes/errors across closings.
	useEffect(() => {
		if (open) {
			setStep("email");
			setEmail("");
			setCode("");
			setError(null);
		}
	}, [open]);

	// Close on Escape; lock body scroll while open.
	useEffect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
		document.addEventListener("keydown", onKey);
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.removeEventListener("keydown", onKey);
			document.body.style.overflow = prevOverflow;
		};
	}, [open, close]);

	if (!open) return null;

	async function handleEmailSubmit(e: React.FormEvent) {
		e.preventDefault();
		setError(null);
		setSubmitting(true);
		try {
			await requestCode(email);
			setStep("code");
		} catch (err) {
			setError(messageFor(err));
		} finally {
			setSubmitting(false);
		}
	}

	async function handleVerify(submittedCode: string) {
		setError(null);
		setSubmitting(true);
		try {
			const session = await verifyCode(email, submittedCode);
			setUser(session.user);
			close();
			toast.success(`Signed in as ${session.user.email}`);
		} catch (err) {
			setError(messageFor(err));
			setCode("");
		} finally {
			setSubmitting(false);
		}
	}

	async function handleResend() {
		setError(null);
		try {
			await requestCode(email);
		} catch (err) {
			setError(messageFor(err));
		}
	}

	return createPortal(
		<div className="fixed inset-0 z-50 flex items-center justify-center">
			<button
				type="button"
				onClick={close}
				aria-label="Close sign-in dialog"
				className="absolute inset-0 w-full h-full bg-black/60 backdrop-blur-[3px] cursor-default"
			/>
			<div
				className="relative w-full max-w-sm rounded-lg bg-bg-primary border border-border p-6 mx-4 animate-modal"
				role="dialog"
				aria-modal="true"
				aria-labelledby="login-modal-title"
			>
				<button
					type="button"
					onClick={close}
					aria-label="Close"
					className="absolute top-3 right-3 p-1 text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
				>
					<X size={18} />
				</button>

				<h2
					id="login-modal-title"
					className="text-xl font-semibold text-text-primary mb-1"
				>
					Sign in to MoodMix
				</h2>
				<p className="text-sm text-text-secondary mb-4 whitespace-break-spaces">
					{step === "email"
						? "Or get started with a new account. \nWe'll email you a one-time code."
						: `Enter the 6-digit code we sent to ${email}.`}
				</p>

				{step === "email" ? (
					<form onSubmit={handleEmailSubmit} className="space-y-4" noValidate>
						<input
							id="login-email"
							ref={emailInputRef}
							type="email"
							required
							maxLength={200}
							placeholder="you@example.com"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							className="w-full rounded-md bg-bg-secondary border border-border px-3 py-2 text-text-primary focus:outline-none focus:border-accent"
						/>

						{error && <p className="text-sm text-accent">{error}</p>}

						<button
							type="submit"
							disabled={submitting || !email}
							className="w-full px-4 py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
						>
							{submitting ? "Sending…" : "Send code"}
						</button>
					</form>
				) : (
					<div className="space-y-4">
						<OtpInput
							value={code}
							onChange={setCode}
							onComplete={handleVerify}
							autoFocus
							disabled={submitting}
						/>

						{error && (
							<p className="text-sm text-accent text-center">{error}</p>
						)}

						<div className="flex items-center justify-between">
							<button
								type="button"
								onClick={() => setStep("email")}
								className="text-sm text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
							>
								Use a different email
							</button>
							<ResendCodeButton onResend={handleResend} />
						</div>
					</div>
				)}
			</div>
		</div>,
		document.body,
	);
}

function messageFor(err: unknown): string {
	if (err instanceof ApiError) {
		if (err.status === 422) return "That doesn't look like a valid email.";
		if (err.status === 429) return "Too many attempts. Try again in a minute.";
		if (err.status === 401) return "Code is invalid or expired.";
		if (err.status === 503) return "Sign-in is temporarily unavailable.";
	}
	return "Something went wrong. Please try again.";
}
