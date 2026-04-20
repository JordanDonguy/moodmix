import { Moon, Sun, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useThemeStore } from "../../store/themeStore";

type MenuItem = { to: string; label: string };

const ITEMS: MenuItem[] = [
	{ to: "/info/about", label: "About" },
	{ to: "/info/help", label: "Help" },
	{ to: "/info/privacy", label: "Privacy" },
	{ to: "/info/terms", label: "Terms" },
	{ to: "/info/contact", label: "Contact" },
];

export default function AppMenu() {
	const [open, setOpen] = useState(false);
	const ref = useRef<HTMLDivElement>(null);
	const { theme, toggleTheme } = useThemeStore();

	useEffect(() => {
		if (!open) return;
		const handleClick = (e: MouseEvent) => {
			if (!ref.current?.contains(e.target as Node)) setOpen(false);
		};
		const handleKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		document.addEventListener("mousedown", handleClick);
		document.addEventListener("keydown", handleKey);
		return () => {
			document.removeEventListener("mousedown", handleClick);
			document.removeEventListener("keydown", handleKey);
		};
	}, [open]);

	return (
		<div ref={ref} className="relative">
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				aria-label="Open menu"
				aria-expanded={open}
				aria-haspopup="menu"
				className="p-2 text-text-primary hover:opacity-80 transition-colors cursor-pointer"
			>
				<User size={20} />
			</button>

			{open && (
				<div
					role="menu"
					className="absolute right-0 top-full mt-1 min-w-44 rounded-md border border-border bg-bg-primary/98 shadow-lg py-1 z-50 animate-menu-open-top-right"
				>
					{ITEMS.map((item) => (
						<Link
							key={item.to}
							to={item.to}
							role="menuitem"
							onClick={() => setOpen(false)}
							className="block px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors"
						>
							{item.label}
						</Link>
					))}

					<div className="my-1 border-t border-border" />

					<button
						type="button"
						role="menuitem"
						onClick={toggleTheme}
						className="flex w-full items-center justify-between px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors cursor-pointer"
					>
						<span>{theme === "dark" ? "Light theme" : "Dark theme"}</span>
						{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
					</button>
				</div>
			)}
		</div>
	);
}
