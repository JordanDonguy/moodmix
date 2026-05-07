import type { ReactNode } from "react";

interface Props {
	content: string;
	children: ReactNode;
}

export function Tooltip({ content, children }: Props) {
	return (
		<span className="relative group">
			{children}
			<span
				role="tooltip"
				className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-52 rounded border border-border bg-bg-elevated px-2 py-1.5 text-xs text-text-secondary leading-snug pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-100 z-50 text-center whitespace-normal"
			>
				{content}
			</span>
		</span>
	);
}
