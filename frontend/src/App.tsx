import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import HomePage from "./pages/HomePage";
import { usePlayerStore } from "./store/playerStore";

const PlayerBar = lazy(() => import("./components/layout/PlayerBar"));
const YouTubePlayer = lazy(() => import("./components/player/YouTubePlayer"));

const InfoLayout = lazy(() => import("./pages/info/InfoLayout"));
const AboutPage = lazy(() => import("./pages/info/AboutPage"));
const HelpPage = lazy(() => import("./pages/info/HelpPage"));
const PrivacyPage = lazy(() => import("./pages/info/PrivacyPage"));
const TermsPage = lazy(() => import("./pages/info/TermsPage"));
const ContactPage = lazy(() => import("./pages/info/ContactPage"));

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
			<Routes>
				<Route path="/" element={<HomePage />} />
				<Route
					path="/info"
					element={
						<Suspense>
							<InfoLayout />
						</Suspense>
					}
				>
					<Route index element={<Navigate to="about" replace />} />
					<Route path="about" element={<AboutPage />} />
					<Route path="help" element={<HelpPage />} />
					<Route path="privacy" element={<PrivacyPage />} />
					<Route path="terms" element={<TermsPage />} />
					<Route path="contact" element={<ContactPage />} />
				</Route>
				<Route path="*" element={<Navigate to="/" replace />} />
			</Routes>

			<Suspense>
				<PlayerBar />
				<YouTubePlayer />
			</Suspense>
		</div>
	);
}
