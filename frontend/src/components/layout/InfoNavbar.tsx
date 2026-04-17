import { ArrowLeft, Moon, Sun } from "lucide-react";
import { Link } from "react-router-dom";
import { useThemeStore } from "../../store/themeStore";

export default function InfoNavbar() {
	const { theme, toggleTheme } = useThemeStore();

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

			<button
				type="button"
				onClick={toggleTheme}
				aria-label={
					theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
				}
				className="p-2 text-text-primary hover:opacity-80 transition-colors cursor-pointer"
			>
				{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
			</button>
		</nav>
	);
}
