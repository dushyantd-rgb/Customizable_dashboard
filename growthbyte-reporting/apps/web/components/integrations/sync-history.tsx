import type { SyncRunSummary } from "@growthbyte/shared-types";

import { EmptyState, ErrorState, LoadingState } from "../async-state";

interface SyncHistoryProps {
  readonly error?: unknown;
  readonly isLoading: boolean;
  readonly runs?: readonly SyncRunSummary[];
  readonly sourceLabel: string;
}

export function SyncHistory({ error, isLoading, runs, sourceLabel }: SyncHistoryProps) {
  if (isLoading) {
    return <LoadingState label={`Loading ${sourceLabel} sync history...`} />;
  }
  if (error) {
    return <ErrorState message={`Could not load ${sourceLabel} sync history.`} />;
  }
  if (!runs?.length) {
    return <EmptyState message={`No ${sourceLabel} syncs have run for this client.`} />;
  }

  return (
    <div className="overflow-x-auto border border-growthbyte-black">
      <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
        <thead className="bg-growthbyte-black text-growthbyte-white">
          <tr>
            <th className="px-4 py-3 font-semibold" scope="col">
              Status
            </th>
            <th className="px-4 py-3 font-semibold" scope="col">
              Started
            </th>
            <th className="px-4 py-3 font-semibold" scope="col">
              Read
            </th>
            <th className="px-4 py-3 font-semibold" scope="col">
              Upserted
            </th>
            <th className="px-4 py-3 font-semibold" scope="col">
              Warnings
            </th>
            <th className="px-4 py-3 font-semibold" scope="col">
              Result
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr className="border-t border-growthbyte-black/20" key={run.id}>
              <td className="px-4 py-3 font-semibold">{run.status}</td>
              <td className="px-4 py-3">{formatTimestamp(run.started_at ?? run.created_at)}</td>
              <td className="px-4 py-3 tabular-nums">{run.rows_read}</td>
              <td className="px-4 py-3 tabular-nums">{run.rows_written}</td>
              <td className="px-4 py-3 tabular-nums">{run.rows_rejected}</td>
              <td className="max-w-72 px-4 py-3">{run.error_summary ?? "Completed safely"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
