import { IntegrationsManager } from "../../../../components/integrations/integrations-manager";

interface IntegrationsPageProps {
  readonly params: Promise<{ clientId: string }>;
  readonly searchParams: Promise<{ tab?: string }>;
}

export default async function IntegrationsPage({ params, searchParams }: IntegrationsPageProps) {
  const { clientId } = await params;
  const { tab } = await searchParams;
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <IntegrationsManager
        clientId={clientId}
        initialTab={tab === "sync" ? "sync" : "connections"}
      />
    </main>
  );
}
