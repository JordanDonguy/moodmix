import MobileNavbar from "./components/layout/MobileNavbar";
import Navbar from "./components/layout/Navbar";
import MixGrid from "./components/mixes/MixGrid";
import QuickTags from "./components/search/QuickTags";

export default function App() {
	return (
		<div className="min-h-screen bg-bg-primary">
			<Navbar />
			<MobileNavbar />
			<QuickTags />

			<main className="px-4 py-6">
				<MixGrid />
			</main>
		</div>
	);
}
