import { Mic, MicOff } from "lucide-react";

interface VocalToggleProps {
	instrumental: boolean;
	onChange: (v: boolean) => void;
}

export default function VocalToggle({
	instrumental,
	onChange,
}: VocalToggleProps) {
	return (
		<button
			type="button"
			aria-label={instrumental ? "Showing instrumental only" : "Showing all mixes"}
			onClick={() => onChange(!instrumental)}
			className={`p-2 mr-3.5 lg:mr-0 rounded-lg transition-colors cursor-pointer ${
				instrumental
					? "bg-accent/15 text-accent"
					: "text-text-primary hover:opacity-80"
			}`}
		>
			{instrumental ? <MicOff size={18} /> : <Mic size={18} />}
		</button>
	);
}
