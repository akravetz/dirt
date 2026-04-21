/**
 * Typed API client for the Dirt webapp v1 contract.
 *
 * Wraps `openapi-fetch` with project-wide defaults:
 *  - `credentials: "include"` so the browser attaches the `dirt_session`
 *    cookie to every request (the cookie is httponly; no JS reads it).
 *  - 401 → redirect to `/login` via the injected `onUnauthorized` hook so
 *    components can stay unaware of the cookie lifecycle.
 *
 * The schema types under `./generated/` are produced by
 * `scripts/gen-contract` from `contracts/webapp-v1.yaml`. App code MUST
 * NOT import `./generated/schema` directly — go through this module so
 * 401 handling and base-url defaults stay uniform.
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./generated/schema";

export type DirtApiClient = ReturnType<typeof createClient<paths>>;

export interface DirtApiClientOptions {
  /** Base URL for the API. Defaults to same-origin. */
  baseUrl?: string;
  /** Called on any 401 response. Default behaviour: window.location to /login. */
  onUnauthorized?: () => void;
}

const defaultOnUnauthorized = (): void => {
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
};

export const createDirtApiClient = (
  options: DirtApiClientOptions = {},
): DirtApiClient => {
  const { baseUrl = "/", onUnauthorized = defaultOnUnauthorized } = options;

  const client = createClient<paths>({
    baseUrl,
    credentials: "include",
  });

  const unauthorizedMiddleware: Middleware = {
    onResponse: ({ response }) => {
      if (response.status === 401) {
        onUnauthorized();
      }
      return response;
    },
  };
  client.use(unauthorizedMiddleware);

  return client;
};
