export default function HelpPage() {
	return (
		<>
			<h1>Help</h1>

			<h2>The mood sliders</h2>

			<p>Three sliders describe a mix's character:</p>

			<ul>
				<li>
					<strong>Mood</strong>, dark to bright
				</li>
				<li>
					<strong>Energy</strong>, chill to dynamic
				</li>
				<li>
					<strong>Instrumentation</strong>, organic to electronic
				</li>
			</ul>

			<p>
				You don't have to set all three. Leave them all untouched and you'll get
				a <strong>random mix</strong> of everything in the catalog, a good way
				to browse. Move one or two and the app{" "}
				<strong>narrows things down</strong> to mixes that broadly match. Move
				all three and it finds the mixes whose feel is{" "}
				<strong>closest to the exact combination</strong> you've picked.
			</p>

			<h2>Genres and the instrumental toggle</h2>

			<p>
				Genres are additive filters: pick any combination and the app will only
				show mixes tagged with at least one of them. The{" "}
				<strong>instrumental</strong> toggle hides mixes that contain vocals,
				useful when you want music you can work to.
			</p>

			<h2>Quick tags</h2>

			<p>
				The row of chips just under the top bar is a set of{" "}
				<strong>one-click starting points</strong>. Each tag applies a
				ready-made combination of sliders and genres, handy when you don't want
				to think about settings and just want a vibe to land on right away. You
				can still adjust anything afterwards.
			</p>

			<h2>AI search</h2>

			<p>
				Describe the vibe you're after in a sentence, the AI search bar
				translates it into sliders and genre filters. Good prompts are evocative
				rather than literal: "sunny morning café" works better than "ambient
				music".
			</p>

			<h2>The player</h2>

			<p>
				Click any card to start a mix. The player keeps playing while you
				browse, scroll, or navigate to other pages. Press <strong>space</strong>{" "}
				to play/pause.
			</p>

			<h2>Something not working?</h2>

			<p>
				If a mix won't play, YouTube may have removed or restricted it. You can
				report it from the player bar and it'll be removed from the catalog. For
				anything else, use the <a href="/info/contact">contact form</a>.
			</p>
		</>
	);
}
