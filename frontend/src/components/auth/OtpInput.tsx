import {
	type ClipboardEvent,
	type KeyboardEvent,
	useEffect,
	useRef,
} from "react";

interface OtpInputProps {
	value: string;
	onChange: (value: string) => void;
	onComplete?: (value: string) => void;
	autoFocus?: boolean;
	disabled?: boolean;
	length?: number;
}

/**
 * Six-digit one-time-code input. Treats the underlying `value` (a string) as
 * the source of truth and renders one `<input>` per digit so the visual
 * "boxes" match. Supports:
 *   - typing a digit auto-advances focus to the next slot
 *   - backspace on an empty slot returns to the previous slot
 *   - pasting "123456" fills all slots in one shot and fires onComplete
 *   - non-digit characters are silently dropped
 *   - autoFocus places the cursor on the first empty slot on mount
 */
export default function OtpInput({
	value,
	onChange,
	onComplete,
	autoFocus = false,
	disabled = false,
	length = 6,
}: OtpInputProps) {
	const refs = useRef<(HTMLInputElement | null)[]>([]);

	useEffect(() => {
		if (!autoFocus) return;
		const firstEmpty = Math.min(value.length, length - 1);
		refs.current[firstEmpty]?.focus();
	}, [autoFocus, length, value.length]);

	function setDigit(index: number, digit: string) {
		if (digit && !/^\d$/.test(digit)) return;
		const next = (value + " ".repeat(length)).slice(0, length).split("");
		next[index] = digit;
		// Trim trailing spaces so the model never holds whitespace.
		const joined = next.join("").replace(/\s+$/, "");
		onChange(joined);
		if (digit && index < length - 1) refs.current[index + 1]?.focus();
		if (joined.length === length && onComplete) onComplete(joined);
	}

	function handleKeyDown(e: KeyboardEvent<HTMLInputElement>, index: number) {
		if (e.key === "Backspace") {
			if (value[index]) {
				setDigit(index, "");
			} else if (index > 0) {
				refs.current[index - 1]?.focus();
				setDigit(index - 1, "");
				e.preventDefault();
			}
			return;
		}
		if (e.key === "ArrowLeft" && index > 0) {
			refs.current[index - 1]?.focus();
			e.preventDefault();
		}
		if (e.key === "ArrowRight" && index < length - 1) {
			refs.current[index + 1]?.focus();
			e.preventDefault();
		}
	}

	function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
		const text = e.clipboardData
			.getData("text")
			.replace(/\D/g, "")
			.slice(0, length);
		if (!text) return;
		e.preventDefault();
		onChange(text);
		const last = Math.min(text.length, length) - 1;
		refs.current[last]?.focus();
		if (text.length === length && onComplete) onComplete(text);
	}

	return (
		<div className="flex gap-2 justify-center">
			{Array.from({ length }).map((_, i) => (
				<input
					// biome-ignore lint/suspicious/noArrayIndexKey: positions are stable
					key={i}
					ref={(el) => {
						refs.current[i] = el;
					}}
					type="text"
					inputMode="numeric"
					autoComplete="one-time-code"
					maxLength={1}
					disabled={disabled}
					value={value[i] ?? ""}
					onChange={(e) => setDigit(i, e.target.value.slice(-1))}
					onKeyDown={(e) => handleKeyDown(e, i)}
					onPaste={handlePaste}
					aria-label={`Digit ${i + 1} of ${length}`}
					className="w-10 h-12 text-center text-lg font-semibold rounded-md bg-bg-secondary border border-border text-text-primary focus:outline-none focus:border-accent disabled:opacity-50"
				/>
			))}
		</div>
	);
}
