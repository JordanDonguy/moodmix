import { useState } from "react";

const SESSION_KEY = "moodmix_admin_key";

export function useAdminAuth() {
	const [apiKey, setApiKey] = useState<string>(
		() => sessionStorage.getItem(SESSION_KEY) ?? "",
	);

	function setKey(k: string) {
		sessionStorage.setItem(SESSION_KEY, k);
		setApiKey(k);
	}

	function signOut() {
		sessionStorage.removeItem(SESSION_KEY);
		setApiKey("");
	}

	return { apiKey, setKey, signOut };
}
