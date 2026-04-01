import type { Genre } from "../types/mix";
import { apiFetch } from "./client";

export function getGenres(): Promise<Genre[]> {
	return apiFetch<Genre[]>("/api/genres");
}
