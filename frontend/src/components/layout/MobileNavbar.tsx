import { AnimatePresence, motion } from "framer-motion";
import {
	Cpu,
	Drum,
	Moon,
	MoonStar,
	Search,
	SlidersHorizontal,
	Sofa,
	Sun,
	X,
	Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchStore } from "../../store/searchStore";
import { useThemeStore } from "../../store/themeStore";
import AiSearchBar from "../search/AiSearchBar";
import GenreDropdown from "../search/GenreDropdown";
import MoodSlider from "../search/MoodSlider";
import ResetFilters from "../search/ResetFilters";
import VocalToggle from "../search/VocalToggle";

export default function MobileNavbar() {
	const [filtersOpen, setFiltersOpen] = useState(false);
	const [searchOpen, setSearchOpen] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);
	const prevHeightRef = useRef(0);

	// Track sticky container height changes and adjust scroll to match
	useEffect(() => {
		const el = containerRef.current;
		if (!el) return;
		prevHeightRef.current = el.offsetHeight;

		const observer = new ResizeObserver(() => {
			const newHeight = el.offsetHeight;
			const diff = newHeight - prevHeightRef.current;
			if (diff !== 0 && window.scrollY > 0) {
				window.scrollTo({
					top: window.scrollY - diff,
					behavior: "instant",
				});
			}
			prevHeightRef.current = newHeight;
		});

		observer.observe(el);
		return () => observer.disconnect();
	}, []);

	const {
		mood,
		energy,
		instrumentation,
		genres,
		instrumental,
		setMood,
		setEnergy,
		setInstrumentation,
		toggleGenre,
		clearGenres,
		setInstrumental,
	} = useSearchStore();

	const { theme, toggleTheme } = useThemeStore();

	const activeFilterCount =
		(mood !== null ? 1 : 0) +
		(energy !== null ? 1 : 0) +
		(instrumentation !== null ? 1 : 0) +
		genres.length +
		(instrumental ? 1 : 0);

	return (
		<div ref={containerRef} className="lg:hidden sticky top-0 z-40">
			{/* Top bar */}
			<div className="flex items-center justify-between px-4 h-14 bg-bg-primary/91 backdrop-blur-[3px] border-b border-border">
				<a href="/#" className="text-lg font-semibold">
					<span className="text-accent">Mood</span>
					<span className="text-text-primary">Mix</span>
				</a>

				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={toggleTheme}
						className="p-2 text-text-primary hover:opacity-80 transition-colors cursor-pointer"
					>
						{theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
					</button>

					<button
						type="button"
						onClick={() => {
							setSearchOpen((o) => !o);
							setFiltersOpen(false);
						}}
						className={`p-2 rounded-lg transition-colors cursor-pointer ${
							searchOpen ? "text-accent" : "text-text-primary hover:opacity-80"
						}`}
					>
						{searchOpen ? <X size={20} /> : <Search size={20} />}
					</button>

					<button
						type="button"
						onClick={() => {
							setFiltersOpen((o) => !o);
							setSearchOpen(false);
						}}
						className={`relative p-2 rounded-lg transition-colors cursor-pointer ${
							filtersOpen ? "text-accent" : "text-text-primary hover:opacity-80"
						}`}
					>
						<SlidersHorizontal size={20} />
						{activeFilterCount > 0 && (
							<span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-accent text-white text-[10px] flex items-center justify-center">
								{activeFilterCount}
							</span>
						)}
					</button>
				</div>
			</div>

			{/* Search panel */}
			<AnimatePresence>
				{searchOpen && (
					<motion.div
						initial={{ height: 0, opacity: 0 }}
						animate={{ height: "auto", opacity: 1 }}
						exit={{ height: 0, opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="overflow-hidden bg-bg-primary/91 backdrop-blur-[3px] border-b border-border"
					>
						<div className="px-4 py-3">
							<AiSearchBar />
						</div>
					</motion.div>
				)}
			</AnimatePresence>

			{/* Filters sheet */}
			<AnimatePresence>
				{filtersOpen && (
					<motion.div
						initial={{ height: 0, opacity: 0 }}
						animate={{ height: "auto", opacity: 1 }}
						exit={{ height: 0, opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="overflow-hidden bg-bg-primary/91 backdrop-blur-[3px] border-b border-border"
					>
						<div className="px-4 py-4 space-y-4">
							{/* Sliders with labels */}
							<div className="space-y-3">
								<span className="text-xs text-text-muted uppercase tracking-wider">
									Mood
								</span>
								<MoodSlider
									value={mood}
									onChange={setMood}
									leftIcon={MoonStar}
									rightIcon={Sun}
									leftTooltip="Dark"
									rightTooltip="Bright"
									gradientFrom="#6366f1"
									gradientTo="#f97316"
									expand
								/>
							</div>

							<div className="space-y-3">
								<span className="text-xs text-text-muted uppercase tracking-wider">
									Energy
								</span>
								<MoodSlider
									value={energy}
									onChange={setEnergy}
									leftIcon={Sofa}
									rightIcon={Zap}
									leftTooltip="Chill"
									rightTooltip="Dynamic"
									gradientFrom="#14b8a6"
									gradientTo="#eab308"
									expand
								/>
							</div>

							<div className="space-y-3">
								<span className="text-xs text-text-muted uppercase tracking-wider">
									Instrumentation
								</span>
								<MoodSlider
									value={instrumentation}
									onChange={setInstrumentation}
									leftIcon={Drum}
									rightIcon={Cpu}
									leftTooltip="Organic"
									rightTooltip="Electronic"
									gradientFrom="#d97706"
									gradientTo="#8b5cf6"
									expand
								/>
							</div>

							{/* Vocal toggle + reset + genres */}
							<div className="pt-2">
								<div className="flex justify-between items-start">
									<GenreDropdown
										selected={genres}
										onToggle={toggleGenre}
										onClear={clearGenres}
										inline
									/>
									<div className="flex items-center gap-2 shrink-0">
										<ResetFilters size={18} />
										<VocalToggle
											instrumental={instrumental}
											onChange={setInstrumental}
										/>
									</div>
								</div>
							</div>
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</div>
	);
}
