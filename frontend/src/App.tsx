import MobileNavbar from "./components/layout/MobileNavbar";
import Navbar from "./components/layout/Navbar";
import QuickTags from "./components/search/QuickTags";

export default function App() {
	return (
		<div className="min-h-screen bg-bg-primary">
			<Navbar />
			<MobileNavbar />
			<QuickTags />

		</div>
	);
}
