import { lazy, Suspense } from "react";

import Navbar from "../components/layout/Navbar";
import MixGrid from "../components/mixes/MixGrid";
import QuickTags from "../components/search/QuickTags";

const MobileNavbar = lazy(() => import("../components/layout/MobileNavbar"));

export default function HomePage() {
	return (
		<>
			<Navbar />
			<Suspense>
				<MobileNavbar />
			</Suspense>
			<QuickTags />

			<main className="px-4 py-6 pb-24">
				<MixGrid />
			</main>
		</>
	);
}
