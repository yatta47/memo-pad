import Link from "next/link";
import type { IconNode } from "lucide";
import Icon from "@/components/Icon";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {description && <p className="lead">{description}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, tone = "neutral", icon, href }: {
  label: string; value: string | number; hint?: string; tone?: "danger" | "warn" | "ok" | "accent" | "neutral"; icon?: IconNode; href?: string;
}) {
  const body = (
    <>
      <span className="l">{label}</span>
      <span className="v">{value}</span>
      {hint && <span className="h">{hint}</span>}
      {icon && <span className="ico"><Icon node={icon} size={18} /></span>}
    </>
  );
  const cls = `stat-card tone-${tone}`;
  return href ? <Link href={href} className={cls}>{body}</Link> : <div className={cls}>{body}</div>;
}
