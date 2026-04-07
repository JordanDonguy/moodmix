import NowPlayingInfo from "../player/NowPlayingInfo";
import ProgressBar from "../player/ProgressBar";
import TransportControls from "../player/TransportControls";
import VolumeControl from "../player/VolumeControl";

/**
 * Bottom player bar — pure layout composition.
 *
 * Each child component subscribes to the player store independently,
 * so PlayerBar itself never re-renders during playback.
 */
export default function PlayerBar() {
	return (
		<div className="fixed bottom-0 left-0 right-0 z-50 bg-bg-primary/91 backdrop-blur-[3px] border-t border-border animate-slide-up">
			{/* -- Desktop -- */}
			<div className="hidden sm:flex items-center gap-4 px-4 h-18">
				<div className="w-1/4 min-w-0">
					<NowPlayingInfo />
				</div>

				<div className="flex-1 flex flex-col items-center gap-1 max-w-xl mx-auto">
					<TransportControls />
					<ProgressBar />
				</div>

				<div className="w-1/4 flex justify-end">
					<VolumeControl />
				</div>
			</div>

			{/* -- Mobile -- */}
			<div className="sm:hidden px-3 py-2 space-y-1.5">
				<div className="flex items-center gap-3">
					<NowPlayingInfo compact />
					<TransportControls />
				</div>
				<ProgressBar />
			</div>
		</div>
	);
}
