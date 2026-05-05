import { dirtApiBaseUrl } from "./client";

export interface CloudSite {
  site_id: string;
  name: string;
  timezone: string;
  is_active: boolean;
  gateway_last_seen_at: string | null;
  last_catalog_sync_at: string | null;
}

export interface CloudTent {
  site_id: string;
  tent_id: string;
  name: string;
  is_active: boolean;
  synced_at: string;
}

export interface CloudTentState {
  site_id: string;
  tent_id: string;
  name: string;
  is_active: boolean;
  gateway_last_seen_at: string | null;
  last_catalog_sync_at: string | null;
}

export interface CloudMetric {
  metric: string;
  value: number;
  unit: string | null;
  capability_id: string;
  device_id: string | null;
  source_updated_at: string;
  received_at: string;
  stale_after_s: number;
}

export interface CloudHistoryPoint {
  bucket: string;
  bucket_start_at: string;
  bucket_end_at: string;
  min: number | null;
  avg: number | null;
  max: number | null;
  sample_count: number;
  unit: string | null;
}

export interface CloudMetricHistory {
  metric: string;
  range: string;
  points: CloudHistoryPoint[];
}

export interface CloudDevice {
  device_id: string;
  name: string;
  kind: string;
  controller: string | null;
  is_active: boolean;
  last_seen_at: string | null;
}

export interface CloudAsset {
  asset_id: string;
  kind: string;
  content_type: string;
  byte_size: number;
  sha256: string | null;
  captured_at: string;
  uploaded_at: string;
  signed_url: string;
  signed_url_expires_at: string;
}

export interface CloudSyncStatus {
  site_id: string;
  gateway_last_seen_at: string | null;
  last_catalog_sync_at: string | null;
  command_backlog_depth: number;
  status: "live" | "stale" | "offline";
}

export async function cloudGet<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { credentials: "include" });
  if (response.status === 401) {
    window.location.assign("/login");
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  const body: unknown = await response.json();
  return body as T;
}

function apiUrl(path: string): string {
  const scopedPath = appendFixtureParam(path);
  if (dirtApiBaseUrl === "/") return scopedPath;
  return `${dirtApiBaseUrl}${scopedPath}`;
}

function appendFixtureParam(path: string): string {
  if (typeof window === "undefined") return path;
  const fixture = new URLSearchParams(window.location.search).get("cloud_fixture");
  if (fixture === null || fixture.length === 0) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}cloud_fixture=${encodeURIComponent(fixture)}`;
}
