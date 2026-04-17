export default function PrivacyPage() {
	const lastUpdated = "April 2026";

	return (
		<>
			<h1>Privacy Policy</h1>

			<p className="text-sm text-text-muted">Last updated: {lastUpdated}</p>

			<p>
				MoodMix is operated from the European Union and designed to minimise the
				personal data it collects. This policy explains what data is processed,
				why, and the rights you have under the EU General Data Protection
				Regulation (GDPR).
			</p>

			<h2>Data controller</h2>

			<p>
				The data controller for MoodMix is the site operator. For any
				privacy-related request, please use the{" "}
				<a href="/info/contact">contact form</a>.
			</p>

			<h2>No user accounts (yet)</h2>

			<p>
				MoodMix currently does not offer user accounts. We do not ask for, and
				cannot store, a name, email, or password unless you voluntarily submit
				one through the contact form.
			</p>

			<h2>YouTube video playback</h2>

			<p>
				Mix playback is provided by YouTube, embedded via{" "}
				<strong>youtube-nocookie.com</strong> (YouTube's privacy-enhanced mode).
				This means:
			</p>

			<ul>
				<li>
					<strong>Before you press play:</strong> no YouTube cookies are set.
					The iframe loads in a tracking-free mode.
				</li>
				<li>
					<strong>When you press play:</strong> YouTube (Google LLC) will set
					cookies and process data as described in their{" "}
					<a
						href="https://policies.google.com/privacy"
						target="_blank"
						rel="noopener noreferrer"
					>
						privacy policy
					</a>
					. This is necessary to deliver the video and counts as a
					user-initiated action.
				</li>
			</ul>

			<h2>Analytics</h2>

			<p>
				We use <strong>Cloudflare Web Analytics</strong>, which is cookieless
				and does not track individuals across sites or sessions. It collects
				aggregate metrics such as page views, referrer domains, and browser /
				device class, all stripped of personally identifiable information. No
				consent banner is required for this type of analytics under GDPR.
			</p>

			<h2>Server logs</h2>

			<p>
				Our server automatically records basic request metadata (IP address,
				timestamp, HTTP method, and URL requested) for security and abuse
				prevention. These logs are not persisted long-term: they live only for
				as long as the server container runs between deployments, and are
				discarded when it is recreated.
			</p>

			<h2>Contact form</h2>

			<p>
				When you submit the contact form, we process the name, email address,
				and message you provide in order to reply. Submissions are delivered to
				the operator via email and retained for up to 12 months, after which
				they are deleted unless an ongoing conversation requires otherwise.
			</p>

			<h2>Legal basis</h2>

			<ul>
				<li>
					<strong>YouTube playback:</strong> necessary for the performance of
					the service you requested (Art. 6(1)(b) GDPR)
				</li>
				<li>
					<strong>Server logs:</strong> legitimate interest in security and
					reliability (Art. 6(1)(f) GDPR)
				</li>
				<li>
					<strong>Contact form:</strong> legitimate interest in responding to
					your request (Art. 6(1)(f) GDPR)
				</li>
				<li>
					<strong>Cloudflare Web Analytics:</strong> legitimate interest in
					understanding aggregate usage (Art. 6(1)(f) GDPR); no personal data is
					processed
				</li>
			</ul>

			<h2>Your rights</h2>

			<p>Under GDPR you have the right to:</p>

			<ul>
				<li>Access the personal data we hold about you</li>
				<li>Request correction of inaccurate data</li>
				<li>Request erasure ("right to be forgotten")</li>
				<li>Object to processing based on legitimate interest</li>
				<li>Lodge a complaint with your national data protection authority</li>
			</ul>

			<p>
				To exercise any of these rights, use the{" "}
				<a href="/info/contact">contact form</a> and we'll respond within 30
				days.
			</p>

			<h2>Third parties</h2>

			<ul>
				<li>
					<strong>Google / YouTube</strong>, video playback (when you press
					play)
				</li>
				<li>
					<strong>Cloudflare</strong>, hosting and cookieless analytics
				</li>
				<li>
					<strong>Resend</strong>, delivery of contact-form emails to the
					operator
				</li>
			</ul>

			<h2>Changes to this policy</h2>

			<p>
				We may update this policy as the service evolves (for example when user
				accounts are introduced). The "last updated" date at the top of this
				page reflects the most recent change.
			</p>
		</>
	);
}
