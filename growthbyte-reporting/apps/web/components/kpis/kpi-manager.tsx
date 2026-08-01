"use client";

import type { KpiRecord } from "@growthbyte/shared-types";
import { useState } from "react";
import useSWR from "swr";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";
import { KpiForm } from "./kpi-form";

interface KpiManagerProps {
  readonly clientId: string;
  readonly reportingTimezone: string;
}

export function KpiManager({ clientId, reportingTimezone }: KpiManagerProps) {
  const { data, error, isLoading, mutate } = useSWR<KpiRecord[]>(["kpis", clientId], () =>
    api.listKpis(clientId),
  );
  const [editing, setEditing] = useState<KpiRecord | "new" | null>(null);

  async function finishEdit() {
    await mutate();
    setEditing(null);
  }

  return (
    <section className="space-y-6" aria-labelledby="kpi-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
            KPI configuration
          </p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight" id="kpi-heading">
            Client KPIs
          </h2>
          <p className="mt-2 text-growthbyte-black/70">
            Targets and effective periods only. Performance is calculated in a later phase.
          </p>
        </div>
        <button className="primary-button" onClick={() => setEditing("new")} type="button">
          Add KPI
        </button>
      </div>

      {editing ? (
        <KpiForm
          clientId={clientId}
          key={editing === "new" ? "new" : editing.id}
          onCancel={() => setEditing(null)}
          onSaved={finishEdit}
          record={editing === "new" ? undefined : editing}
        />
      ) : null}

      {isLoading ? <LoadingState label="Loading KPIs…" /> : null}
      {error ? <ErrorState message={safeErrorMessage(error)} /> : null}
      {!isLoading && !error && !data?.length ? (
        <EmptyState message="No KPIs are configured for this client." />
      ) : null}
      {data?.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((record) => (
            <KpiCard
              key={record.id}
              onEdit={() => setEditing(record)}
              record={record}
              reportingTimezone={reportingTimezone}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

interface KpiCardProps {
  readonly onEdit: () => void;
  readonly record: KpiRecord;
  readonly reportingTimezone: string;
}

function KpiCard({ onEdit, record, reportingTimezone }: KpiCardProps) {
  const effectiveState = getEffectiveState(record, reportingTimezone);
  return (
    <article className="border border-growthbyte-black p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{record.label}</h3>
          <p className="mt-1 text-sm text-growthbyte-black/65">{record.metric_key}</p>
        </div>
        <span className="bg-growthbyte-black px-2 py-1 text-xs uppercase text-growthbyte-white">
          {effectiveState}
        </span>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
        <KpiValue label="Target" value={record.target_value ?? "Not set"} />
        <KpiValue label="Unit" value={record.unit} />
        <KpiValue label="Direction" value={record.direction} />
        <KpiValue label="Attribution" value={record.attribution_level} />
        <KpiValue label="Active from" value={record.active_from} />
        <KpiValue label="Active to" value={record.active_to ?? "Open-ended"} />
      </dl>
      <button className="secondary-button mt-5" onClick={onEdit} type="button">
        Edit {record.label}
      </button>
    </article>
  );
}

function KpiValue({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div>
      <dt className="text-growthbyte-black/60">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  );
}

function getEffectiveState(
  record: KpiRecord,
  reportingTimezone: string,
): "Active" | "Configured" | "Ended" | "Scheduled" {
  const today = dateInTimezone(reportingTimezone);
  if (today === null) {
    return "Configured";
  }
  if (record.active_from > today) {
    return "Scheduled";
  }
  if (record.active_to && record.active_to < today) {
    return "Ended";
  }
  return "Active";
}

function dateInTimezone(timeZone: string): string | null {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      day: "2-digit",
      month: "2-digit",
      timeZone,
      year: "numeric",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    if (!values.year || !values.month || !values.day) {
      return null;
    }
    return `${values.year}-${values.month}-${values.day}`;
  } catch {
    return null;
  }
}
