import { useMemo } from "react";
import { usePlayerStore } from "../../store/playerStore";
import type { Mix } from "../../types/mix";
import { formatDuration } from "../../utils/formatDuration";

function moodToColor(mix: Mix): string {
	const m = mix.mood ?? 0;
	const e = mix.energy ?? 0;
	const i = mix.instrumentation ?? 0;

	// Trilinear interpolation between 8 corner hues on the color wheel.
	// Each corner maps a mood/energy/instrumentation extreme to a hand-picked color.
	const corners = [
		220, // dark chill organic → deep blue
		280, // dark chill electronic → purple
		185, // dark dynamic organic → teal
		320, // dark dynamic electronic → pink
		70, // bright chill organic → yellow-green
		350, // bright chill electronic → red
		35, // bright dynamic organic → orange
		10, // bright dynamic electronic → red-orange
	];

	const hlerp = (h1: number, h2: number, t: number) => {
		const diff = ((h2 - h1 + 180) % 360) - 180;
		return (h1 + diff * t + 360) % 360;
	};

	const tm = (m + 1) / 2; // 0=dark, 1=bright
	const te = (e + 1) / 2; // 0=chill, 1=dynamic
	const ti = (i + 1) / 2; // 0=organic, 1=electronic

	const c00 = hlerp(corners[0], corners[1], ti);
	const c01 = hlerp(corners[2], corners[3], ti);
	const c10 = hlerp(corners[4], corners[5], ti);
	const c11 = hlerp(corners[6], corners[7], ti);
	const c0 = hlerp(c00, c01, te);
	const c1 = hlerp(c10, c11, te);
	const hue = hlerp(c0, c1, tm);

	const saturation = 75 + (e + 1) * 15; // 55-85%
	const lightness = 50;

	return `${hue} ${saturation}% ${lightness}%`;
}

export function MixCard({ mix, queue, priority }: { mix: Mix; queue: Mix[]; priority?: boolean }) {
	const currentMixId = usePlayerStore((s) => s.currentMix?.id);
	const isActive = currentMixId === mix.id;

	const hsl = useMemo(() => moodToColor(mix), [mix]);

	const thumbnail =
		mix.thumbnail_url ??
		`https://i.ytimg.com/vi/${mix.youtube_id}/hqdefault.jpg`;

	const handleClick = () => {
		usePlayerStore.getState().playMix(mix, queue);
	};

	return (
		<button
			type="button"
			onClick={handleClick}
			className="group cursor-pointer flex flex-col h-full text-left rounded-xl outline-transparent duration-200 card-hover"
			style={{
				"--card-color": `hsl(${hsl})`,
				"--card-hover-bg": `hsl(${hsl} / var(--hover-card-opacity))`,
				...(isActive
					? {
							outline: `8px solid hsl(${hsl} / var(--active-card-opacity))`,
							backgroundColor: `hsl(${hsl} / var(--active-card-opacity))`,
						}
					: {}),
			} as React.CSSProperties}
		>
			<div className="relative aspect-video rounded-xl overflow-hidden bg-bg-secondary w-full">
				<img
					src={thumbnail}
					alt={mix.title}
					loading={priority ? "eager" : "lazy"}
					decoding="async"
					fetchPriority={priority ? "high" : "auto"}
					className="w-full h-full object-cover group-hover:scale-105 duration-200"
				/>
				<span className="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-xs px-1.5 py-0.5 rounded">
					{formatDuration(mix.duration_seconds)}
				</span>
			</div>

			<div className="mt-2 px-0.5 flex flex-col flex-1">
				<h3 className="text-sm text-text-primary font-medium leading-snug line-clamp-2">
					{mix.title}
				</h3>
				<div className="flex justify-between items-center mt-auto pt-1 pb-2">
					<p className="text-xs text-text-secondary">{mix.channel_name}</p>
					{mix.genres.length > 0 && (
						<div className="flex flex-wrap gap-1">
							{mix.genres.map((g) => (
								<span
									key={g.id}
									className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-elevated text-text-secondary"
								>
									{g.name}
								</span>
							))}
						</div>
					)}
				</div>
			</div>
		</button>
	);
}
