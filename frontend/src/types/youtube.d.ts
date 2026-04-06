// YouTube IFrame API type declarations
interface YTPlayerEvent {
	data: number;
	target: YTPlayer;
}

interface YTPlayer {
	loadVideoById(videoId: string, startSeconds?: number): void;
	playVideo(): void;
	pauseVideo(): void;
	seekTo(seconds: number, allowSeekAhead: boolean): void;
	getCurrentTime(): number;
	getDuration(): number;
	getPlayerState(): number;
	setVolume(volume: number): void;
	isMuted(): boolean;
	mute(): void;
	unMute(): void;
	destroy(): void;
}

interface YTPlayerOptions {
	height?: string | number;
	width?: string | number;
	videoId?: string;
	playerVars?: {
		autoplay?: 0 | 1;
		controls?: 0 | 1;
		disablekb?: 0 | 1;
		modestbranding?: 0 | 1;
		rel?: 0 | 1;
		playsinline?: 0 | 1;
	};
	events?: {
		onReady?: (event: YTPlayerEvent) => void;
		onStateChange?: (event: YTPlayerEvent) => void;
		onError?: (event: YTPlayerEvent) => void;
	};
}

interface YTStatic {
	Player: new (elementOrId: string | HTMLElement, options: YTPlayerOptions) => YTPlayer;
	PlayerState: {
		UNSTARTED: -1;
		ENDED: 0;
		PLAYING: 1;
		PAUSED: 2;
		BUFFERING: 3;
		CUED: 5;
	};
}

interface Window {
	YT: YTStatic;
	onYouTubeIframeAPIReady: (() => void) | undefined;
}
