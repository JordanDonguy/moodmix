import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "ghost" | "primary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: ButtonVariant;
}

const BASE = "cursor-pointer disabled:opacity-30";

const VARIANTS: Record<ButtonVariant, string> = {
	ghost: "text-text-secondary hover:text-text-primary transition-colors",
	primary:
		"w-8 h-8 flex items-center justify-center rounded-full bg-text-primary text-bg-primary hover:scale-105 transition-transform",
};

/**
 * Base button primitive.
 *
 * - `ghost` (default): icon-only button that picks up a hover color.
 * - `primary`: filled circular call-to-action (e.g. play/pause).
 *
 * Forwards all native button props. Always provide an `aria-label` for
 * icon-only buttons.
 */
export default function Button({
	variant = "ghost",
	type = "button",
	className = "",
	...props
}: ButtonProps) {
	return (
		<button
			type={type}
			className={`${BASE} ${VARIANTS[variant]} ${className}`}
			{...props}
		/>
	);
}
