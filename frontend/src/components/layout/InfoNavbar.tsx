import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import AppMenu from "./AppMenu";

export default function InfoNavbar() {
	return (
		<nav className="flex items-center justify-between px-4 h-14 lg:h-16 bg-bg-primary/91 backdrop-blur-[3px] border-b border-border sticky top-0 z-40">
			<Link
				to="/"
				className="flex items-center gap-2 text-lg font-semibold group"
			>
				<ArrowLeft
					size={18}
					className="text-text-secondary group-hover:text-text-primary transition-colors"
				/>
				<div>
					<span className="text-accent">Mood</span>
					<span className="text-text-primary">Mix</span>
				</div>
			</Link>

			<AppMenu />
		</nav>
	);
}
