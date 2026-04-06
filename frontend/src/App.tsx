import { lazy, Suspense, useEffect } from "react";

import Navbar from "./components/layout/Navbar";
import MixGrid from "./components/mixes/MixGrid";
import QuickTags from "./components/search/QuickTags";
import { usePlayerStore } from "./store/playerStore";

const MobileNavbar = lazy(() => import("./components/layout/MobileNavbar"));
const PlayerBar = lazy(() => import("./components/layout/PlayerBar"));
const YouTubePlayer = lazy(() => import("./components/player/YouTubePlayer"));

function useDocumentTitle() {
	const currentMix = usePlayerStore((s) => s.currentMix);
	useEffect(() => {
		document.title = currentMix ? `${currentMix.title} — MoodMix` : "MoodMix";
	}, [currentMix]);
}

function useSpacebarPlayPause() {
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.code !== "Space") return;
			const tag = (e.target as HTMLElement).tagName;
			if (tag === "INPUT" || tag === "TEXTAREA") return;
			e.preventDefault();
			(document.activeElement as HTMLElement)?.blur();
			const { currentMix, isPlaying, pause, resume } =
				usePlayerStore.getState();
			if (!currentMix) return;
			if (isPlaying) pause();
			else resume();
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, []);
}

export default function App() {
	useDocumentTitle();
	useSpacebarPlayPause();

	return (
		<div className="min-h-screen bg-bg-primary">
			<Navbar />
			<Suspense>
				<MobileNavbar />
			</Suspense>
			<QuickTags />

			<main className="px-4 py-6 pb-24">
				<MixGrid />
			</main>

			<Suspense>
				<PlayerBar />
				<YouTubePlayer />
			</Suspense>
		</div>
	);
}
