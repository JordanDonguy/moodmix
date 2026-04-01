export interface Genre {
	id: string;
	name: string;
	slug: string;
}

export interface Chapter {
	time: number;
	title: string;
}

export interface Mix {
	id: string;
	youtube_id: string;
	title: string;
	channel_name: string | null;
	duration_seconds: number;
	thumbnail_url: string | null;
	mood: number | null;
	energy: number | null;
	instrumentation: number | null;
	has_vocals: boolean | null;
	genres: Genre[];
	chapters: Chapter[] | null;
}

export interface SearchResponse {
	mixes: Mix[];
	total: number;
	limit: number;
	offset: number;
}

export interface AiSearchInferred {
	mood: number | null;
	energy: number | null;
	instrumentation: number | null;
	genres: string[];
	instrumental: boolean;
}

export interface AiSearchResponse {
	inferred: AiSearchInferred;
	mixes: Mix[];
	total: number;
}
