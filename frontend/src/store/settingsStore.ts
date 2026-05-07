import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
	/**
	 * When `true` (default), `playerStore.next()` picks the closest mix by
	 * genre overlap + mood-vector distance instead of advancing through the
	 * queue. When `false`, behaviour falls back to "next mix in line."
	 *
	 * Persisted across reloads so the user's preference is sticky on a
	 * given device until cross-device preference sync ships.
	 */
	smartPlay: boolean;

	toggleSmartPlay: () => void;
	setSmartPlay: (v: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
	persist(
		(set) => ({
			smartPlay: true,
			toggleSmartPlay: () => set((s) => ({ smartPlay: !s.smartPlay })),
			setSmartPlay: (v) => set({ smartPlay: v }),
		}),
		{ name: "moodmix-settings" },
	),
);
