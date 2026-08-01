"use client";

import Link from "next/link";

import { GoogleIntegrationPanel } from "./google-integration-panel";
import { MetaIntegrationPanel } from "./meta-integration-panel";

export function IntegrationsManager({ clientId }: Readonly<{ clientId: string }>) {
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
      <MetaIntegrationPanel clientId={clientId} />
      <GoogleIntegrationPanel clientId={clientId} />
    </div>
  );
}
