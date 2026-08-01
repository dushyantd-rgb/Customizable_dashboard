import { APIStatus } from "../components/api-status";

export default function HomePage() {
  return (
    <main className="mx-auto grid min-h-[calc(100vh-75px)] max-w-5xl content-center gap-8 px-6 py-16">
      <section className="max-w-3xl">
        <p className="mb-4 font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
          Phase 2 client management
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          GrowthByte Reporting Platform
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8">
          Manage reporting clients, reviewed knowledge, and KPI targets while integrations,
          dashboards, and reporting workflows remain intentionally out of scope.
        </p>
      </section>
      <APIStatus />
    </main>
  );
}
