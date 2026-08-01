"use client";

import Link from "next/link";
import { useState } from "react";

import { GoogleIntegrationPanel } from "./google-integration-panel";
import { LiveSyncPanel } from "./live-sync-panel";
import { MetaIntegrationPanel } from "./meta-integration-panel";

type IntegrationTab = "connections" | "sync";

interface IntegrationsManagerProps {
  readonly clientId: string;
  readonly initialTab?: IntegrationTab;
}

export function IntegrationsManager({
  clientId,
  initialTab = "connections",
}: Readonly<IntegrationsManagerProps>) {
  const [activeTab, setActiveTab] = useState<IntegrationTab>(initialTab);

  return (
    <div className="space-y-10">
      <header>
        <Link
          className="text-sm font-medium text-growthbyte-teal underline"
          href={`/clients/${encodeURIComponent(clientId)}`}
        >
          Back to client
        </Link>
        <p className="mt-5 font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
          Phase 3 prototype
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight">Source integrations</h1>
        <p className="mt-3 max-w-3xl leading-7 text-growthbyte-black/75">
          Configure one Meta ad account and one read-only Google worksheet for this client. Every
          request remains bound to this client ID.
        </p>
      </header>
      <div className="flex gap-2 border-b border-growthbyte-black" role="tablist">
        <button
          aria-controls="connections-panel"
          aria-selected={activeTab === "connections"}
          className={`px-5 py-3 font-semibold ${
            activeTab === "connections"
              ? "bg-growthbyte-black text-growthbyte-white"
              : "hover:bg-growthbyte-black/10"
          }`}
          id="connections-tab"
          onClick={() => setActiveTab("connections")}
          role="tab"
          type="button"
        >
          Connections
        </button>
        <button
          aria-controls="sync-panel"
          aria-selected={activeTab === "sync"}
          className={`px-5 py-3 font-semibold ${
            activeTab === "sync"
              ? "bg-growthbyte-black text-growthbyte-white"
              : "hover:bg-growthbyte-black/10"
          }`}
          id="sync-tab"
          onClick={() => setActiveTab("sync")}
          role="tab"
          type="button"
        >
          Sync live data
        </button>
      </div>
      {activeTab === "connections" ? (
        <div
          aria-labelledby="connections-tab"
          className="space-y-10"
          id="connections-panel"
          role="tabpanel"
        >
          <MetaIntegrationPanel clientId={clientId} showSyncControls={false} />
          <GoogleIntegrationPanel clientId={clientId} showSyncControls={false} />
        </div>
      ) : (
        <div aria-labelledby="sync-tab" id="sync-panel" role="tabpanel">
          <LiveSyncPanel clientId={clientId} />
        </div>
      )}
    </div>
  );
}
