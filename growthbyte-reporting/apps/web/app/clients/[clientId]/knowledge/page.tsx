import { KnowledgeManager } from "../../../../components/knowledge/knowledge-manager";

interface KnowledgePageProps {
  readonly params: Promise<{ clientId: string }>;
}

export default async function KnowledgePage({ params }: KnowledgePageProps) {
  const { clientId } = await params;
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <KnowledgeManager clientId={clientId} />
    </main>
  );
}
