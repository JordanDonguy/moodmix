import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { applyTheme, useThemeStore } from "./store/themeStore";

// Apply stored theme before first render to avoid flash
applyTheme(useThemeStore.getState().theme);

// Auto-reload when cached JS chunks no longer exist after a deploy.
// Vite's lazy imports will throw on stale hashes; a single reload fetches
// the new index.html which points to the current chunks.
window.addEventListener("vite:preloadError", () => {
	window.location.reload();
});

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			staleTime: 1000 * 60 * 2, // 2 min
			refetchOnWindowFocus: false,
			retry: 1,
		},
	},
});

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");

createRoot(rootEl).render(
	<StrictMode>
		<QueryClientProvider client={queryClient}>
			<BrowserRouter>
				<App />
			</BrowserRouter>
		</QueryClientProvider>
	</StrictMode>,
);
