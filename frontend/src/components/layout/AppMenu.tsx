import { Info, LogIn, LogOut, Moon, Sun, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import { useAuthStore } from "../../store/authStore";
import { useSettingsStore } from "../../store/settingsStore";
import { useThemeStore } from "../../store/themeStore";
import { ToggleSwitch } from "../ui/ToggleSwitch";
import { Tooltip } from "../ui/Tooltip";

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
	const smartPlay = useSettingsStore((s) => s.smartPlay);
	const toggleSmartPlay = useSettingsStore((s) => s.toggleSmartPlay);
	const user = useAuthStore((s) => s.user);
	const openLoginModal = useAuthStore((s) => s.openLoginModal);
	const signOut = useAuthStore((s) => s.signOut);

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

	function handleSignIn() {
		setOpen(false);
		openLoginModal();
	}

	async function handleSignOut() {
		setOpen(false);
		await signOut();
		toast.success("Signed out");
	}

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
					className="absolute right-0 top-full mt-1 min-w-52 max-w-72 rounded-md border border-border bg-bg-primary/98 shadow-lg py-1 z-50 animate-menu-open-top-right"
				>
					{user ? (
						<>
							<div className="px-3 py-2 text-xs text-text-muted">
								<p>Signed in as</p>
								<p className="text-text-primary truncate" title={user.email}>
									{user.email}
								</p>
							</div>
							<div className="my-1 border-t border-border" />
						</>
					) : (
						<>
							<button
								type="button"
								role="menuitem"
								onClick={handleSignIn}
								className="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors cursor-pointer"
							>
								<LogIn size={16} />
								<span>Sign in</span>
							</button>
							<div className="my-1 border-t border-border" />
						</>
					)}

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
						role="menuitemcheckbox"
						aria-checked={smartPlay}
						onClick={toggleSmartPlay}
						className="flex w-full items-center justify-between px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors cursor-pointer"
					>
						<span className="flex items-center gap-1.5">
							Smart play
							<Tooltip content="When on, picks a mix with a similar feel after the current one. When off, simply plays the next mix in the list.">
								<span className="text-text-muted hover:text-text-secondary transition-colors">
									<Info size={14} />
								</span>
							</Tooltip>
						</span>
						<ToggleSwitch checked={smartPlay} />
					</button>

					<button
						type="button"
						role="menuitem"
						onClick={toggleTheme}
						className="flex w-full items-center justify-between px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors cursor-pointer"
					>
						<span>{theme === "dark" ? "Light theme" : "Dark theme"}</span>
						{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
					</button>

					{user && (
						<button
							type="button"
							role="menuitem"
							onClick={handleSignOut}
							className="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-bg-secondary transition-colors cursor-pointer"
						>
							<LogOut size={16} />
							<span>Sign out</span>
						</button>
					)}
				</div>
			)}
		</div>
	);
}
