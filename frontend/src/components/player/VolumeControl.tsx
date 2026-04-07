import { Volume2, VolumeOff } from "lucide-react";
import { usePlayerStore } from "../../store/playerStore";
import Button from "../ui/Button";
import Slider from "../ui/Slider";

export default function VolumeControl() {
	const volume = usePlayerStore((s) => s.volume);
	const muted = usePlayerStore((s) => s.muted);
	const setVolume = usePlayerStore((s) => s.setVolume);
	const toggleMute = usePlayerStore((s) => s.toggleMute);

	const effectiveVolume = muted ? 0 : volume;

	return (
		<div className="flex items-center gap-2">
			<Button onClick={toggleMute} aria-label={muted ? "Unmute" : "Mute"}>
				{muted || volume === 0 ? <VolumeOff size={18} /> : <Volume2 size={18} />}
			</Button>
			<Slider
				value={effectiveVolume}
				onChange={setVolume}
				ariaLabel="Volume"
				className="w-24"
			/>
		</div>
	);
}
