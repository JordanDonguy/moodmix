import { apiFetch } from "./client";

export interface ContactPayload {
	name: string;
	email: string;
	message: string;
	website: string;
}

export interface ContactResponse {
	sent: boolean;
}

export function submitContact(
	payload: ContactPayload,
): Promise<ContactResponse> {
	return apiFetch<ContactResponse>("/api/contact", {
		method: "POST",
		body: JSON.stringify(payload),
	});
}
