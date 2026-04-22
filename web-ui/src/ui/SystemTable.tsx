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
// narrowed duck-typed mirror of the two fields we actually read from
// contracts/webapp-v1.yaml #/components/schemas/DeviceStatus; the
// route-level consumer passes the generated `DevicesResponse["devices"]`
// straight in, and its typecheck catches drift.
import type { ReactNode } from "react";

type DeviceStatusKind = "ok" | "listening" | "warn" | "offline";

interface SystemTableRow {
  name: string;
  status: DeviceStatusKind;
}

interface SystemTableProps {
  /** Devices in the order the backend returned them. */
  devices: readonly SystemTableRow[];
}

// Badge colour keyed on status. Advisory only — the aria-label +
// visible text are the load-bearing accessible signals.
const BADGE_CLASS: Record<DeviceStatusKind, string> = {
  ok: "text-ink border-rule",
  listening: "text-ink border-rule",
  warn: "text-accent-magenta border-accent-magenta",
  offline: "text-ink-3 border-ink-3",
};

export function SystemTable({ devices }: SystemTableProps): ReactNode {
  return (
    <section
      aria-label="System devices"
      className="flex flex-col gap-2 border border-rule bg-paper p-4"
    >
      <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">System</h2>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th
              scope="col"
              className="border-b border-rule py-1 text-left font-mono text-xs uppercase tracking-caps text-ink-3"
            >
              Device
            </th>
            <th
              scope="col"
              className="border-b border-rule py-1 text-right font-mono text-xs uppercase tracking-caps text-ink-3"
            >
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => (
            <tr key={device.name} className="border-b border-rule last:border-b-0">
              <td className="py-2 font-serif text-base text-ink">{device.name}</td>
              <td className="py-2 text-right">
                <span
                  role="status"
                  aria-label={`${device.name} status`}
                  className={`inline-block border px-2 py-0.5 font-mono text-xs uppercase tracking-caps ${BADGE_CLASS[device.status]}`}
                >
                  {device.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
