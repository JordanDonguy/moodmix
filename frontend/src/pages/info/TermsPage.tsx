export default function TermsPage() {
	const lastUpdated = "April 2026";

	return (
		<>
			<h1>Terms of Service</h1>

			<p className="text-sm text-text-muted">Last updated: {lastUpdated}</p>

			<p>
				By using MoodMix, you agree to these terms. If you don't agree, please
				don't use the service.
			</p>

			<h2>What MoodMix is</h2>

			<p>
				MoodMix is a free, ad-free discovery tool that indexes publicly
				available YouTube mixes and plays them through YouTube's embedded
				player. MoodMix does not host, upload, or distribute any audio or video
				content, all playback happens via YouTube.
			</p>

			<h2>Acceptable use</h2>

			<p>You agree not to:</p>

			<ul>
				<li>
					Use the service for any unlawful purpose or to abuse other users
				</li>
				<li>Attempt to scrape, reverse-engineer, or overload the API</li>
				<li>Circumvent rate limits or attempt to bypass security measures</li>
				<li>Submit misleading or spam content through the contact form</li>
			</ul>

			<h2>YouTube terms</h2>

			<p>
				Because playback is delivered via YouTube's embedded player, your use of
				the player is also subject to{" "}
				<a
					href="https://www.youtube.com/t/terms"
					target="_blank"
					rel="noopener noreferrer"
				>
					YouTube's Terms of Service
				</a>
				.
			</p>

			<h2>No warranty</h2>

			<p>
				MoodMix is provided "as is" without warranties of any kind. Mixes may
				become unavailable if their underlying YouTube video is removed, made
				private, or geo-restricted. We don't guarantee uninterrupted
				availability.
			</p>

			<h2>Limitation of liability</h2>

			<p>
				To the maximum extent permitted by law, MoodMix and its operator are not
				liable for any indirect, incidental, or consequential damages arising
				from your use of the service.
			</p>

			<h2>Content and copyright</h2>

			<p>
				All mixes are the property of their respective YouTube creators and
				rights-holders. If you believe a mix in our catalog infringes your
				rights, please contact us via the{" "}
				<a href="/info/contact">contact form</a> and we'll remove it.
			</p>

			<h2>Changes</h2>

			<p>
				These terms may be updated over time. Continued use of the service after
				changes constitutes acceptance.
			</p>

			<h2>Governing law</h2>

			<p>
				These terms are governed by the laws of the European Union member state
				in which the operator is established.
			</p>
		</>
	);
}
