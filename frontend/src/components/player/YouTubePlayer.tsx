import { useCallback, useEffect, useRef } from "react";
import { reportUnavailable } from "../../api/mixes";
import { usePlayerStore } from "../../store/playerStore";

let apiLoaded = false;
const apiReady = new Promise<void>((resolve) => {
	if (typeof window !== "undefined" && window.YT) {
		resolve();
		return;
	}
	window.onYouTubeIframeAPIReady = () => resolve();
});

function loadApi() {
	if (apiLoaded) return;
	apiLoaded = true;
	const script = document.createElement("script");
	script.src = "https://www.youtube.com/iframe_api";
	document.head.appendChild(script);
}

export default function YouTubePlayer() {
	const playerRef = useRef<YTPlayer | null>(null);
	const readyRef = useRef(false);
	const loadingRef = useRef(false);
	const seekingRef = useRef(false);
	const intervalRef = useRef<number>(0);
	// Manual time tracking: record wall-clock time when playback starts/resumes
	const playStartedAtRef = useRef(0);
	const playStartedTimeRef = useRef(0);
	const currentMix = usePlayerStore((s) => s.currentMix);
	const isPlaying = usePlayerStore((s) => s.isPlaying);

	const startTracking = useCallback(() => {
		clearInterval(intervalRef.current);
		// Record when we started tracking for manual time calculation
		playStartedAtRef.current = Date.now();
		playStartedTimeRef.current = usePlayerStore.getState().currentTime;
		intervalRef.current = window.setInterval(() => {
			if (seekingRef.current) return;
			const elapsed = (Date.now() - playStartedAtRef.current) / 1000;
			const time = playStartedTimeRef.current + elapsed;
			const store = usePlayerStore.getState();
			store.setProgress(time, store.duration);
		}, 500);
	}, []);

	const stopTracking = useCallback(() => {
		clearInterval(intervalRef.current);
	}, []);

	// Load API on mount
	useEffect(() => {
		loadApi();
		apiReady.then(() => {
			new window.YT.Player("yt-player", {
				height: "1",
				width: "1",
				playerVars: {
					autoplay: 0,
					controls: 0,
					disablekb: 1,
					modestbranding: 1,
					rel: 0,
					playsinline: 1,
				},
				events: {
					onReady: (event) => {
						playerRef.current = event.target;
						readyRef.current = true;
						const mix = usePlayerStore.getState().currentMix;
						if (mix) {
							event.target.loadVideoById(mix.youtube_id);
						}
					},
					onStateChange: (event) => {
						const { setIsPlaying, next } = usePlayerStore.getState();
						switch (event.data) {
							case window.YT.PlayerState.PLAYING:
								loadingRef.current = false;
								setIsPlaying(true);
								startTracking();
								break;
							case window.YT.PlayerState.PAUSED:
								if (loadingRef.current) break;
								setIsPlaying(false);
								stopTracking();
								break;
							case window.YT.PlayerState.ENDED:
								stopTracking();
								next();
								break;
						}
					},
					onError: () => {
						const { currentMix: mix, next } = usePlayerStore.getState();
						if (mix) {
							reportUnavailable(mix.id).catch(() => {});
						}
						next();
					},
				},
			});
		});

		return () => {
			stopTracking();
			playerRef.current?.destroy();
		};
	}, [startTracking, stopTracking]);

	// Load new video when currentMix changes
	useEffect(() => {
		if (!readyRef.current || !playerRef.current || !currentMix) return;
		loadingRef.current = true;
		playerRef.current.loadVideoById(currentMix.youtube_id);
	}, [currentMix]);

	// Play/pause sync
	useEffect(() => {
		if (!readyRef.current || !playerRef.current || !currentMix) return;

		if (isPlaying) {
			playerRef.current.playVideo();
			startTracking();
		} else {
			playerRef.current.pauseVideo();
			stopTracking();
		}
	}, [isPlaying, currentMix, startTracking, stopTracking]);

	// Media Session API — hardware media keys + OS media controls
	useEffect(() => {
		if (!("mediaSession" in navigator)) return;
		navigator.mediaSession.setActionHandler("play", () =>
			usePlayerStore.getState().resume(),
		);
		navigator.mediaSession.setActionHandler("pause", () =>
			usePlayerStore.getState().pause(),
		);
		navigator.mediaSession.setActionHandler("nexttrack", () =>
			usePlayerStore.getState().next(),
		);
		navigator.mediaSession.setActionHandler("previoustrack", () =>
			usePlayerStore.getState().prev(),
		);
		return () => {
			navigator.mediaSession.setActionHandler("play", null);
			navigator.mediaSession.setActionHandler("pause", null);
			navigator.mediaSession.setActionHandler("nexttrack", null);
			navigator.mediaSession.setActionHandler("previoustrack", null);
		};
	}, []);

	// Keep OS media controls metadata in sync
	useEffect(() => {
		if (!("mediaSession" in navigator)) return;
		if (!currentMix) {
			navigator.mediaSession.metadata = null;
			return;
		}
		navigator.mediaSession.metadata = new MediaMetadata({
			title: currentMix.title,
			artist: currentMix.channel_name ?? "",
			artwork: [
				{
					src:
						currentMix.thumbnail_url ??
						`https://i.ytimg.com/vi/${currentMix.youtube_id}/hqdefault.jpg`,
					sizes: "480x360",
					type: "image/jpeg",
				},
			],
		});
	}, [currentMix]);

	// Keep OS playback state in sync
	useEffect(() => {
		if (!("mediaSession" in navigator)) return;
		navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
	}, [isPlaying]);

	// Volume sync
	useEffect(() => {
		const unsub = usePlayerStore.subscribe((state, prev) => {
			const player = playerRef.current;
			if (!player) return;
			if (state.volume !== prev.volume) {
				player.setVolume(state.volume);
			}
			if (state.muted !== prev.muted) {
				if (state.muted) player.mute();
				else player.unMute();
			}
		});
		return unsub;
	}, []);

	// Seek when user explicitly calls seekTo
	useEffect(() => {
		const unsub = usePlayerStore.subscribe((state, prev) => {
			if (
				state.pendingSeek !== null &&
				state.pendingSeek !== prev.pendingSeek
			) {
				seekingRef.current = true;
				playerRef.current?.seekTo(state.pendingSeek, true);
				usePlayerStore.setState({ pendingSeek: null });
				// Update manual tracking refs to the seek position
				playStartedAtRef.current = Date.now();
				playStartedTimeRef.current = state.currentTime;
				setTimeout(() => {
					seekingRef.current = false;
					// Re-sync manual tracking after seek settles
					startTracking();
				}, 1000);
			}
		});
		return unsub;
	}, [startTracking]);

	return (
		<div
			id="yt-player"
			className="fixed -left-2499.75 -top-2499.75 w-px h-px"
		/>
	);
}
