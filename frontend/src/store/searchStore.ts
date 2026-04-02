import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AiSearchInferred } from "../types/mix";

interface SearchState {
	mood: number | null;
	energy: number | null;
	instrumentation: number | null;
	genres: string[];
	instrumental: boolean;
	seed: number;

	setMood: (v: number | null) => void;
	setEnergy: (v: number | null) => void;
	setInstrumentation: (v: number | null) => void;
	toggleGenre: (slug: string) => void;
	clearGenres: () => void;
	setInstrumental: (v: boolean) => void;
	applyAiInferred: (inferred: AiSearchInferred) => void;
	resetAll: () => void;
	resetSeed: () => void;
}

export const useSearchStore = create<SearchState>()(
	persist(
		(set) => ({
			mood: null,
			energy: null,
			instrumentation: null,
			genres: [],
			instrumental: false,
			seed: Math.round(Math.random() * 10000) / 10000,

			setMood: (v) => set({ mood: v }),
			setEnergy: (v) => set({ energy: v }),
			setInstrumentation: (v) => set({ instrumentation: v }),
			toggleGenre: (slug) =>
				set((s) => ({
					genres: s.genres.includes(slug)
						? s.genres.filter((g) => g !== slug)
						: [...s.genres, slug],
				})),
			clearGenres: () => set({ genres: [] }),
			setInstrumental: (v) => set({ instrumental: v }),
			applyAiInferred: (inferred) =>
				set({
					mood: inferred.mood,
					energy: inferred.energy,
					instrumentation: inferred.instrumentation,
					genres: inferred.genres,
					instrumental: inferred.instrumental,
				}),
			resetAll: () =>
				set({
					mood: null,
					energy: null,
					instrumentation: null,
					genres: [],
					instrumental: false,
				}),
			resetSeed: () => set({ seed: newSeed() }),
		}),
		{
			name: "moodmix-search",
			partialize: (s) => ({
				mood: s.mood,
				energy: s.energy,
				instrumentation: s.instrumentation,
				genres: s.genres,
				instrumental: s.instrumental,
			}),
		},
	),
);

function newSeed(): number {
	return Math.round(Math.random() * 10000) / 10000;
}
