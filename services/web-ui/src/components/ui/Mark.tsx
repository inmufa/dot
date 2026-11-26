"use client";
import { BuddyMark } from "@/components/buddy/Buddy";

/** The Dot mark: the buddy in its logo pose (winking), in the chosen buddy colour. */
export function Mark({ size = 24, label }: { size?: number; small?: boolean; label?: string }) {
  return <BuddyMark size={size} label={label} />;
}
