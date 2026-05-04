import { useEffect, useRef } from "react";
import { toast } from "react-toastify";
import { useAuthStore } from "../store/authStore";

/**
 * Read the `?auth=…` marker the backend appends after a Google OAuth
 * callback, surface the matching toast, and strip the marker from the URL.
 *
 * Success path is two-phase: we set a flag on first mount (so a refresh
 * doesn't replay the toast), then wait for `hydrate()` to populate the user
 * before firing the personalized "Signed in as user@…" message. Failure
 * path is one-shot — it doesn't depend on auth state.
 */
export function useOauthRedirectFeedback() {
	const user = useAuthStore((s) => s.user);
	const pendingSuccessToast = useRef(false);

	// On first mount, classify the redirect marker and strip it. Pending
	// success is deferred to the second effect below, so the toast can
	// include the user's email once hydration resolves.
	useEffect(() => {
		const params = new URLSearchParams(window.location.search);
		const authFlag = params.get("auth");
		if (!authFlag) return;

		if (authFlag === "signed_in") {
			pendingSuccessToast.current = true;
		} else if (authFlag === "oauth_failed") {
			toast.error("Google sign-in failed. Please try again.");
		}

		params.delete("auth");
		const cleaned = params.toString();
		const newUrl =
			window.location.pathname +
			(cleaned ? `?${cleaned}` : "") +
			window.location.hash;
		window.history.replaceState({}, "", newUrl);
	}, []);

	// Fire the personalized toast as soon as hydration resolves with a user.
	useEffect(() => {
		if (pendingSuccessToast.current && user) {
			toast.success(`Signed in as ${user.email}`);
			pendingSuccessToast.current = false;
		}
	}, [user]);
}
