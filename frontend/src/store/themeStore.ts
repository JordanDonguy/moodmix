import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "dark" | "light";

interface ThemeState {
	theme: Theme;
	toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
	persist(
		(set, get) => ({
			theme: "dark",
			toggleTheme: () => {
				const next: Theme = get().theme === "dark" ? "light" : "dark";
				applyTheme(next);
				set({ theme: next });
			},
		}),
		{ name: "moodmix-theme" },
	),
);

export function applyTheme(theme: Theme): void {
	document.documentElement.classList.toggle("dark", theme === "dark");
}
