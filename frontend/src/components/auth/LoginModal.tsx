import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { toast } from "react-toastify";
import { useSigninFlow } from "../../hooks/useSigninFlow";
import { useAuthStore } from "../../store/authStore";
import GoogleLogo from "./GoogleLogo";
import OtpInput from "./OtpInput";
import ResendCodeButton from "./ResendCodeButton";

/**
 * Sign-in modal. Owns presentation only — modal lifecycle (open/close,
 * keyboard, scroll lock, focus) and rendering. The auth flow itself
 * (state machine + API calls + error mapping) lives in `useSigninFlow`.
 */
export default function LoginModal() {
	const open = useAuthStore((s) => s.loginModalOpen);
	const close = useAuthStore((s) => s.closeLoginModal);

	const flow = useSigninFlow({
		onSuccess: () => {
			close();
			toast.success("Signed in");
		},
	});
	const emailInputRef = useRef<HTMLInputElement>(null);

	// Reset to a clean slate every time the modal opens — never carry stale
	// codes/errors across closings. `flow.reset` is memoized inside the hook
	// so this effect only fires on the open ↔ close transition.
	useEffect(() => {
		if (open) flow.reset();
	}, [open, flow.reset]);

	// Focus the email input when the modal opens or when stepping back from
	// the code screen. Done programmatically (instead of `autoFocus`) so a11y
	// linters don't trip — same UX, explicit ownership.
	useEffect(() => {
		if (open && flow.step === "email") {
			emailInputRef.current?.focus();
		}
	}, [open, flow.step]);

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
					{flow.step === "email"
						? "Or get started with a new account. \nWe'll email you a one-time code."
						: `Enter the 6-digit code we sent to ${flow.email}.`}
				</p>

				{flow.step === "email" ? (
					<>
						<form onSubmit={flow.submitEmail} className="space-y-4" noValidate>
							<input
								id="login-email"
								ref={emailInputRef}
								type="email"
								required
								maxLength={200}
								placeholder="you@example.com"
								value={flow.email}
								onChange={(e) => flow.setEmail(e.target.value)}
								className="w-full rounded-md bg-bg-secondary border border-border px-3 py-2 text-text-primary focus:outline-none focus:border-accent"
							/>

							{flow.error && (
								<p className="text-sm text-accent">{flow.error}</p>
							)}

							<button
								type="submit"
								disabled={flow.submitting || !flow.email}
								className="w-full px-4 py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
							>
								{flow.submitting ? "Sending…" : "Send code"}
							</button>
						</form>

						<div className="my-4 flex items-center gap-3">
							<div className="flex-1 h-px bg-border" />
							<span className="text-xs uppercase tracking-wider text-text-muted">
								or
							</span>
							<div className="flex-1 h-px bg-border" />
						</div>

						<button
							type="button"
							onClick={flow.signInWithGoogle}
							className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-white text-gray-800 border border-border hover:bg-gray-50 transition-colors cursor-pointer"
						>
							<GoogleLogo />
							<span className="text-sm font-medium">Sign in with Google</span>
						</button>
					</>
				) : (
					<div className="space-y-4">
						<OtpInput
							value={flow.code}
							onChange={flow.setCode}
							onComplete={flow.verifyAndSignIn}
							autoFocus
							disabled={flow.submitting}
						/>

						{flow.error && (
							<p className="text-sm text-accent text-center">{flow.error}</p>
						)}

						<div className="flex items-center justify-between">
							<button
								type="button"
								onClick={flow.backToEmail}
								className="text-sm text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
							>
								Use a different email
							</button>
							<ResendCodeButton onResend={flow.resend} />
						</div>
					</div>
				)}
			</div>
		</div>,
		document.body,
	);
}
