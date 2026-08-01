"use client";

import type {
  ColumnMappingInput,
  SpreadsheetSummary,
  StatusMappingInput,
  SyncRunSummary,
  WorksheetSummary,
} from "@growthbyte/shared-types";
import { FormEvent, useMemo, useState } from "react";
import useSWR from "swr";

import { api, googleOAuthUrl, safeErrorMessage } from "../../lib/api-client";
import { SyncHistory } from "./sync-history";

interface GoogleIntegrationPanelProps {
  readonly clientId: string;
}

interface ActionState {
  readonly kind: "error" | "success";
  readonly message: string;
}

interface StatusDraft {
  readonly source_value: string;
  readonly canonical_status: string;
  readonly counts_as_reviewed: boolean;
}

const canonicalLeadFields = [
  "source_lead_id",
  "lead_date",
  "lead_identifier",
  "campaign_id",
  "campaign_name",
  "adset_id",
  "adset_name",
  "ad_id",
  "ad_name",
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "lead_status",
  "is_qualified",
  "lead_stage",
  "qualification_reason",
  "disqualification_reason",
  "sales_notes",
  "owner",
  "follow_up_status",
  "conversion_status",
  "revenue",
] as const;

const canonicalStatuses = [
  "qualified",
  "in_progress",
  "invalid",
  "disqualified",
  "converted",
  "not_reviewed",
] as const;

const initialStatusDraft: StatusDraft = {
  source_value: "",
  canonical_status: "not_reviewed",
  counts_as_reviewed: false,
};

