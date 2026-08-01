"use client";

import type { SyncRunSummary } from "@growthbyte/shared-types";
import { FormEvent, useState } from "react";
import useSWR from "swr";

import { api, googleOAuthUrl, safeErrorMessage } from "../../lib/api-client";
import { SyncHistory } from "./sync-history";
import { currentMonthToDate } from "./sync-date-range";

interface ActionState {
  readonly kind: "error" | "success";
  readonly message: string;
}

export function LiveSyncPanel({ clientId }: Readonly<{ clientId: string }>) {
  const initialDates = currentMonthToDate();
  const [dateFrom, setDateFrom] = useState(initialDates.dateFrom);
  const [dateTo, setDateTo] = useState(initialDates.dateTo);
  const [busyAction, setBusyAction] = useState<"meta" | "google" | null>(null);
  const [actionState, setActionState] = useState<ActionState | null>(null);
  const metaHistory = useSWR<SyncRunSummary[]>(["meta-sync-runs", clientId], () =>
    api.listMetaSyncRuns(clientId),
  );
  const googleHistory = useSWR<SyncRunSummary[]>(["google-sync-runs", clientId], () =>
    api.listGoogleSyncRuns(clientId),
  );

  function resetToCurrentMonth() {
    const currentMonth = currentMonthToDate();
    setDateFrom(currentMonth.dateFrom);
    setDateTo(currentMonth.dateTo);
  }

  async function syncMeta(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dateFrom || !dateTo || dateTo < dateFrom) {
      setActionState({ kind: "error", message: "Choose a valid sync date range." });
      return;
    }
    setBusyAction("meta");
    setActionState(null);
    try {
      const result = await api.syncMeta(clientId, { date_from: dateFrom, date_to: dateTo });
      await metaHistory.mutate();
      setActionState({
        kind: "success",
        message: `Meta sync ${result.status}: ${result.rows_read} read, ${result.rows_written} upserted.`,
      });
    } catch (error) {
      setActionState({ kind: "error", message: safeErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function syncGoogle() {
    setBusyAction("google");
    setActionState(null);
    try {
      const result = await api.syncGoogle(clientId);
      await googleHistory.mutate();
      setActionState({
        kind: "success",
        message: `Google sync ${result.status}: ${result.rows_read} read, ${result.rows_written} upserted, ${result.rows_skipped} skipped.`,
      });
    } catch (error) {
      setActionState({ kind: "error", message: safeErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="space-y-6" aria-labelledby="live-sync-heading">
      <header>
        <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
          Live sources
        </p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight" id="live-sync-heading">
          Sync live data
        </h2>
        <p className="mt-2 max-w-3xl text-growthbyte-black/70">
          Meta Ads defaults to month-to-date. Change the existing date filter whenever you need a
          different reporting period. Google Sheets imports the latest rows from the configured
          read-only worksheet.
        </p>
      </header>

      {actionState ? (
        <p
          className={`border p-4 ${
            actionState.kind === "success"
              ? "border-growthbyte-teal bg-teal-50 text-growthbyte-black"
              : "border-red-700 bg-red-50 text-red-900"
          }`}
          role={actionState.kind === "error" ? "alert" : "status"}
        >
          {actionState.message}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <form className="space-y-5 border border-growthbyte-black p-6" onSubmit={syncMeta}>
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-growthbyte-black/60">
              Meta Ads
            </p>
            <h3 className="mt-1 text-xl font-semibold">Pull ad performance</h3>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 font-medium">
              <span>Start date</span>
              <input
                className="form-input"
                onChange={(event) => setDateFrom(event.target.value)}
                type="date"
                value={dateFrom}
              />
            </label>
            <label className="space-y-2 font-medium">
              <span>End date</span>
              <input
                className="form-input"
                onChange={(event) => setDateTo(event.target.value)}
                type="date"
                value={dateTo}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="primary-button" disabled={busyAction !== null} type="submit">
              {busyAction === "meta" ? "Syncing Meta..." : "Sync Meta Ads"}
            </button>
            <button
              className="secondary-button"
              disabled={busyAction !== null}
              onClick={resetToCurrentMonth}
              type="button"
            >
              This month
            </button>
          </div>
        </form>

        <div className="space-y-5 border border-growthbyte-black p-6">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-growthbyte-black/60">
              Google Sheets
            </p>
            <h3 className="mt-1 text-xl font-semibold">Pull live lead data</h3>
            <p className="mt-2 text-sm text-growthbyte-black/70">
              OAuth access is client-scoped and read-only. Connect Google once, then sync the
              worksheet configured in the Connections tab.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a className="secondary-button" href={googleOAuthUrl(clientId)}>
              Connect Google
            </a>
            <button
              className="primary-button"
              disabled={busyAction !== null}
              onClick={syncGoogle}
              type="button"
            >
              {busyAction === "google" ? "Syncing Google..." : "Sync Google Sheets"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 border-t border-growthbyte-black/20 pt-6 xl:grid-cols-2">
        <div className="space-y-3">
          <h3 className="text-xl font-semibold">Recent Meta syncs</h3>
          <SyncHistory
            error={metaHistory.error}
            isLoading={metaHistory.isLoading}
            runs={metaHistory.data}
            sourceLabel="Meta"
          />
        </div>
        <div className="space-y-3">
          <h3 className="text-xl font-semibold">Recent Google Sheet syncs</h3>
          <SyncHistory
            error={googleHistory.error}
            isLoading={googleHistory.isLoading}
            runs={googleHistory.data}
            sourceLabel="Google Sheet"
          />
        </div>
      </div>
    </section>
  );
}
