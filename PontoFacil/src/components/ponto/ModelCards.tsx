import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import m1 from "@/assets/modelo1.jpg";
import m2 from "@/assets/modelo2.jpg";
import m3 from "@/assets/modelo3.jpg";
import m4 from "@/assets/modelo4.jpg";

const MODELS = [
  {
    id: "modelo-1",
    name: "Modelo 1",
    desc: "Faixa azul",
    img: m1,
    ready: true,
    to: "/processamento/modelo-1",
  },
  {
    id: "modelo-2",
    name: "Modelo 2",
    desc: "Folha diária",
    img: m2,
    ready: true,
    to: "/processamento/modelo-2",
  },
  {
    id: "modelo-3",
    name: "Modelo 3",
    desc: "Cartão tradicional",
    img: m3,
    ready: true,
    to: "/processamento/modelo-3",
  },
  {
    id: "modelo-4",
    name: "Modelo 4",
    desc: "Registro mensal",
    img: m4,
    ready: true,
    to: "/processamento/modelo-4",
  },
] as const;

export function ModelCards() {
  return (
    <section>
      <h2 className="mb-3 font-serif text-xl font-semibold">Novo processamento</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {MODELS.map((m) => {
          const inner = (
            <>
              <img
                src={m.img}
                alt={`Miniatura do ${m.name}`}
                loading="lazy"
                width={736}
                height={912}
                className="h-20 w-16 shrink-0 rounded object-cover shadow-sm"
              />
              <div className="flex-1">
                <div className="font-semibold">{m.name}</div>
                <div className="text-sm text-muted-foreground">{m.desc}</div>
                <span
                  className={cn(
                    "mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
                    m.ready ? "bg-success-soft text-success" : "bg-muted text-muted-foreground",
                  )}
                >
                  {m.ready ? "Já funciona" : "Em breve"}
                </span>
              </div>
              <ChevronRight className="h-5 w-5 text-primary" />
            </>
          );
          const cls =
            "flex h-28 items-center gap-4 rounded-xl border bg-card px-5 shadow-sm transition-colors";
          return m.ready ? (
            <Link
              key={m.id}
              to={m.to}
              className={cn(cls, "hover:border-primary/40 hover:bg-primary-soft/50")}
            >
              {inner}
            </Link>
          ) : (
            <div
              key={m.id}
              aria-disabled="true"
              title="Em desenvolvimento"
              className={cn(cls, "cursor-not-allowed")}
            >
              {inner}
            </div>
          );
        })}
      </div>
    </section>
  );
}
