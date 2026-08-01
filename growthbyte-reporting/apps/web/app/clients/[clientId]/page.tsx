import { ClientDetails } from "../../../components/clients/client-details";

interface ClientPageProps {
  readonly params: Promise<{ clientId: string }>;
}

export default async function ClientPage({ params }: ClientPageProps) {
  const { clientId } = await params;
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <ClientDetails clientId={clientId} />
    </main>
  );
}
