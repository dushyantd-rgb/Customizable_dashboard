"use client";

import type { MetaAccountDiscoveryResponse, SyncRunSummary } from "@growthbyte/shared-types";
import { FormEvent, useState } from "react";
import useSWR from "swr";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";
import { SyncHistory } from "./sync-history";

interface MetaIntegrationPanelProps {
  readonly clientId: string;
}

interface ActionState {
  readonly kind: "error" | "success";
  readonly message: string;
}

const initialDates = getInitialDates();

export function MetaIntegrationPanel({ clientId }: MetaIntegrationPanelProps) {
  const accounts = useSWR<MetaAccountDiscoveryResponse>(["meta-accounts", clientId], () =>
    api.listMetaAccounts(clientId),
  );
  const history = useSWR<SyncRunSummary[]>(["meta-sync-runs", clientId], () =>
    api.listMetaSyncRuns(clientId),
  );
  const [accountId, setAccountId] = useState("");
  const [dateFrom, setDateFrom] = useState(initialDates.dateFrom);
  const [dateTo, setDateTo] = useState(initialDates.dateTo);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionState, setActionState] = useState<ActionState | null>(null);

  async function runAction(action: string, operation: () => Promise<ActionState>) {
    setBusyAction(action);
    setActionState(null);
    try {
      setActionState(await operation());
    } catch (error) {
      setActionState({ kind: "error", message: safeErrorMessage(error) });
    } finally {
      setBusyAction(null);
    }
  }

  async function configure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accountId) {
      setActionState({ kind: "error", message: "Select a Meta ad account first." });
      return;
    }
    await runAction("configure", async () => {
      const account = accounts.data?.accounts.find(
        (candidate) => candidate.external_account_id === accountId,
      );
      await api.configureMeta(clientId, {
        external_account_id: accountId,
        display_name: account?.name,
      });
      return { kind: "success", message: "Meta account assigned to this client." };
    });
  }

  async function testConnection() {
    await runAction("test", async () => {
      const result = await api.testMeta(clientId);
      return result.connected
        ? { kind: "success", message: "Meta connection is ready." }
        : { kind: "error", message: "No Meta account is configured for this client." };
    });
  }

  async function sync(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dateFrom || !dateTo || dateTo < dateFrom) {
      setActionState({ kind: "error", message: "Choose a valid Meta sync date range." });
      return;
    }
    await runAction("sync", async () => {
      const result = await api.syncMeta(clientId, { date_from: dateFrom, date_to: dateTo });
      await history.mutate();
      return {
        kind: "success",
        message: `Meta sync ${result.status}: ${result.rows_read} read, ${result.rows_written} upserted.`,
      };
    });
  }

  return (
    <section
      className="space-y-6 border border-growthbyte-black p-6"
      aria-labelledby="meta-heading"
    >
      <header>
        <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">Meta Ads</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight" id="meta-heading">
          Ad account and manual sync
        </h2>
        <p className="mt-2 max-w-3xl text-growthbyte-black/70">
          Assign one accessible ad account, verify it, then import a small explicit date range.
        </p>
      </header>

      {accounts.isLoading ? <LoadingState label="Loading accessible Meta accounts..." /> : null}
      {accounts.error ? <ErrorState message={safeErrorMessage(accounts.error)} /> : null}
      {!accounts.isLoading && !accounts.error && !accounts.data?.accounts.length ? (
        <EmptyState message="No Meta ad accounts are accessible with the configured backend token." />
      ) : null}

      {accounts.data?.accounts.length ? (
        <form className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end" onSubmit={configure}>
          <label className="space-y-2 font-medium">
            <span>Meta ad account</span>
            <select
              className="form-input"
              onChange={(event) => setAccountId(event.target.value)}
              value={accountId}
            >
              <option value="">Select an account</option>
              {accounts.data.accounts.map((account) => (
                <option key={account.external_account_id} value={account.external_account_id}>
                  {account.name ?? "Unnamed account"} ({account.external_account_id})
                </option>
              ))}
            </select>
          </label>
          <button className="primary-button" disabled={busyAction !== null} type="submit">
            {busyAction === "configure" ? "Saving..." : "Assign account"}
          </button>
        </form>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <button
          className="secondary-button"
          disabled={busyAction !== null}
          onClick={testConnection}
          type="button"
        >
          {busyAction === "test" ? "Testing..." : "Test Meta connection"}
        </button>
        <button
          className="secondary-button"
          disabled={accounts.isLoading}
          onClick={() => accounts.mutate()}
          type="button"
        >
          Refresh accounts
        </button>
      </div>

      <form
        className="grid gap-4 border-t border-growthbyte-black/20 pt-6 sm:grid-cols-2"
        onSubmit={sync}
      >
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
        <div className="sm:col-span-2">
          <button className="primary-button" disabled={busyAction !== null} type="submit">
            {busyAction === "sync" ? "Syncing Meta..." : "Run Meta sync"}
          </button>
        </div>
      </form>

      {actionState ? <ActionNotice state={actionState} /> : null}

      <div className="space-y-3 border-t border-growthbyte-black/20 pt-6">
        <h3 className="text-xl font-semibold">Recent Meta syncs</h3>
        <SyncHistory
          error={history.error}
          isLoading={history.isLoading}
          runs={history.data}
          sourceLabel="Meta"
        />
      </div>
    </section>
  );
}

function ActionNotice({ state }: Readonly<{ state: ActionState }>) {
  return (
    <p
      className={`border p-4 ${
        state.kind === "success"
          ? "border-growthbyte-teal bg-teal-50 text-growthbyte-black"
          : "border-red-700 bg-red-50 text-red-900"
      }`}
      role={state.kind === "error" ? "alert" : "status"}
    >
      {state.message}
    </p>
  );
}

function getInitialDates(): { dateFrom: string; dateTo: string } {
  const dateTo = new Date();
  const dateFrom = new Date(dateTo);
  dateFrom.setUTCDate(dateFrom.getUTCDate() - 6);
  return {
    dateFrom: dateFrom.toISOString().slice(0, 10),
    dateTo: dateTo.toISOString().slice(0, 10),
  };
}
