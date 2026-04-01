import type { AiSearchResponse, SearchResponse } from "../types/mix";
import { apiFetch } from "./client";

export interface SearchParams {
	mood?: number | null;
	energy?: number | null;
	instrumentation?: number | null;
	genres?: string[];
	instrumental?: boolean;
	seed?: number;
	limit?: number;
	offset?: number;
}

export function searchMixes(params: SearchParams): Promise<SearchResponse> {
	const query = new URLSearchParams();

	if (params.mood != null) query.set("mood", String(params.mood));
	if (params.energy != null) query.set("energy", String(params.energy));
	if (params.instrumentation != null)
		query.set("instrumentation", String(params.instrumentation));
	if (params.genres?.length) query.set("genres", params.genres.join(","));
	if (params.instrumental) query.set("instrumental", "true");
	if (params.seed != null) query.set("seed", String(params.seed));
	if (params.limit != null) query.set("limit", String(params.limit));
	if (params.offset != null) query.set("offset", String(params.offset));

	return apiFetch<SearchResponse>(`/api/mixes/search?${query}`);
}

export function aiSearch(query: string): Promise<AiSearchResponse> {
	return apiFetch<AiSearchResponse>("/api/mixes/ai-search", {
		method: "POST",
		body: JSON.stringify({ query }),
	});
}

export function reportUnavailable(id: string): Promise<void> {
	return apiFetch<void>(`/api/mixes/${id}/report-unavailable`, {
		method: "POST",
	});
}
