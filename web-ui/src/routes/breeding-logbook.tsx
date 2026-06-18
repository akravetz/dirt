import { createFileRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import {
  BreedingLogbookPage,
  StatusScreen,
} from "@/features/breeding-logbook/BreedingLogbookPage";

export const Route = createFileRoute("/breeding-logbook")({
  component: BreedingLogbookRoute,
  errorComponent: () => (
    <StatusScreen message="Failed to load breeding logbook." tone="danger" />
  ),
});

function BreedingLogbookRoute() {
  return (
    <Suspense fallback={<StatusScreen message="Loading breeding logbook..." />}>
      <BreedingLogbookPage />
    </Suspense>
  );
}
