import { Cpu, Drum, Moon, MoonStar, Sofa, Sun, Zap } from "lucide-react";
import { useSearchStore } from "../../store/searchStore";
import { useThemeStore } from "../../store/themeStore";
import AiSearchBar from "../search/AiSearchBar";
import GenreDropdown from "../search/GenreDropdown";
import MoodSlider from "../search/MoodSlider";
import ResetFilters from "../search/ResetFilters";
import VocalToggle from "../search/VocalToggle";

export default function Navbar() {
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

	return (
		<nav className="hidden lg:flex items-center gap-2 xl:gap-3 px-4 h-16 bg-bg-primary/91 backdrop-blur-[3px] border-b border-border sticky top-0 z-40">
			{/* Logo */}
			<a href="/#" className="text-lg font-semibold mr-2 shrink-0">
				<span className="text-accent">Mood</span>
				<span className="text-text-primary">Mix</span>
			</a>

			{/* Divider */}
			<div className="w-px h-6 bg-border shrink-0" />

			{/* Sliders */}
			<MoodSlider
				value={mood}
				onChange={setMood}
				leftIcon={MoonStar}
				rightIcon={Sun}
				leftTooltip="Dark"
				rightTooltip="Bright"
				gradientFrom="#6366f1"
				gradientTo="#f97316"
			/>

			<div className="w-px h-6 bg-border shrink-0" />

			<MoodSlider
				value={energy}
				onChange={setEnergy}
				leftIcon={Sofa}
				rightIcon={Zap}
				leftTooltip="Chill"
				rightTooltip="Dynamic"
				gradientFrom="#14b8a6"
				gradientTo="#eab308"
			/>

			<div className="w-px h-6 bg-border shrink-0" />

			<MoodSlider
				value={instrumentation}
				onChange={setInstrumentation}
				leftIcon={Drum}
				rightIcon={Cpu}
				leftTooltip="Organic"
				rightTooltip="Electronic"
				gradientFrom="#d97706"
				gradientTo="#8b5cf6"
			/>

			<div className="w-px h-6 bg-border shrink-0" />

			{/* Vocal toggle */}
			<VocalToggle instrumental={instrumental} onChange={setInstrumental} />

			<div className="w-px h-6 bg-border shrink-0" />

			{/* Genres */}
			<GenreDropdown
				selected={genres}
				onToggle={toggleGenre}
				onClear={clearGenres}
			/>

			{/* Reset all filters */}
			<ResetFilters size={16} divider />

			{/* Spacer */}
			<div className="flex-1" />

			{/* AI Search */}
			<AiSearchBar />

			{/* Theme toggle */}
			<button
				type="button"
				onClick={toggleTheme}
				title={theme === "dark" ? "Switch to light" : "Switch to dark"}
				className="p-2 text-text-primary hover:opacity-80 transition-colors cursor-pointer"
			>
				{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
			</button>
		</nav>
	);
}