export function GoogleIntegrationPanel({ clientId }: GoogleIntegrationPanelProps) {
  const history = useSWR<SyncRunSummary[]>(["google-sync-runs", clientId], () =>
    api.listGoogleSyncRuns(clientId),
  );
  const [spreadsheets, setSpreadsheets] = useState<readonly SpreadsheetSummary[]>([]);
  const [worksheets, setWorksheets] = useState<readonly WorksheetSummary[]>([]);
  const [spreadsheetId, setSpreadsheetId] = useState("");
  const [worksheetName, setWorksheetName] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  const [dataStartRow, setDataStartRow] = useState(2);
  const [headers, setHeaders] = useState<readonly string[]>([]);
  const [columnFields, setColumnFields] = useState<Record<string, string>>({});
  const [requiredHeaders, setRequiredHeaders] = useState<ReadonlySet<string>>(new Set());
  const [statusDrafts, setStatusDrafts] = useState<readonly StatusDraft[]>([initialStatusDraft]);
  const [configId, setConfigId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionState, setActionState] = useState<ActionState | null>(null);

  const columnMappings = useMemo<ColumnMappingInput[]>(
    () =>
      headers
        .filter((header) => Boolean(columnFields[header]))
        .map((header) => ({
          source_header: header,
          canonical_field: columnFields[header],
          required: requiredHeaders.has(header),
        })),
    [columnFields, headers, requiredHeaders],
  );

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

  async function testConnection() {
    await runAction("test", async () => {
      const result = await api.testGoogle(clientId);
      return result.connected
        ? { kind: "success", message: "Google Sheets connection is ready and read-only." }
        : { kind: "error", message: "Google Sheets is not connected for this client." };
    });
  }

  async function discoverSpreadsheets() {
    await runAction("discover-spreadsheets", async () => {
      const discovered = await api.listGoogleSpreadsheets(clientId);
      setSpreadsheets(discovered);
      if (discovered.length === 1) {
        setSpreadsheetId(discovered[0].id);
      }
      return discovered.length
        ? { kind: "success", message: `Found ${discovered.length} readable spreadsheet(s).` }
        : { kind: "error", message: "No readable Google spreadsheets were found." };
    });
  }

  async function loadWorksheets() {
    if (!spreadsheetId.trim()) {
      setActionState({ kind: "error", message: "Select or enter a spreadsheet first." });
      return;
    }
    await runAction("worksheets", async () => {
      const discovered = await api.listGoogleWorksheets(clientId, spreadsheetId.trim());
      setWorksheets(discovered);
      setWorksheetName(discovered.length === 1 ? discovered[0].name : "");
      setHeaders([]);
      return discovered.length
        ? { kind: "success", message: `Found ${discovered.length} worksheet(s).` }
        : { kind: "error", message: "This spreadsheet has no readable worksheets." };
    });
  }

  async function previewHeaders() {
    if (!spreadsheetId.trim() || !worksheetName) {
      setActionState({ kind: "error", message: "Select a spreadsheet and worksheet first." });
      return;
    }
    if (dataStartRow <= headerRow) {
      setActionState({ kind: "error", message: "Data must start after the header row." });
      return;
    }
    await runAction("preview", async () => {
      const preview = await api.previewGoogleSheet(
        clientId,
        spreadsheetId.trim(),
        worksheetName,
        headerRow,
        dataStartRow,
      );
      const safeHeaders = preview.headers.filter((header) => header.trim().length > 0);
      setHeaders(safeHeaders);
      setColumnFields((current) =>
        Object.fromEntries(safeHeaders.map((header) => [header, current[header] ?? ""])),
      );
      return safeHeaders.length
        ? { kind: "success", message: `Read ${safeHeaders.length} worksheet header(s).` }
        : { kind: "error", message: "The selected header row is empty." };
    });
  }

  async function saveConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spreadsheetId.trim() || !worksheetName || dataStartRow <= headerRow) {
      setActionState({ kind: "error", message: "Complete a valid Sheet configuration first." });
      return;
    }
    if (!columnMappings.length) {
      setActionState({ kind: "error", message: "Map at least one Sheet column." });
      return;
    }
    const statusMappings = normalizedStatusMappings(statusDrafts);
    await runAction("save", async () => {
      const configured = await api.configureGoogleSheet(clientId, {
        spreadsheet_id: spreadsheetId.trim(),
        worksheet_name: worksheetName,
        header_row: headerRow,
        data_start_row: dataStartRow,
      });
      const columns = await api.saveGoogleColumnMappings(
        clientId,
        configured.config_id,
        columnMappings,
      );
      let statusesSaved = 0;
      if (statusMappings.length) {
        const statuses = await api.saveGoogleStatusMappings(
          clientId,
          configured.config_id,
          statusMappings,
        );
        statusesSaved = statuses.mappings_saved;
      }
      setConfigId(configured.config_id);
      return {
        kind: "success",
        message: `Saved ${columns.mappings_saved} column mapping(s) and ${statusesSaved} status mapping(s).`,
      };
    });
  }

  async function syncSheet() {
    await runAction("sync", async () => {
      const result = await api.syncGoogle(clientId);
      await history.mutate();
      return {
        kind: "success",
        message: `Google sync ${result.status}: ${result.rows_read} read, ${result.rows_written} upserted, ${result.rows_skipped} skipped.`,
      };
    });
  }

  function updateStatusDraft(index: number, patch: Partial<StatusDraft>) {
    setStatusDrafts((current) =>
      current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, ...patch } : draft)),
    );
  }

  return (
    <section
      className="space-y-6 border border-growthbyte-black p-6"
      aria-labelledby="google-heading"
    >
      <header>
        <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
          Google Sheets
        </p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight" id="google-heading">
          Read-only lead import
        </h2>
        <p className="mt-2 max-w-3xl text-growthbyte-black/70">
          Connect Google, select one Sheet, map its columns and statuses, then run a manual import.
          This prototype never writes to the source spreadsheet.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <a className="primary-button" href={googleOAuthUrl(clientId)}>
          Connect Google
        </a>
        <button
          className="secondary-button"
          disabled={busyAction !== null}
          onClick={testConnection}
          type="button"
        >
          {busyAction === "test" ? "Testing..." : "Test Google connection"}
        </button>
        <button
          className="secondary-button"
          disabled={busyAction !== null}
          onClick={discoverSpreadsheets}
          type="button"
        >
          {busyAction === "discover-spreadsheets" ? "Loading..." : "Discover spreadsheets"}
        </button>
      </div>

      <form
        className="space-y-6 border-t border-growthbyte-black/20 pt-6"
        onSubmit={saveConfiguration}
      >
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <label className="space-y-2 font-medium">
            <span>Spreadsheet</span>
            <input
              className="form-input"
              list="google-spreadsheets"
              onChange={(event) => {
                setSpreadsheetId(event.target.value);
                setWorksheets([]);
                setWorksheetName("");
                setHeaders([]);
              }}
              placeholder="Select a discovered Sheet or paste its ID"
              value={spreadsheetId}
            />
            <datalist id="google-spreadsheets">
              {spreadsheets.map((spreadsheet) => (
                <option key={spreadsheet.id} value={spreadsheet.id}>
                  {spreadsheet.name ?? spreadsheet.id}
                </option>
              ))}
            </datalist>
          </label>
          <button
            className="secondary-button"
            disabled={busyAction !== null}
            onClick={loadWorksheets}
            type="button"
          >
            {busyAction === "worksheets" ? "Loading..." : "Load worksheets"}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="space-y-2 font-medium">
            <span>Worksheet</span>
            <select
              className="form-input"
              onChange={(event) => {
                setWorksheetName(event.target.value);
                setHeaders([]);
              }}
              value={worksheetName}
            >
              <option value="">Select a worksheet</option>
              {worksheets.map((worksheet) => (
                <option key={worksheet.sheet_id} value={worksheet.name}>
                  {worksheet.name} ({worksheet.row_count} rows)
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 font-medium">
            <span>Header row</span>
            <input
              className="form-input"
              min={1}
              onChange={(event) => setHeaderRow(Number(event.target.value))}
              type="number"
              value={headerRow}
            />
          </label>
          <label className="space-y-2 font-medium">
            <span>Data starts on row</span>
            <input
              className="form-input"
              min={2}
              onChange={(event) => setDataStartRow(Number(event.target.value))}
              type="number"
              value={dataStartRow}
            />
          </label>
        </div>

        <button
          className="secondary-button"
          disabled={busyAction !== null}
          onClick={previewHeaders}
          type="button"
        >
          {busyAction === "preview" ? "Reading headers..." : "Preview headers"}
        </button>

        {headers.length ? (
          <fieldset className="space-y-3">
            <legend className="text-xl font-semibold">Column mapping</legend>
            <p className="text-sm text-growthbyte-black/70">
              Only approved canonical lead fields are available. Required columns stop a sync if
              their source header disappears.
            </p>
            <div className="overflow-x-auto border border-growthbyte-black">
              <table className="w-full min-w-[38rem] border-collapse text-left text-sm">
                <thead className="bg-growthbyte-black text-growthbyte-white">
                  <tr>
                    <th className="px-4 py-3" scope="col">
                      Sheet header
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Canonical field
                    </th>
                    <th className="px-4 py-3" scope="col">
                      Required
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {headers.map((header) => (
                    <tr className="border-t border-growthbyte-black/20" key={header}>
                      <th className="px-4 py-3 font-medium" scope="row">
                        {header}
                      </th>
                      <td className="px-4 py-3">
                        <select
                          aria-label={`Map ${header}`}
                          className="form-input"
                          onChange={(event) =>
                            setColumnFields((current) => ({
                              ...current,
                              [header]: event.target.value,
                            }))
                          }
                          value={columnFields[header] ?? ""}
                        >
                          <option value="">Do not import</option>
                          {canonicalLeadFields.map((field) => (
                            <option key={field} value={field}>
                              {field}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <input
                          aria-label={`Require ${header}`}
                          checked={requiredHeaders.has(header)}
                          disabled={!columnFields[header]}
                          onChange={(event) =>
                            setRequiredHeaders((current) => {
                              const next = new Set(current);
                              if (event.target.checked) next.add(header);
                              else next.delete(header);
                              return next;
                            })
                          }
                          type="checkbox"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </fieldset>
        ) : null}

        {headers.length ? (
          <fieldset className="space-y-3">
            <legend className="text-xl font-semibold">Lead-status mapping</legend>
            <p className="text-sm text-growthbyte-black/70">
              Unknown or blank values remain not reviewed; they are never guessed.
            </p>
            {statusDrafts.map((draft, index) => (
              <div
                className="grid gap-3 border border-growthbyte-black/20 p-4 sm:grid-cols-3"
                key={index}
              >
                <label className="space-y-2 font-medium">
                  <span>Source status {index + 1}</span>
                  <input
                    className="form-input"
                    onChange={(event) =>
                      updateStatusDraft(index, { source_value: event.target.value })
                    }
                    value={draft.source_value}
                  />
                </label>
                <label className="space-y-2 font-medium">
                  <span>Canonical status {index + 1}</span>
                  <select
                    className="form-input"
                    onChange={(event) =>
                      updateStatusDraft(index, { canonical_status: event.target.value })
                    }
                    value={draft.canonical_status}
                  >
                    {canonicalStatuses.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 self-end py-2 font-medium">
                  <input
                    checked={draft.counts_as_reviewed}
                    onChange={(event) =>
                      updateStatusDraft(index, { counts_as_reviewed: event.target.checked })
                    }
                    type="checkbox"
                  />
                  Counts as reviewed
                </label>
              </div>
            ))}
            <button
              className="secondary-button"
              onClick={() => setStatusDrafts((current) => [...current, { ...initialStatusDraft }])}
              type="button"
            >
              Add status mapping
            </button>
          </fieldset>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button className="primary-button" disabled={busyAction !== null} type="submit">
            {busyAction === "save" ? "Saving mapping..." : "Save Sheet mapping"}
          </button>
          {configId ? (
            <span className="text-sm text-growthbyte-black/65">Configuration saved.</span>
          ) : null}
        </div>
      </form>

      <div className="flex flex-wrap gap-3 border-t border-growthbyte-black/20 pt-6">
        <button
          className="primary-button"
          disabled={busyAction !== null}
          onClick={syncSheet}
          type="button"
        >
          {busyAction === "sync" ? "Syncing Sheet..." : "Run Google Sheet sync"}
        </button>
      </div>

      {actionState ? <ActionNotice state={actionState} /> : null}

      <div className="space-y-3 border-t border-growthbyte-black/20 pt-6">
        <h3 className="text-xl font-semibold">Recent Google Sheet syncs</h3>
        <SyncHistory
          error={history.error}
          isLoading={history.isLoading}
          runs={history.data}
          sourceLabel="Google Sheet"
        />
      </div>
    </section>
  );
}

function normalizedStatusMappings(drafts: readonly StatusDraft[]): StatusMappingInput[] {
  return drafts
    .filter((draft) => draft.source_value.trim().length > 0)
    .map((draft) => ({
      source_value: draft.source_value.trim(),
      canonical_status: draft.canonical_status,
      counts_as_reviewed: draft.counts_as_reviewed,
    }));
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
