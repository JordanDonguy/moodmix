import { apiFetch } from "./client";

export interface User {
	id: string;
	email: string;
	created_at: string;
	last_login_at: string | null;
}

export interface SessionResponse {
	user: User;
}

/** Send a one-time sign-in code to the supplied email. Always 204 on success. */
export function requestCode(email: string): Promise<void> {
	return apiFetch<void>("/api/auth/request-code", {
		method: "POST",
		body: JSON.stringify({ email }),
		// Don't try to recover from auth failures here — request-code is the
		// entry point, an auth failure means the user isn't allowed to sign in.
		skipRefreshOn401: true,
	});
}

/** Verify a code and start a session. Sets HttpOnly cookies; returns the user. */
export function verifyCode(
	email: string,
	code: string,
): Promise<SessionResponse> {
	return apiFetch<SessionResponse>("/api/auth/verify-code", {
		method: "POST",
		body: JSON.stringify({ email, code }),
		skipRefreshOn401: true,
	});
}

/** Rotate the refresh cookie. Used internally by the refresh-on-401 retry. */
export function refresh(): Promise<SessionResponse> {
	return apiFetch<SessionResponse>("/api/auth/refresh", {
		method: "POST",
		skipRefreshOn401: true,
	});
}

/** Revoke the refresh token and clear the cookies. */
export function logout(): Promise<void> {
	return apiFetch<void>("/api/auth/logout", {
		method: "POST",
		skipRefreshOn401: true,
	});
}

/** Return the currently authenticated user. 401 if no valid session. */
export function me(): Promise<User> {
	return apiFetch<User>("/api/auth/me");
}
