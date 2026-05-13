export type { DirtApiClient, DirtApiClientOptions } from "./client";
export { createDirtApiClient, isHostedApiMode } from "./client";
export type {
  components as hostedComponents,
  operations as hostedOperations,
  paths as hostedPaths,
} from "./generated/hosted-schema";
export type { components, operations, paths } from "./generated/schema";
export { createHostedApiClient } from "./hosted";
