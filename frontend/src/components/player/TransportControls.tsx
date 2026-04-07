import {
	FastForward,
	Pause,
	Play,
	Rewind,
	SkipBack,
	SkipForward,
} from "lucide-react";
import { usePlayerStore } from "../../store/playerStore";
import Button from "../ui/Button";

export default function TransportControls() {
	const currentMix = usePlayerStore((s) => s.currentMix);
	const isPlaying = usePlayerStore((s) => s.isPlaying);
	const pause = usePlayerStore((s) => s.pause);
	const resume = usePlayerStore((s) => s.resume);
	const next = usePlayerStore((s) => s.next);
	const prev = usePlayerStore((s) => s.prev);
	const skipChapter = usePlayerStore((s) => s.skipChapter);

	const disabled = !currentMix;

	return (
		<div className="flex items-center gap-3">
			<Button onClick={prev} disabled={disabled} aria-label="Previous mix">
				<SkipBack size={18} />
			</Button>
			<Button
				onClick={() => skipChapter("prev")}
				disabled={disabled}
				aria-label="Previous chapter"
			>
				<Rewind size={18} />
			</Button>
			<Button
				variant="primary"
				onClick={isPlaying ? pause : resume}
				disabled={disabled}
				aria-label={isPlaying ? "Pause" : "Play"}
			>
				{isPlaying ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
			</Button>
			<Button
				onClick={() => skipChapter("next")}
				disabled={disabled}
				aria-label="Next chapter"
			>
				<FastForward size={18} />
			</Button>
			<Button onClick={next} disabled={disabled} aria-label="Next mix">
				<SkipForward size={18} />
			</Button>
		</div>
	);
}
