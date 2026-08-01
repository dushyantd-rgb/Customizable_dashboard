"use client";

import type { MetaAccountSummary, MetaSyncResult } from "@growthbyte/shared-types";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import useSWR, { mutate } from "swr";
import { z } from "zod";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";

const metaConfigSchema = z.object({
  external_account_id: z.string().min(1, "Account ID is required"),
  display_name: z.string().optional(),
});

const metaSyncSchema = z.object({
  date_from: z.string().min(1, "Start date is required"),
  date_to: z.string().min(1, "End date is required"),
  include_campaigns: z.boolean(),
  include_ad_sets: z.boolean(),
  include_ads: z.boolean(),
  include_insights: z.boolean(),
});

type MetaConfigForm = z.infer<typeof metaConfigSchema>;
type MetaSyncForm = z.infer<typeof metaSyncSchema>;

export function MetaIntegration({ clientId }: Readonly<{ clientId: string }>) {
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<MetaSyncResult | null>(null);

  const { data: accounts, error: accountsError, isLoading: loadingAccounts } = useSWR<
    MetaAccountSummary[]
  >("meta-accounts", () =>
    api
      .request<{ accounts: MetaAccountSummary[] }>("/integrations/meta/accounts")
      .then((r) => r.accounts),
  );

  const { data: connection, error: connectionError } = useSWR<{ connected: boolean }>(
    ["meta-connection", clientId],
    () =>
      api.request<{ connected: boolean }>(
        `/integrations/meta/clients/${encodeURIComponent(clientId)}/test`,
      ),
  );

  const configForm = useForm<MetaConfigForm>({
    resolver: zodResolver(metaConfigSchema),
    defaultValues: { external_account_id: "", display_name: "" },
  });

  const syncForm = useForm<MetaSyncForm>({
    resolver: zodResolver(metaSyncSchema),
    defaultValues: {
      date_from: "",
      date_to: "",
      include_campaigns: true,
      include_ad_sets: true,
      include_ads: true,
      include_insights: true,
    },
  });

  async function handleSaveConfig(values: MetaConfigForm) {
    setSavingConfig(true);
    try {
      await api.request(
        `/integrations/meta/clients/${encodeURIComponent(clientId)}/config`,
        {
          method: "POST",
          body: JSON.stringify(values),
        },
      );
      await mutate(["meta-connection", clientId]);
    } catch (error) {
      configForm.setError("root", { message: safeErrorMessage(error) });
    } finally {
      setSavingConfig(false);
    }
  }

  async function handleSync(values: MetaSyncForm) {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await api.request<MetaSyncResult>(
        `/integrations/meta/clients/${encodeURIComponent(clientId)}/sync`,
        {
          method: "POST",
          body: JSON.stringify({
            ...values,
            date_from: values.date_from,
            date_to: values.date_to,
          }),
        },
      );
      setSyncResult(result);
    } catch (error) {
      syncForm.setError("root", { message: safeErrorMessage(error) });
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="border border-growthbyte-black p-6">
        <h2 className="text-2xl font-semibold">Meta Ads Account</h2>
        <p className="mt-2 text-sm text-growthbyte-black/70">
          Select the Meta ad account to sync for this client. The environment token is used
          for discovery and sync.
        </p>

        {loadingAccounts ? <LoadingState label="Discovering accounts…" /> : null}
        {accountsError ? <ErrorState message={safeErrorMessage(accountsError)} /> : null}

        {accounts && accounts.length > 0 ? (
          <form className="mt-6 space-y-4" onSubmit={configForm.handleSubmit(handleSaveConfig)}>
            <label className="block">
              <span className="font-medium">Ad Account</span>
              <select
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                {...configForm.register("external_account_id")}
              >
                <option value="">Select an account</option>
                {accounts.map((acc) => (
                  <option key={acc.external_account_id} value={acc.external_account_id}>
                    {acc.name} ({acc.external_account_id})
                  </option>
                ))}
              </select>
              {configForm.formState.errors.external_account_id ? (
                <p className="mt-1 text-sm text-red-800">
                  {configForm.formState.errors.external_account_id.message}
                </p>
              ) : null}
            </label>

            <label className="block">
              <span className="font-medium">Display Name (optional)</span>
              <input
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                type="text"
                {...configForm.register("display_name")}
                placeholder="e.g., Client Alpha - Main Account"
              />
            </label>

            <button
              className="primary-button"
              disabled={savingConfig}
              type="submit"
            >
              {savingConfig ? "Saving…" : "Save Configuration"}
            </button>
          </form>
        ) : accounts && accounts.length === 0 ? (
          <EmptyState message="No Meta ad accounts found for the environment token." />
        ) : null}

        {connection?.connected ? (
          <div className="mt-4 text-sm text-green-700">
            ✓ Meta account configured
          </div>
        ) : null}
      </section>

      {connection?.connected ? (
        <section className="border border-growthbyte-black p-6">
          <h2 className="text-2xl font-semibold">Manual Sync</h2>
          <p className="mt-2 text-sm text-growthbyte-black/70">
            Sync campaigns, ads, and insights for a specific date range. This will pull data
            from Meta and store it in your reporting database.
          </p>

          <form className="mt-6 space-y-4" onSubmit={syncForm.handleSubmit(handleSync)}>
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="block">
                <span className="font-medium">Start Date</span>
                <input
                  className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                  type="date"
                  {...syncForm.register("date_from")}
                />
                {syncForm.formState.errors.date_from ? (
                  <p className="mt-1 text-sm text-red-800">
                    {syncForm.formState.errors.date_from.message}
                  </p>
                ) : null}
              </label>

              <label className="block">
                <span className="font-medium">End Date</span>
                <input
                  className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                  type="date"
                  {...syncForm.register("date_to")}
                />
                {syncForm.formState.errors.date_to ? (
                  <p className="mt-1 text-sm text-red-800">
                    {syncForm.formState.errors.date_to.message}
                  </p>
                ) : null}
              </label>
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <label className="flex items-center gap-3">
                <input
                  className="h-5 w-5 border border-growthbyte-black"
                  type="checkbox"
                  {...syncForm.register("include_campaigns")}
                />
                <span>Sync Campaigns</span>
              </label>

              <label className="flex items-center gap-3">
                <input
                  className="h-5 w-5 border border-growthbyte-black"
                  type="checkbox"
                  {...syncForm.register("include_ad_sets")}
                />
                <span>Sync Ad Sets</span>
              </label>

              <label className="flex items-center gap-3">
                <input
                  className="h-5 w-5 border border-growthbyte-black"
                  type="checkbox"
                  {...syncForm.register("include_ads")}
                />
                <span>Sync Ads</span>
              </label>

              <label className="flex items-center gap-3">
                <input
                  className="h-5 w-5 border border-growthbyte-black"
                  type="checkbox"
                  {...syncForm.register("include_insights")}
                />
                <span>Sync Insights</span>
              </label>
            </div>

            <button
              className="primary-button"
              disabled={syncing}
              type="submit"
            >
              {syncing ? "Syncing…" : "Start Sync"}
            </button>
          </form>

          {syncResult ? (
            <div className="mt-6 border border-growthbyte-teal bg-growthbyte-teal/10 p-4">
              <h3 className="font-semibold text-growthbyte-teal">Sync Complete</h3>
              <div className="mt-3 grid gap-2 text-sm">
                <div>
                  <span className="font-medium">Status:</span> {syncResult.status}
                </div>
                <div>
                  <span className="font-medium">Rows Read:</span> {syncResult.rows_read}
                </div>
                <div>
                  <span className="font-medium">Rows Written:</span> {syncResult.rows_written}
                </div>
                <div className="grid gap-1 lg:grid-cols-3">
                  <div>Campaigns: {syncResult.campaigns_synced}</div>
                  <div>Ad Sets: {syncResult.ad_sets_synced}</div>
                  <div>Ads: {syncResult.ads_synced}</div>
                </div>
                <div>Insights: {syncResult.insights_synced}</div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
