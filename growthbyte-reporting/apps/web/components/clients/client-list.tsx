"use client";

import type { ClientSummary } from "@growthbyte/shared-types";
import Link from "next/link";
import useSWR from "swr";

import { api, safeErrorMessage } from "../../lib/api-client";
import { EmptyState, ErrorState, LoadingState } from "../async-state";

export function ClientList() {
  const { data, error, isLoading } = useSWR<ClientSummary[]>("clients", () => api.listClients());

  if (isLoading) {
    return <LoadingState label="Loading clients…" />;
  }
  if (error) {
    return <ErrorState message={safeErrorMessage(error)} />;
  }
  if (!data?.length) {
    return <EmptyState message="No reporting clients are available." />;
  }

  return (
    <ul className="grid gap-4 md:grid-cols-2">
      {data.map((client) => (
        <li className="border border-growthbyte-black p-5" key={client.id}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">{client.name}</h2>
              <p className="mt-1 text-sm text-growthbyte-black/70">{client.slug}</p>
            </div>
            <span className="bg-growthbyte-black px-2 py-1 text-xs uppercase text-growthbyte-white">
              {client.status}
            </span>
          </div>
          <Link
            className="mt-5 inline-block font-medium text-growthbyte-teal underline underline-offset-4"
            href={`/clients/${encodeURIComponent(client.id)}`}
          >
            Open client
          </Link>
        </li>
      ))}
    </ul>
  );
}
