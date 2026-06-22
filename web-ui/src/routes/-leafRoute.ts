import { useRouterState } from "@tanstack/react-router";

export function useIsLeafRoute(routeId: string): boolean {
  return useRouterState({
    select: (state) => state.matches.at(-1)?.routeId === routeId,
  });
}
