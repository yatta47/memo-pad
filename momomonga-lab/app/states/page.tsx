import Link from "next/link";
import { getStates } from "@/lib/content/states";

export default function StatesPage() {
  const states = getStates();

  return (
    <main className="space-y-6">
      <h1 className="text-4xl font-semibold">States</h1>
      <div className="grid gap-5 md:grid-cols-2">
        {states.map((state) => (
          <Link key={state.slug} href={`/states/${state.slug}`} className="card block">
            <h2 className="text-2xl font-semibold">{state.title}</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--muted)]">{state.goal}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
