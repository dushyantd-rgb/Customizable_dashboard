import { ClientList } from "../../components/clients/client-list";

export default function ClientsPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
        Reporting clients
      </p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Client workspace</h1>
      <p className="mb-8 mt-4 max-w-2xl leading-7 text-growthbyte-black/75">
        Choose a client to maintain its reporting knowledge and KPI configuration.
      </p>
      <ClientList />
    </main>
  );
}
