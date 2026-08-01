"use client";

import type { ClientDetails as ClientDetailsContract } from "@growthbyte/shared-types";
import Link from "next/link";
import useSWR from "swr";

import { api, safeErrorMessage } from "../../lib/api-client";
import { ErrorState, LoadingState } from "../async-state";
import { KpiManager } from "../kpis/kpi-manager";

export function ClientDetails({ clientId }: Readonly<{ clientId: string }>) {
  const { data, error, isLoading } = useSWR<ClientDetailsContract>(["client", clientId], () =>
    api.getClient(clientId),
  );

  if (isLoading) {
    return <LoadingState label="Loading client details…" />;
  }
  if (error || !data) {
    return <ErrorState message={safeErrorMessage(error)} />;
  }

  return (
    <div className="space-y-12">
      <section aria-labelledby="client-heading">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
              Client details
            </p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight" id="client-heading">
              {data.name}
            </h1>
          </div>
          <Link
            className="border border-growthbyte-black px-4 py-2 font-medium hover:bg-growthbyte-black hover:text-growthbyte-white"
            href={`/clients/${encodeURIComponent(clientId)}/knowledge`}
          >
            Manage knowledge
          </Link>
        </div>
        <dl className="mt-8 grid gap-px bg-growthbyte-black sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Status", data.status],
            ["Slug", data.slug],
            ["Timezone", data.reporting_timezone],
            ["Currency", data.default_currency],
          ].map(([label, value]) => (
            <div className="bg-growthbyte-white p-4" key={label}>
              <dt className="text-xs font-semibold uppercase tracking-wider text-growthbyte-black/60">
                {label}
              </dt>
              <dd className="mt-2 font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <KpiManager clientId={clientId} reportingTimezone={data.reporting_timezone} />
    </div>
  );
}
