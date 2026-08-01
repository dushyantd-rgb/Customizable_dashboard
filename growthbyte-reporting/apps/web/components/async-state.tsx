export function LoadingState({ label }: Readonly<{ label: string }>) {
  return (
    <p className="border border-growthbyte-black/20 bg-growthbyte-white p-5" role="status">
      {label}
    </p>
  );
}

export function ErrorState({ message }: Readonly<{ message: string }>) {
  return (
    <p className="border border-red-700 bg-red-50 p-5 text-red-900" role="alert">
      {message}
    </p>
  );
}

export function EmptyState({ message }: Readonly<{ message: string }>) {
  return (
    <p className="border border-dashed border-growthbyte-black/40 p-8 text-center">{message}</p>
  );
}
