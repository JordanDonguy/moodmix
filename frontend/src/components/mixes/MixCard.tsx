import type { Mix } from "../../types/mix";
import { formatDuration } from "../../utils/formatDuration";

export function MixCard({ mix }: { mix: Mix }) {
	const thumbnail =
		mix.thumbnail_url ??
		`https://i.ytimg.com/vi/${mix.youtube_id}/hqdefault.jpg`;

	return (
		<a
			className="group cursor-pointer flex flex-col h-full"
			href={`https://www.youtube.com/watch?v=${mix.youtube_id}`}
			target="_blank"
			rel="noopener noreferrer"
		>
			<div className="relative aspect-video rounded-xl overflow-hidden bg-bg-secondary">
				<img
					src={thumbnail}
					alt={mix.title}
					className="w-full h-full object-cover group-hover:scale-115 group-hover:translate-y-2 duration-200"
				/>
				<span className="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-xs px-1.5 py-0.5 rounded">
					{formatDuration(mix.duration_seconds)}
				</span>
			</div>

			<div className="mt-2 px-0.5 flex flex-col flex-1">
				<h3 className="text-sm text-text-primary font-medium leading-snug line-clamp-2">
					{mix.title}
				</h3>
				<div className="flex justify-between items-center mt-auto pt-1">
					<p className="text-xs text-text-secondary">
						{mix.channel_name}
					</p>
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
		</a>
	);
}
