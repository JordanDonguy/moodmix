import { type FormEvent, useCallback, useState } from "react";
import { requestCode, verifyCode } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuthStore } from "../store/authStore";

export type SigninStep = "email" | "code";

interface UseSigninFlowOptions {
	/** Called after a successful verify-code so the caller can dismiss the
	 * modal, navigate, or whatever it needs. */
	onSuccess?: () => void;
}

/**
 * Two-step email-code sign-in state machine plus the Google redirect.
 *
 * Owns the form state (email / code / step), the API orchestration (request
 * → verify → store update), and the error → user-message mapping. Components
 * read the result and just render — they shouldn't import api/auth directly.
 */
export function useSigninFlow({ onSuccess }: UseSigninFlowOptions = {}) {
	const setUser = useAuthStore((s) => s.setUser);

	const [step, setStep] = useState<SigninStep>("email");
	const [email, setEmail] = useState("");
	const [code, setCode] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// `reset` is wrapped in useCallback so consumers (e.g. LoginModal's
	// "reset on open" effect) can depend on it without re-firing every
	// render. setState setters are already stable, so empty deps are safe.
	const reset = useCallback(() => {
		setStep("email");
		setEmail("");
		setCode("");
		setError(null);
	}, []);

	async function submitEmail(e: FormEvent) {
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

	async function verifyAndSignIn(submittedCode: string) {
		setError(null);
		setSubmitting(true);
		try {
			const session = await verifyCode(email, submittedCode);
			setUser(session.user);
			onSuccess?.();
		} catch (err) {
			setError(messageFor(err));
			setCode("");
		} finally {
			setSubmitting(false);
		}
	}

	async function resend() {
		setError(null);
		try {
			await requestCode(email);
		} catch (err) {
			setError(messageFor(err));
		}
	}

	function backToEmail() {
		setStep("email");
	}

	function signInWithGoogle() {
		// Full-page redirect (not fetch) — OAuth's redirect chain only works
		// with real navigations. Backend handles the round-trip and bounces
		// back to the app with session cookies set.
		const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
		window.location.href = `${apiUrl}/api/auth/google`;
	}

	return {
		step,
		email,
		code,
		submitting,
		error,
		setEmail,
		setCode,
		submitEmail,
		verifyAndSignIn,
		resend,
		backToEmail,
		signInWithGoogle,
		reset,
	} as const;
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
