import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Utility function to merge Tailwind CSS classes with clsx and tailwind-merge.
 * This handles conflicting Tailwind classes properly.
 */
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
