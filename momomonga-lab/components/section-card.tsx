import Link from "next/link";

type SectionCardProps = {
  href: string;
  eyebrow: string;
  title: string;
  description: string;
};

export function SectionCard({
  href,
  eyebrow,
  title,
  description
}: SectionCardProps) {
  return (
    <Link href={href} className="card block transition-transform hover:-translate-y-1">
      <p className="eyebrow">{eyebrow}</p>
      <h3 className="mt-3 text-2xl font-semibold">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-[var(--muted)]">{description}</p>
    </Link>
  );
}
