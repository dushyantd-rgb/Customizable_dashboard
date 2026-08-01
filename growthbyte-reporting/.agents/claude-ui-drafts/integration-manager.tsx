"use client";

import Link from "next/link";
import { useState } from "react";
import { MetaIntegration } from "./meta-integration";
import { GoogleIntegration } from "./google-integration";

export function IntegrationManager({ clientId }: Readonly<{ clientId: string }>) {
  const [activeTab, setActiveTab] = useState<"meta" | "google">("meta");

  return (
    <div className="space-y-8">
      <header>
        <Link
          className="text-sm font-medium text-growthbyte-teal underline"
          href={`/clients/${encodeURIComponent(clientId)}`}
        >
          Back to client
        </Link>
        <p className="mt-5 font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
          Integrations
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight">
          Connect your data sources
        </h1>
        <p className="mt-3 max-w-2xl leading-7 text-growthbyte-black/75">
          Connect Meta Ads and Google Sheets to import marketing performance and lead data.
          All connections are client-scoped and credentials are encrypted.
        </p>
      </header>

      <div className="border-b border-growthbyte-black">
        <nav className="flex gap-8">
          <button
            className={`pb-4 text-lg font-medium ${
              activeTab === "meta"
                ? "border-b-2 border-growthbyte-teal text-growthbyte-teal"
                : "text-growthbyte-black/60 hover:text-growthbyte-black"
            }`}
            onClick={() => setActiveTab("meta")}
            type="button"
          >
            Meta Ads
          </button>
          <button
            className={`pb-4 text-lg font-medium ${
              activeTab === "google"
                ? "border-b-2 border-growthbyte-teal text-growthbyte-teal"
                : "text-growthbyte-black/60 hover:text-growthbyte-black"
            }`}
            onClick={() => setActiveTab("google")}
            type="button"
          >
            Google Sheets
          </button>
        </nav>
      </div>

      <div>
        {activeTab === "meta" ? (
          <MetaIntegration clientId={clientId} />
        ) : (
          <GoogleIntegration clientId={clientId} />
        )}
      </div>
    </div>
  );
}
