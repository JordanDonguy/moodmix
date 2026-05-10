import type {
	ArtistListResponse,
	ArtistTracksResponse,
	FreshPreviewResponse,
} from "../types/catalog";
import { apiFetch } from "./client";

function adminHeaders(apiKey: string): HeadersInit {
	return { "X-API-Key": apiKey };
}

export function listArtists(
	apiKey: string,
	params: { search?: string; limit?: number; offset?: number } = {},
): Promise<ArtistListResponse> {
	const q = new URLSearchParams();
	if (params.search) q.set("search", params.search);
	if (params.limit != null) q.set("limit", String(params.limit));
	if (params.offset != null) q.set("offset", String(params.offset));
	return apiFetch<ArtistListResponse>(`/api/admin/artists?${q}`, {
		headers: adminHeaders(apiKey),
	});
}

export function getArtistTracks(
	apiKey: string,
	artistId: string,
): Promise<ArtistTracksResponse> {
	return apiFetch<ArtistTracksResponse>(`/api/admin/artists/${artistId}/tracks`, {
		headers: adminHeaders(apiKey),
	});
}

export function getFreshPreview(
	apiKey: string,
	trackId: string,
): Promise<FreshPreviewResponse> {
	return apiFetch<FreshPreviewResponse>(
		`/api/admin/tracks/${trackId}/fresh-preview`,
		{ headers: adminHeaders(apiKey) },
	);
}
