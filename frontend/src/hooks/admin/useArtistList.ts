import { useCallback, useEffect, useRef, useState } from "react";
import { listArtists } from "../../api/admin";
import type { ArtistListItem } from "../../types/catalog";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 300;

export function useArtistList(apiKey: string) {
	const [search, setSearch] = useState("");
	const [artists, setArtists] = useState<ArtistListItem[]>([]);
	const [total, setTotal] = useState(0);
	const [offset, setOffset] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

	const fetchArtists = useCallback(
		async (key: string, q: string, off: number) => {
			setLoading(true);
			setError(null);
			try {
				const res = await listArtists(key, {
					search: q,
					limit: PAGE_SIZE,
					offset: off,
				});
				setArtists(res.artists);
				setTotal(res.total);
			} catch {
				setError("Failed to load artists — check the API key.");
				setArtists([]);
			} finally {
				setLoading(false);
			}
		},
		[],
	);

	// Debounced search — also resets to page 1
	useEffect(() => {
		if (!apiKey) return;
		if (searchTimeout.current) clearTimeout(searchTimeout.current);
		searchTimeout.current = setTimeout(() => {
			setOffset(0);
			fetchArtists(apiKey, search, 0);
		}, SEARCH_DEBOUNCE_MS);
		return () => {
			if (searchTimeout.current) clearTimeout(searchTimeout.current);
		};
	}, [apiKey, search, fetchArtists]);

	// Page turns (the search effect resets offset to 0, so this only fires on
	// genuine page changes after the initial load)
	useEffect(() => {
		if (!apiKey) return;
		fetchArtists(apiKey, search, offset);
	}, [offset, apiKey, fetchArtists, search]);

	const totalPages = Math.ceil(total / PAGE_SIZE);
	const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

	function goToPage(page: number) {
		setOffset((page - 1) * PAGE_SIZE);
	}

	return {
		search,
		setSearch,
		artists,
		total,
		loading,
		error,
		totalPages,
		currentPage,
		goToPage,
	};
}
