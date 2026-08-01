import { IntegrationsManager } from "../../../../components/integrations/integrations-manager";

interface IntegrationsPageProps {
  readonly params: Promise<{ clientId: string }>;
}

export default async function IntegrationsPage({ params }: IntegrationsPageProps) {
  const { clientId } = await params;
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <IntegrationsManager clientId={clientId} />
    </main>
  );
}
