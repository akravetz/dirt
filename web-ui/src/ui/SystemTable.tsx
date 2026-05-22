// Dashboard system table.
//
// Renders one row per device from /api/system/devices. Each row's
// status badge carries role="status" + aria-label + visible text so
// screen readers (and the e2e spec) can read the status without
// relying on colour.
//
// The `ui` layer is forbidden from importing `@/api-client`
// (eslint-plugin-boundaries keeps presentational components
// independent of the OpenAPI surface). The props type is therefore a
// narrowed duck-typed mirror of the fields we actually read from
// contracts/webapp-v1.yaml #/components/schemas/DeviceStatus; the
// route-level consumer passes the generated `DevicesResponse["devices"]`
// straight in, and its typecheck catches drift.
import type { ReactNode } from "react";

type DeviceStatusKind = "ok" | "listening" | "warn" | "offline";

type WifiTelemetry = {
  rssi_dbm: number | null;
  reconnect_count: number | null;
  driver_reset_count: number | null;
  disconnect_reason: number | null;
};

type SystemTableRow = {
  name: string;
  status: DeviceStatusKind;
  wifi: WifiTelemetry | null;
};

type SystemTableProps = {
  /** Devices in the order the backend returned them. */
  devices: readonly SystemTableRow[];
};

// Badge colour keyed on status. Advisory only — the aria-label +
// visible text are the load-bearing accessible signals.
const BADGE_CLASS: Record<DeviceStatusKind, string> = {
  ok: "text-status-ok border-status-ok",
  listening: "text-ink border-rule-strong",
  warn: "text-status-warn border-status-warn",
  offline: "text-status-err border-status-err",
};

function formatNullable(value: number | null | undefined): string {
  return value == null ? "--" : String(value);
}

export function SystemTable({ devices }: SystemTableProps): ReactNode {
  return (
    <section aria-label="System devices" className="flex flex-col bg-paper-2 p-4">
      <h2 className="mb-2 font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
        System
      </h2>
      <table className="w-full border-collapse font-sans text-fs-12">
        <thead>
          <tr>
            <th
              scope="col"
              className="border-b border-rule-strong px-3.5 py-1.5 text-left font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              Device
            </th>
            <th
              scope="col"
              className="border-b border-rule-strong px-3.5 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              Status
            </th>
            <th
              scope="col"
              className="border-b border-rule-strong px-2 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              RSSI
            </th>
            <th
              scope="col"
              className="border-b border-rule-strong px-2 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              Reconn
            </th>
            <th
              scope="col"
              className="border-b border-rule-strong px-2 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              Reset
            </th>
            <th
              scope="col"
              className="border-b border-rule-strong px-2 py-1.5 text-right font-sans text-fs-10 font-semibold uppercase tracking-caps text-ink-2"
            >
              Reason
            </th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => (
            <tr key={device.name} className="border-b border-rule last:border-b-0">
              <td className="px-3.5 py-2.5 text-ink">{device.name}</td>
              <td className="px-3.5 py-2.5 text-right">
                <span
                  role="status"
                  aria-label={`${device.name} status`}
                  className={`inline-block border px-1.75 py-0.5 font-mono text-fs-10 uppercase tracking-caps ${BADGE_CLASS[device.status]}`}
                >
                  {device.status}
                </span>
              </td>
              <td className="px-2 py-2.5 text-right font-mono text-fs-11 text-ink-2">
                {formatNullable(device.wifi?.rssi_dbm)}
              </td>
              <td className="px-2 py-2.5 text-right font-mono text-fs-11 text-ink-2">
                {formatNullable(device.wifi?.reconnect_count)}
              </td>
              <td className="px-2 py-2.5 text-right font-mono text-fs-11 text-ink-2">
                {formatNullable(device.wifi?.driver_reset_count)}
              </td>
              <td className="px-2 py-2.5 text-right font-mono text-fs-11 text-ink-2">
                {formatNullable(device.wifi?.disconnect_reason)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
