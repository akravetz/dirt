import type { ReactNode } from "react";

interface PlantStickerProps {
  color: string | null;
  size?: "sm" | "md";
}

export function PlantSticker({ color, size = "md" }: PlantStickerProps): ReactNode {
  if (color === null) return null;
  const sizeClass = size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3";
  return (
    <span
      title={`${color} sticker`}
      className={`${sizeClass} shrink-0 border border-rule-strong ${stickerClass(
        color,
      )}`}
    />
  );
}

function stickerClass(color: string): string {
  switch (color) {
    case "yellow":
      return "bg-sticker-yellow";
    case "orange":
      return "bg-sticker-orange";
    case "pink":
      return "bg-sticker-pink";
    case "blue":
      return "bg-sticker-blue";
    default:
      return "bg-paper-3";
  }
}
