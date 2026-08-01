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
          <div className="flex flex-wrap gap-3">
            <Link
              className="border border-growthbyte-black px-4 py-2 font-medium hover:bg-growthbyte-black hover:text-growthbyte-white"
              href={`/clients/${encodeURIComponent(clientId)}/integrations`}
            >
              Manage integrations
            </Link>
            <Link
              className="border border-growthbyte-black px-4 py-2 font-medium hover:bg-growthbyte-black hover:text-growthbyte-white"
              href={`/clients/${encodeURIComponent(clientId)}/knowledge`}
            >
              Manage knowledge
            </Link>
            <Link
              className="border border-blue-600 bg-blue-600 text-white px-4 py-2 font-medium hover:bg-blue-700"
              href={`/clients/${encodeURIComponent(clientId)}/matching`}
            >
              Lead Matching
            </Link>
            <Link
              className="border border-green-600 bg-green-600 text-white px-4 py-2 font-medium hover:bg-green-700"
              href={`/clients/${encodeURIComponent(clientId)}/metrics`}
            >
              Metrics Dashboard
            </Link>
          </div>
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

        {/* Phase 4 Features Banner */}
        <div className="mt-8 bg-gradient-to-r from-blue-50 to-green-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            🎯 Phase 4: Attribution Matching & Metrics
          </h3>
          <p className="text-gray-700 mb-4">
            New features available! Match leads to campaigns and view calculated KPIs with quality scores.
          </p>
          <div className="flex gap-4">
            <div className="flex-1">
              <h4 className="font-medium text-blue-900">Lead Matching</h4>
              <p className="text-sm text-gray-600">Match imported leads to Meta campaigns for accurate attribution</p>
            </div>
            <div className="flex-1">
              <h4 className="font-medium text-green-900">Metrics Dashboard</h4>
              <p className="text-sm text-gray-600">View calculated KPIs including CPL, qualification rates, and more</p>
            </div>
          </div>
        </div>
      </section>
      <KpiManager clientId={clientId} reportingTimezone={data.reporting_timezone} />
    </div>
  );
}
