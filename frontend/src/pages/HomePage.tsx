import { lazy, Suspense } from "react";

import Navbar from "../components/layout/Navbar";
import MixGrid from "../components/mixes/MixGrid";
import QuickTags from "../components/search/QuickTags";

const MobileNavbar = lazy(() => import("../components/layout/MobileNavbar"));

export default function HomePage() {
	return (
		<>
			<div className="sr-only">
				<h1>MoodMix - Background Music Mixes to Focus and Relax</h1>
				<p>
					Hand-picked YouTube music mixes crafted by real human curators, no AI-generated music. 
					Find the perfect soundtrack for your work, study, or relaxation.
				</p>
			</div>
			<Navbar />
			<Suspense>
				<MobileNavbar />
			</Suspense>
			<QuickTags />

			<main className="sm:px-4 py-6 pb-24">
				<MixGrid />
			</main>
		</>
	);
}
