import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import InfoNavbar from "../../components/layout/InfoNavbar";

const SECTIONS = [
	{ to: "about", label: "About" },
	{ to: "help", label: "Help" },
	{ to: "privacy", label: "Privacy" },
	{ to: "terms", label: "Terms" },
	{ to: "contact", label: "Contact" },
] as const;

export default function InfoLayout() {
	return (
		<>
			<InfoNavbar />

			<div className="max-w-6xl mx-auto px-4 py-8 pb-32">
				{/* Mobile tab strip */}
				<nav className="lg:hidden mb-6 -mx-4 px-4 overflow-x-auto">
					<ul className="flex gap-1 min-w-max border-b border-border">
						{SECTIONS.map((s) => (
							<li key={s.to}>
								<NavLink
									to={s.to}
									className={({ isActive }) =>
										`inline-block px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
											isActive
												? "text-text-primary border-accent"
												: "text-text-secondary border-transparent hover:text-text-primary"
										}`
									}
								>
									{s.label}
								</NavLink>
							</li>
						))}
					</ul>
				</nav>

				<div className="lg:flex lg:gap-10">
					{/* Desktop sidebar */}
					<aside className="hidden lg:block w-48 shrink-0">
						<ul className="sticky top-24 space-y-1">
							{SECTIONS.map((s) => (
								<li key={s.to}>
									<NavLink
										to={s.to}
										className={({ isActive }) =>
											`block px-3 py-2 rounded-md text-sm transition-colors ${
												isActive
													? "bg-bg-elevated text-text-primary"
													: "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
											}`
										}
									>
										{s.label}
									</NavLink>
								</li>
							))}
						</ul>
					</aside>

					<article className="flex-1 min-w-0 max-w-3xl text-text-secondary leading-relaxed space-y-4 [&_h1]:text-3xl [&_h1]:font-semibold [&_h1]:text-text-primary [&_h1]:mb-6 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-text-primary [&_h2]:mt-8 [&_h2]:mb-3 [&_a]:text-accent [&_a]:hover:underline [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-2 [&_strong]:text-text-primary">
						<Suspense
							fallback={<div className="text-text-muted">Loading…</div>}
						>
							<Outlet />
						</Suspense>
					</article>
				</div>
			</div>
		</>
	);
}
