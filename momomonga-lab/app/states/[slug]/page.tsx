import { notFound } from "next/navigation";
import { getState } from "@/lib/content/states";

type Props = {
  params: Promise<{ slug: string }>;
};

export default async function StateDetailPage({ params }: Props) {
  const { slug } = await params;
  const state = getState(slug);
  if (!state) notFound();

  return (
    <main className="card">
      <p className="eyebrow">State</p>
      <h1 className="mt-4 text-4xl font-semibold">{state.title}</h1>
      <p className="mt-5 text-base leading-8 text-[var(--muted)]">{state.goal}</p>
      <ul className="mt-8 grid gap-3 text-sm text-[var(--muted)] md:grid-cols-2">
        {state.symptoms.map((symptom) => (
          <li key={symptom} className="rounded-2xl border border-[var(--line)] px-4 py-3">
            {symptom}
          </li>
        ))}
      </ul>
    </main>
  );
}
