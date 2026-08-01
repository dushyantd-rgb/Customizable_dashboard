"use client";

import type { SpreadsheetSummary, WorksheetSummary } from "@growthbyte/shared-types";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import useSWR from "swr";
import { z } from "zod";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";

const googleConfigSchema = z.object({
  spreadsheet_id: z.string().min(1, "Spreadsheet is required"),
  worksheet_name: z.string().min(1, "Worksheet is required"),
  header_row: z.number().min(1).default(1),
  data_start_row: z.number().min(2).default(2),
  source_timezone: z.string().default("UTC"),
});

type GoogleConfigForm = z.infer<typeof googleConfigSchema>;

export function GoogleIntegration({ clientId }: Readonly<{ clientId: string }>) {
  const [savingConfig, setSavingConfig] = useState(false);
  const [selectedSpreadsheet, setSelectedSpreadsheet] = useState<string | null>(null);
  const [selectedWorksheet, setSelectedWorksheet] = useState<string | null>(null);

  const configForm = useForm<GoogleConfigForm>({
    resolver: zodResolver(googleConfigSchema),
    defaultValues: {
      spreadsheet_id: "",
      worksheet_name: "",
      header_row: 1,
      data_start_row: 2,
      source_timezone: "UTC",
    },
  });

  // Check connection status
  const { data: connection } = useSWR<{ connected: boolean }>(
    ["google-connection", clientId],
    () =>
      api.request<{ connected: boolean }>(
        `/integrations/google/test/${encodeURIComponent(clientId)}`,
      ),
  );

  // Load spreadsheets if connected
  const { data: spreadsheets, error: spreadsheetsError } = useSWR<SpreadsheetSummary[]>(
    connection?.connected ? ["google-spreadsheets", clientId] : null,
    () =>
      api
        .request<SpreadsheetSummary[]>(
          `/integrations/google/spreadsheets/${encodeURIComponent(clientId)}`,
        )
        .then((r) => r),
  );

  // Load worksheets if spreadsheet selected
  const { data: worksheets, error: worksheetsError } = useSWR<WorksheetSummary[]>(
    selectedSpreadsheet ? ["google-worksheets", clientId, selectedSpreadsheet] : null,
    () =>
      api.request<WorksheetSummary[]>(
        `/integrations/google/spreadsheets/${encodeURIComponent(clientId)}/${encodeURIComponent(selectedSpreadsheet ?? "")}/worksheets`,
      ),
  );

  async function handleConnectGoogle() {
    // Redirect to OAuth flow
    window.location.href = `/api/v1/integrations/google/connect/${encodeURIComponent(clientId)}`;
  }

  async function handleSaveConfig(values: GoogleConfigForm) {
    setSavingConfig(true);
    try {
      await api.request(
        `/integrations/google/config/${encodeURIComponent(clientId)}`,
        {
          method: "POST",
          body: JSON.stringify(values),
        },
      );
      alert("Configuration saved successfully!");
    } catch (error) {
      configForm.setError("root", { message: safeErrorMessage(error) });
    } finally {
      setSavingConfig(false);
    }
  }

  // If not connected, show connect button
  if (!connection?.connected) {
    return (
      <section className="border border-growthbyte-black p-6">
        <h2 className="text-2xl font-semibold">Google Sheets Connection</h2>
        <p className="mt-2 text-sm text-growthbyte-black/70">
          Connect your Google account to read lead data from Google Sheets. We only request
          read-only access and never write to your sheets.
        </p>

        <button
          className="mt-6 primary-button"
          onClick={handleConnectGoogle}
          type="button"
        >
          Connect Google Account
        </button>
      </section>
    );
  }

  // If connected, show configuration UI
  return (
    <div className="space-y-8">
      <section className="border border-growthbyte-black p-6">
        <h2 className="text-2xl font-semibold">Google Sheets Configuration</h2>
        <p className="mt-2 text-sm text-growthbyte-black/70">
          ✓ Connected to Google. Select a spreadsheet and worksheet to sync lead data.
        </p>

        {spreadsheetsError ? (
          <ErrorState message={safeErrorMessage(spreadsheetsError)} />
        ) : null}

        <form className="mt-6 space-y-4" onSubmit={configForm.handleSubmit(handleSaveConfig)}>
          {spreadsheets ? (
            <label className="block">
              <span className="font-medium">Spreadsheet</span>
              <select
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                value={selectedSpreadsheet ?? ""}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedSpreadsheet(value);
                  configForm.setValue("spreadsheet_id", value);
                  setSelectedWorksheet(null);
                  configForm.setValue("worksheet_name", "");
                }}
              >
                <option value="">Select a spreadsheet</option>
                {spreadsheets.map((sheet) => (
                  <option key={sheet.id} value={sheet.id}>
                    {sheet.name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <LoadingState label="Loading spreadsheets…" />
          )}

          {worksheets ? (
            <label className="block">
              <span className="font-medium">Worksheet</span>
              <select
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                value={selectedWorksheet ?? ""}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedWorksheet(value);
                  configForm.setValue("worksheet_name", value);
                }}
              >
                <option value="">Select a worksheet</option>
                {worksheets.map((ws) => (
                  <option key={ws.name} value={ws.name}>
                    {ws.name} ({ws.row_count} rows)
                  </option>
                ))}
              </select>
            </label>
          ) : selectedSpreadsheet ? (
            <LoadingState label="Loading worksheets…" />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <label className="block">
              <span className="font-medium">Header Row Number</span>
              <input
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                type="number"
                min={1}
                {...configForm.register("header_row", { valueAsNumber: true })}
              />
            </label>

            <label className="block">
              <span className="font-medium">Data Start Row</span>
              <input
                className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
                type="number"
                min={2}
                {...configForm.register("data_start_row", { valueAsNumber: true })}
              />
            </label>
          </div>

          <label className="block">
            <span className="font-medium">Source Timezone</span>
            <input
              className="mt-2 w-full border border-growthbyte-black bg-growthbyte-white px-4 py-3"
              type="text"
              {...configForm.register("source_timezone")}
              placeholder="UTC"
            />
          </label>

          <button
            className="primary-button"
            disabled={savingConfig || !selectedWorksheet}
            type="submit"
          >
            {savingConfig ? "Saving…" : "Save Configuration"}
          </button>
        </form>
      </section>

      <section className="border border-growthbyte-black/40 p-6 text-sm text-growthbyte-black/70">
        <h3 className="font-semibold">Phase 3 Prototype Notes</h3>
        <ul className="mt-3 space-y-2 pl-5">
          <li>
            • Column and status mapping configuration is shown as "coming soon" in this
            prototype
          </li>
          <li>
            • Manual sync will be available after completing mapping configuration
          </li>
          <li>
            • Raw Sheet rows are stored with idempotency - repeated syncs don't create
            duplicates
          </li>
          <li>
            • We never write to your Google Sheets - read-only access only
          </li>
        </ul>
      </section>
    </div>
  );
}
