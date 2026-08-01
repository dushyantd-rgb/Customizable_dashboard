"use client";

import type { KnowledgeRecord } from "@growthbyte/shared-types";
import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";
import { KnowledgeForm } from "./knowledge-form";

export function KnowledgeManager({ clientId }: Readonly<{ clientId: string }>) {
  const { data, error, isLoading, mutate } = useSWR<KnowledgeRecord[]>(
    ["knowledge", clientId],
    () => api.listKnowledge(clientId),
  );
  const [editing, setEditing] = useState<KnowledgeRecord | "new" | null>(null);
  const groups = useMemo(() => groupKnowledge(data ?? []), [data]);

  async function finishEdit() {
    await mutate();
    setEditing(null);
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <Link
            className="text-sm font-medium text-growthbyte-teal underline"
            href={`/clients/${encodeURIComponent(clientId)}`}
          >
            Back to client
          </Link>
          <p className="mt-5 font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
            Client knowledge
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Knowledge library</h1>
          <p className="mt-3 max-w-2xl leading-7 text-growthbyte-black/75">
            Review reporting-safe knowledge, its source, and its version. Manual edits never change
            the source identity.
          </p>
        </div>
        <button className="primary-button" onClick={() => setEditing("new")} type="button">
          Add knowledge
        </button>
      </header>

      {editing ? (
        <KnowledgeForm
          clientId={clientId}
          key={editing === "new" ? "new" : editing.id}
          onCancel={() => setEditing(null)}
          onSaved={finishEdit}
          record={editing === "new" ? undefined : editing}
        />
      ) : null}

      {isLoading ? <LoadingState label="Loading knowledge…" /> : null}
      {error ? <ErrorState message={safeErrorMessage(error)} /> : null}
      {!isLoading && !error && groups.length === 0 ? (
        <EmptyState message="No knowledge records exist for this client." />
      ) : null}
      {groups.map(([category, records]) => (
        <section className="space-y-4" key={category}>
          <h2 className="border-b border-growthbyte-black pb-2 text-2xl font-semibold">
            {category}
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {records.map((record) => (
              <KnowledgeCard key={record.id} onEdit={() => setEditing(record)} record={record} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function KnowledgeCard({
  onEdit,
  record,
}: Readonly<{ onEdit: () => void; record: KnowledgeRecord }>) {
  const manual = record.source_type === "manual";
  return (
    <article className="border border-growthbyte-black p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{record.knowledge_key}</h3>
          <p className="mt-1 text-sm text-growthbyte-black/65">Status: {record.status}</p>
        </div>
        <span
          className={`px-2 py-1 text-xs font-semibold uppercase ${
            manual
              ? "bg-growthbyte-black text-growthbyte-white"
              : "bg-growthbyte-teal text-growthbyte-white"
          }`}
        >
          {manual ? "Manual" : "Imported"}
        </span>
      </div>
      <pre className="mt-4 max-h-64 overflow-auto bg-growthbyte-black/5 p-4 text-xs leading-5">
        {JSON.stringify(record.value, null, 2)}
      </pre>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-growthbyte-black/60">Source</dt>
          <dd>{manual ? "Manual entry" : (record.source_display_name ?? record.source_type)}</dd>
        </div>
        <div>
          <dt className="text-growthbyte-black/60">Version</dt>
          <dd>{record.source_version ?? record.version}</dd>
        </div>
      </dl>
      <button className="secondary-button mt-5" onClick={onEdit} type="button">
        Edit {record.knowledge_key}
      </button>
    </article>
  );
}

function groupKnowledge(records: readonly KnowledgeRecord[]): [string, KnowledgeRecord[]][] {
  const grouped = new Map<string, KnowledgeRecord[]>();
  for (const record of records) {
    const categoryRecords = grouped.get(record.category) ?? [];
    categoryRecords.push(record);
    grouped.set(record.category, categoryRecords);
  }
  return [...grouped.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([category, categoryRecords]) => [
      category,
      categoryRecords.sort((left, right) => left.knowledge_key.localeCompare(right.knowledge_key)),
    ]);
}
