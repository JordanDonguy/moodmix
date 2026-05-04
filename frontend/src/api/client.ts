const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.status = status;
		this.name = "ApiError";
	}
}

interface ApiFetchOptions extends RequestInit {
	/** Skip the silent-refresh retry on 401. Used by auth endpoints themselves
	 * to prevent recursion (refresh → 401 → refresh → 401 → ...). */
	skipRefreshOn401?: boolean;
}

/**
 * Coalesces concurrent refresh attempts into one request. If three API calls
 * 401 simultaneously, all three await the same refresh promise and then retry.
 * Avoids hammering /auth/refresh and racing the rotation chain.
 */
let pendingRefresh: Promise<boolean> | null = null;

async function attemptRefresh(): Promise<boolean> {
	if (pendingRefresh) return pendingRefresh;
	pendingRefresh = (async () => {
		try {
			const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
				method: "POST",
				credentials: "include",
				headers: { "Content-Type": "application/json" },
			});
			return res.ok;
		} catch {
			return false;
		} finally {
			// Clear after the chain so concurrent callers in the same tick see
			// the resolved promise; new calls after this line do a fresh refresh.
			queueMicrotask(() => {
				pendingRefresh = null;
			});
		}
	})();
	return pendingRefresh;
}

export async function apiFetch<T>(
	path: string,
	options?: ApiFetchOptions,
): Promise<T> {
	const { skipRefreshOn401, ...init } = options ?? {};

	const send = () =>
		fetch(`${BASE_URL}${path}`, {
			credentials: "include",
			headers: { "Content-Type": "application/json", ...init.headers },
			...init,
		});

	let res = await send();

	if (res.status === 401 && !skipRefreshOn401) {
		const refreshed = await attemptRefresh();
		if (refreshed) {
			res = await send();
		}
	}

	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new ApiError(
			res.status,
			(body as { error?: string }).error ?? res.statusText,
		);
	}

	// 204 / empty body → return undefined as T (caller's responsibility to
	// type the call site as Promise<void> in that case).
	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}
