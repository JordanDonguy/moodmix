interface Props {
	checked: boolean;
}

export function ToggleSwitch({ checked }: Props) {
	return (
		<span
			aria-hidden="true"
			className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors ${
				checked ? "bg-accent border-transparent" : "bg-bg-elevated border-border"
			}`}
		>
			<span
				className={`absolute top-px left-px h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
					checked ? "translate-x-4" : "translate-x-0"
				}`}
			/>
		</span>
	);
}
