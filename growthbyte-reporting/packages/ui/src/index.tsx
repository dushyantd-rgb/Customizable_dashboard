export interface StatusCardProps {
  readonly detail: string;
  readonly healthy?: boolean;
  readonly label: string;
}

export function StatusCard({ detail, healthy = false, label }: StatusCardProps) {
  return (
    <section className="max-w-xl border border-growthbyte-black bg-growthbyte-white p-5">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className={`h-3 w-3 ${healthy ? "bg-growthbyte-teal" : "bg-growthbyte-amber"}`}
        />
        <h2 className="font-semibold">{label}</h2>
      </div>
      <p className="mt-2 text-sm leading-6">{detail}</p>
    </section>
  );
}
