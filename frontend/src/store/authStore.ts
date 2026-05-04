import { create } from "zustand";
import { logout as apiLogout, me, type User } from "../api/auth";
import { ApiError } from "../api/client";

interface AuthState {
	user: User | null;
	/** True after `hydrate()` has resolved at least once — useful to avoid
	 * flickering "signed out" UI on the first paint. */
	hydrated: boolean;
	loginModalOpen: boolean;

	hydrate: () => Promise<void>;
	signOut: () => Promise<void>;
	setUser: (user: User | null) => void;
	openLoginModal: () => void;
	closeLoginModal: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
	user: null,
	hydrated: false,
	loginModalOpen: false,

	hydrate: async () => {
		try {
			const user = await me();
			set({ user, hydrated: true });
		} catch (e) {
			// 401 is the expected "no session" path — treat as logged out.
			if (e instanceof ApiError && e.status === 401) {
				set({ user: null, hydrated: true });
				return;
			}
			// Other errors leave the user unset but mark as hydrated so the UI
			// can render. The next interaction will retry.
			set({ user: null, hydrated: true });
		}
	},

	signOut: async () => {
		try {
			await apiLogout();
		} catch {
			// Logout is fire-and-forget — even if the server is unreachable,
			// we should clear local state so the UI reflects the user's intent.
		}
		set({ user: null, loginModalOpen: false });
	},

	setUser: (user) => set({ user }),
	openLoginModal: () => set({ loginModalOpen: true }),
	closeLoginModal: () => set({ loginModalOpen: false }),
}));
