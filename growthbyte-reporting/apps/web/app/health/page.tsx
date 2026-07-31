import { APIStatus } from "../../components/api-status";

export default function HealthPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <p className="font-semibold uppercase tracking-[0.2em] text-growthbyte-amber">
        Service health
      </p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">Web service is healthy</h1>
      <p className="mt-4 max-w-2xl leading-7">
        The application shell rendered successfully. API availability is checked independently
        below.
      </p>
      <div className="mt-8">
        <APIStatus />
      </div>
    </main>
  );
}
