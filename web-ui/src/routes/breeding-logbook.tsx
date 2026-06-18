import { createFileRoute } from "@tanstack/react-router";
import { BreedingLogbookPage } from "@/features/breeding-logbook/BreedingLogbookPage";

export const Route = createFileRoute("/breeding-logbook")({
  component: BreedingLogbookPage,
});
