import { useEffect, useState } from "react";

interface ResendCodeButtonProps {
	onResend: () => void | Promise<void>;
	cooldownSeconds?: number;
	/** Start in cooldown immediately on mount — typical right after the
	 * initial request-code fires, so the user can't double-tap. */
	startCooldownOnMount?: boolean;
	disabled?: boolean;
}

export default function ResendCodeButton({
	onResend,
	cooldownSeconds = 30,
	startCooldownOnMount = true,
	disabled = false,
}: ResendCodeButtonProps) {
	const [remaining, setRemaining] = useState(
		startCooldownOnMount ? cooldownSeconds : 0,
	);

	useEffect(() => {
		if (remaining <= 0) return;
		const id = setInterval(() => {
			setRemaining((r) => Math.max(0, r - 1));
		}, 1000);
		return () => clearInterval(id);
	}, [remaining]);

	async function handleClick() {
		if (remaining > 0 || disabled) return;
		await onResend();
		setRemaining(cooldownSeconds);
	}

	const cooling = remaining > 0;

	return (
		<button
			type="button"
			onClick={handleClick}
			disabled={cooling || disabled}
			className="text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
		>
			{cooling ? `Resend code in ${remaining}s` : "Resend code"}
		</button>
	);
}
