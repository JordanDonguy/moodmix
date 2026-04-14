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
	const intervalRef = useRef<number>(0);
	const overlayRef = useRef<HTMLDivElement | null>(null);

	const currentMix = usePlayerStore((s) => s.currentMix);
	const isPlaying = usePlayerStore((s) => s.isPlaying);
	const playerContainer = usePlayerStore((s) => s.playerContainer);

	const startTracking = useCallback(() => {
		clearInterval(intervalRef.current);
		intervalRef.current = window.setInterval(() => {
			const player = playerRef.current;
			if (!player) return;
			const time = player.getCurrentTime();
			const dur = player.getDuration() || usePlayerStore.getState().duration;
			usePlayerStore.getState().setProgress(time, dur);
		}, 500);
	}, []);

	const stopTracking = useCallback(() => {
		clearInterval(intervalRef.current);
	}, []);

	// Load API script on mount
	useEffect(() => {
		loadApi();
	}, []);

	// Create stable overlay + YouTube player (lives on document.body, never moves)
	useEffect(() => {
		const overlay = document.createElement("div");
		overlay.style.position = "fixed";
		overlay.style.zIndex = "10";
		overlay.style.overflow = "hidden";
		overlay.style.borderRadius = "0.75rem";
		overlay.style.display = "none";
		document.body.appendChild(overlay);
		overlayRef.current = overlay;

		let cancelled = false;

		apiReady.then(() => {
			if (cancelled) return;

			const state = usePlayerStore.getState();

			const innerDiv = document.createElement("div");
			innerDiv.style.width = "100%";
			innerDiv.style.height = "100%";
			overlay.appendChild(innerDiv);

			new window.YT.Player(innerDiv, {
				width: "100%",
				height: "100%",
				playerVars: {
					autoplay: 1,
					controls: 1,
					disablekb: 1,
					modestbranding: 1,
					rel: 0,
					playsinline: 1,
				},
				events: {
					onReady: (event) => {
						if (cancelled) return;
						playerRef.current = event.target;
						readyRef.current = true;

						event.target.setVolume(state.volume);
						if (state.muted) event.target.mute();

						const mix = usePlayerStore.getState().currentMix;
						if (mix) {
							loadingRef.current = true;
							event.target.loadVideoById(mix.youtube_id, state.currentTime);
						}
					},
					onStateChange: (event) => {
						if (cancelled) return;
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
						if (cancelled) return;
						const { currentMix: mix, next } = usePlayerStore.getState();
						if (mix) reportUnavailable(mix.id).catch(() => {});
						next();
					},
				},
			});
		});

		return () => {
			cancelled = true;
			stopTracking();
			if (playerRef.current) {
				playerRef.current.destroy();
				playerRef.current = null;
				readyRef.current = false;
			}
			document.body.removeChild(overlay);
			overlayRef.current = null;
		};
	}, [startTracking, stopTracking]);

	// Position overlay over the active card's thumbnail area (rAF loop
	// so the overlay tracks grid reflows, not just scroll/resize)
	useEffect(() => {
		const overlay = overlayRef.current;
		if (!overlay) return;

		if (!playerContainer) {
			overlay.style.display = "none";
			return;
		}

		let rafId: number;
		const update = () => {
			const rect = playerContainer.getBoundingClientRect();
			if (rect.bottom < 0 || rect.top > window.innerHeight) {
				overlay.style.display = "none";
			} else {
				overlay.style.display = "block";
				overlay.style.top = `${rect.top}px`;
				overlay.style.left = `${rect.left}px`;
				overlay.style.width = `${rect.width}px`;
				overlay.style.height = `${rect.height}px`;
			}
			rafId = requestAnimationFrame(update);
		};
		rafId = requestAnimationFrame(update);

		return () => cancelAnimationFrame(rafId);
	}, [playerContainer]);

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

	// Resume playback when tab becomes visible (handles background-tab auto-advance)
	useEffect(() => {
		const handleVisibilityChange = () => {
			if (document.hidden) return;
			const { isPlaying: shouldPlay, next } = usePlayerStore.getState();
			const player = playerRef.current;
			if (!player || !readyRef.current) return;
			const ytState = player.getPlayerState();
			if (ytState === window.YT.PlayerState.ENDED) {
				next();
			} else if (
				shouldPlay &&
				ytState !== window.YT.PlayerState.PLAYING &&
				ytState !== window.YT.PlayerState.BUFFERING
			) {
				player.playVideo();
			}
		};
		document.addEventListener("visibilitychange", handleVisibilityChange);
		return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
	}, []);

	// OS media controls
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

	// Media metadata
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

	useEffect(() => {
		if (!("mediaSession" in navigator)) return;
		navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
	}, [isPlaying]);

	// Volume sync
	useEffect(() => {
		const unsub = usePlayerStore.subscribe((state, prev) => {
			const player = playerRef.current;
			if (!player) return;
			if (state.volume !== prev.volume) player.setVolume(state.volume);
			if (state.muted !== prev.muted) {
				if (state.muted) player.mute();
				else player.unMute();
			}
		});
		return unsub;
	}, []);

	// Seek
	useEffect(() => {
		const unsub = usePlayerStore.subscribe((state, prev) => {
			if (state.pendingSeek !== null && state.pendingSeek !== prev.pendingSeek) {
				playerRef.current?.seekTo(state.pendingSeek, true);
				usePlayerStore.setState({ pendingSeek: null });
			}
		});
		return unsub;
	}, []);

	// No visible DOM — player lives in the fixed overlay
	return null;
}
