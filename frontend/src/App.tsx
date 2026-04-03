import { useEffect } from "react";
import MobileNavbar from "./components/layout/MobileNavbar";
import Navbar from "./components/layout/Navbar";
import PlayerBar from "./components/layout/PlayerBar";
import MixGrid from "./components/mixes/MixGrid";
import YouTubePlayer from "./components/player/YouTubePlayer";
import QuickTags from "./components/search/QuickTags";
import { usePlayerStore } from "./store/playerStore";

function useDocumentTitle() {
	const currentMix = usePlayerStore((s) => s.currentMix);
	useEffect(() => {
		document.title = currentMix ? `${currentMix.title} — MoodMix` : "MoodMix";
	}, [currentMix]);
}

function useMediaKeys() {
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			const store = usePlayerStore.getState();
			if (e.code === "Space") {
				const tag = (e.target as HTMLElement).tagName;
				if (tag === "INPUT" || tag === "TEXTAREA") return;
				e.preventDefault();
				if (!store.currentMix) return;
				if (store.isPlaying) store.pause();
				else store.resume();
			} else if (e.code === "MediaTrackNext") {
				e.preventDefault();
				store.next();
			} else if (e.code === "MediaTrackPrevious") {
				e.preventDefault();
				store.prev();
			} else if (e.code === "MediaPlayPause") {
				e.preventDefault();
				if (!store.currentMix) return;
				if (store.isPlaying) store.pause();
				else store.resume();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, []);
}

export default function App() {
	useDocumentTitle();
	useMediaKeys();
	return (
		<div className="min-h-screen bg-bg-primary">
			<Navbar />
			<MobileNavbar />
			<QuickTags />

			<main className="px-4 py-6 pb-24">
				<MixGrid />
			</main>

			<PlayerBar />
			<YouTubePlayer />
		</div>
	);
}
