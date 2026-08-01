"use client";

import type { SuperKFranchiseReportResponse } from "@growthbyte/report-schema";
import Link from "next/link";
import { useState } from "react";

import { api, safeErrorMessage } from "../../lib/api-client";
import { ErrorState } from "../async-state";
import { UnifiedReportView } from "./unified-report-view";

export function SuperKReportGenerator({ clientId }: Readonly<{ clientId: string }>) {
  const [report, setReport] = useState<SuperKFranchiseReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const generateReport = async () => {
    setError(null);
    setIsGenerating(true);
    try {
      setReport(await api.generateSuperKFranchiseReport(clientId));
    } catch (generationError) {
      setError(safeErrorMessage(generationError));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-8">
      <Link
        className="text-sm font-medium text-growthbyte-teal underline underline-offset-4"
        href={`/clients/${encodeURIComponent(clientId)}`}
      >
        Back to client
      </Link>

      {!report && (
        <section className="border border-growthbyte-black bg-growthbyte-white p-8 text-center">
          <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
            SuperK Franchise
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Unified monthly report</h1>
          <p className="mx-auto mt-4 max-w-2xl text-growthbyte-black/70">
            The configured client, latest completed month, approved data sources, knowledge, and KPI
            targets are selected automatically.
          </p>

          {error && (
            <div className="mt-6 text-left">
              <ErrorState message={error} />
            </div>
          )}

          <button
            aria-busy={isGenerating}
            className="primary-button mt-8 min-w-48"
            disabled={isGenerating}
            onClick={generateReport}
            type="button"
          >
            {isGenerating ? "Generating report…" : "Generate report"}
          </button>

          {isGenerating && (
            <p className="mt-4 text-sm text-growthbyte-black/60" role="status">
              Syncing verified sources and building the monthly snapshot…
            </p>
          )}
        </section>
      )}

      {report && <UnifiedReportView report={report} />}
    </div>
  );
}
