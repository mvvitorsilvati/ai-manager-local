import { useQuery } from "@tanstack/react-query"
import { useMemo, useState, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { ViewSkeleton } from "@/components/bits"
import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api, type SpendBucket, type SpendTool } from "@/lib/api"

const PERIODS = [
  { days: 7, label: "7 dias" },
  { days: 30, label: "30 dias" },
  { days: 0, label: "Tudo" },
]

const TOOLS = ["claude", "codex", "opencode", "copilot"]

const TOOL_COLOR: Record<string, string> = {
  claude: "#D97757",
  codex: "#8ce99a",
  opencode: "#A855F7",
  copilot: "#22C55E",
}

const MODEL_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e87ba4", "#008300"]
const MAX_MODEL_SERIES = 6

type Metric = "cost" | "tokens"
type ChartKind = "area" | "bar"

export function useSpend(days: number, tool?: string) {
  return useQuery({
    queryKey: ["spend", days, tool ?? ""],
    queryFn: () => api.spend(days, tool),
    staleTime: 60_000,
  })
}

export function money(value: number, currency: string) {
  if (currency === "AIU") return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 3 })} AIU`
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" }).format(value)
}

function AiuNote() {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className="cursor-help underline decoration-dotted underline-offset-2">AIU</span>}
      />
      <TooltipContent className="max-w-60">
        AI Units: unidade de cobrança do GitHub Copilot. 1 AIU ≈ 1 AI credit = US$ 0,01.
      </TooltipContent>
    </Tooltip>
  )
}

export function Money({ value, currency }: { value: number; currency: string }) {
  if (currency !== "AIU") return <>{money(value, currency)}</>
  return (
    <>
      {value.toLocaleString("pt-BR", { maximumFractionDigits: 3 })} <AiuNote />
    </>
  )
}

export function tokens(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}

const fmtDay = (day: string) => day.slice(8, 10) + "/" + day.slice(5, 7)
const fmtAxisCost = (v: number) => (Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${Math.round(v)}`)

function duration(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours ? `${hours}h ${minutes}min` : `${minutes}min`
}

type Series = { key: string; label: string; color: string; currency: string; axis: "left" | "right" }

function buildSeries(tools: SpendTool[]): { rows: Record<string, number | string>[]; series: Series[] } {
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  if (active.length > 1) {
    const days = [...new Set(active.flatMap((t) => t.by_day.map((r) => r.day)))].sort()
    const rows = days.map((day) => {
      const row: Record<string, number | string> = { day }
      for (const tool of active) row[tool.id] = tool.by_day.find((r) => r.day === day)?.cost ?? 0
      return row
    })
    return {
      rows,
      series: active.map((tool) => ({
        key: tool.id,
        label: tool.label,
        color: TOOL_COLOR[tool.id] ?? "#888888",
        currency: tool.currency,
        axis: "left",
      })),
    }
  }
  const tool = active[0]
  if (!tool) return { rows: [], series: [] }
  const byCost = [...tool.by_model].sort((a, b) => b.cost - a.cost)
  const top = byCost.slice(0, MAX_MODEL_SERIES).map((r) => r.model)
  const rest = new Set(byCost.slice(MAX_MODEL_SERIES).map((r) => r.model))
  const perDay = new Map<string, Record<string, number>>()
  for (const row of tool.by_day_model) {
    const bucket = perDay.get(row.day) ?? {}
    const key = top.includes(row.model) ? row.model : "outros"
    bucket[key] = (bucket[key] ?? 0) + row.cost
    perDay.set(row.day, bucket)
  }
  if (![...perDay.values()].some((b) => b.outros)) rest.clear()
  const rows = [...perDay.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([day, bucket]) => ({ day, ...bucket }))
  const names = [...top, ...(rest.size ? ["outros"] : [])]
  return {
    rows,
    series: names.map((name, i) => ({
      key: name,
      label: name,
      color: MODEL_COLORS[i % MODEL_COLORS.length],
      currency: tool.currency,
      axis: "left",
    })),
  }
}

function buildTokenSeries(tools: SpendTool[]): { rows: Record<string, number | string>[]; series: Series[] } {
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  if (active.length > 1) {
    const days = [...new Set(active.flatMap((t) => t.by_day.map((r) => r.day)))].sort()
    const rows = days.map((day) => {
      const row: Record<string, number | string> = { day }
      for (const tool of active) row[tool.id] = tool.by_day.find((r) => r.day === day)?.total_tokens ?? 0
      return row
    })
    return {
      rows,
      series: active.map((tool) => ({
        key: tool.id,
        label: tool.label,
        color: TOOL_COLOR[tool.id] ?? "#888888",
        currency: tool.currency,
        axis: "left",
      })),
    }
  }
  const tool = active[0]
  if (!tool) return { rows: [], series: [] }
  const byTokens = [...tool.by_model].sort((a, b) => b.total_tokens - a.total_tokens)
  const top = byTokens.slice(0, MAX_MODEL_SERIES).map((r) => r.model)
  const rest = new Set(byTokens.slice(MAX_MODEL_SERIES).map((r) => r.model))
  const perDay = new Map<string, Record<string, number>>()
  for (const row of tool.by_day_model) {
    const bucket = perDay.get(row.day) ?? {}
    const key = top.includes(row.model) ? row.model : "outros"
    bucket[key] = (bucket[key] ?? 0) + row.total_tokens
    perDay.set(row.day, bucket)
  }
  if (![...perDay.values()].some((b) => b.outros)) rest.clear()
  const rows = [...perDay.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([day, bucket]) => ({ day, ...bucket }))
  const names = [...top, ...(rest.size ? ["outros"] : [])]
  return {
    rows,
    series: names.map((name, i) => ({
      key: name,
      label: name,
      color: MODEL_COLORS[i % MODEL_COLORS.length],
      currency: tool.currency,
      axis: "left",
    })),
  }
}

export function SpendTrend({
  tools,
  metric,
  kind,
  height = 240,
}: {
  tools: SpendTool[]
  metric: Metric
  kind: ChartKind
  height?: number
}) {
  const { rows, series } = useMemo(
    () => (metric === "cost" ? buildSeries(tools) : buildTokenSeries(tools)),
    [tools, metric],
  )
  const withAxis: Series[] = useMemo(() => {
    if (metric !== "cost") return series.map((s) => ({ ...s, axis: "left" }))
    const hasCopilot = series.some((s) => s.currency === "AIU")
    const hasUsd = series.some((s) => s.currency !== "AIU")
    if (!hasCopilot || !hasUsd) return series.map((s) => ({ ...s, axis: "left" }))
    return series.map((s) => ({ ...s, axis: s.currency === "AIU" ? "right" : "left" }))
  }, [series, metric])
  const [focus, setFocus] = useState<string | null>(null)
  const visible = focus && withAxis.some((s) => s.key === focus) ? withAxis.filter((s) => s.key === focus) : withAxis
  if (!rows.length || !visible.length) return null

  const config = Object.fromEntries(
    visible.map((s) => [s.key, { label: s.label, color: s.color }]),
  ) satisfies ChartConfig
  const formatValue = (value: unknown, name: unknown) => {
    const s = withAxis.find((x) => x.key === String(name))
    const formatted = metric === "cost" ? money(Number(value), s?.currency ?? "USD") : `${tokens(Number(value))} tokens`
    return (
      <div className="flex w-full items-center gap-2">
        <div className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: s?.color }} />
        <span className="text-muted-foreground">{s?.label ?? String(name)}</span>
        <span className="ml-auto pl-4 font-mono font-medium tabular-nums">{formatted}</span>
      </div>
    )
  }
  const tick = metric === "cost" ? fmtAxisCost : tokens
  const rightAxis = withAxis.some((s) => s.axis === "right")
  const ids = rightAxis ? undefined : "total"

  return (
    <div>
      <ChartContainer config={config} className="w-full" style={{ height }}>
        {kind === "area" ? (
          <AreaChart accessibilityLayer data={rows}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="day"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={fmtDay}
            />
            <YAxis yAxisId="left" tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => tick(v)} />
            {rightAxis && <YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} width={52} />}
            <ChartTooltip content={<ChartTooltipContent formatter={formatValue} />} />
            {visible.map((s) => (
              <Area
                key={s.key}
                yAxisId={s.axis}
                dataKey={s.key}
                name={s.key}
                type="monotone"
                fill={s.color}
                fillOpacity={0.35}
                stroke={s.color}
                strokeWidth={2}
                stackId={ids}
              />
            ))}
          </AreaChart>
        ) : (
          <BarChart accessibilityLayer data={rows}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="day"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={fmtDay}
            />
            <YAxis yAxisId="left" tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => tick(v)} />
            {rightAxis && <YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} width={52} />}
            <ChartTooltip content={<ChartTooltipContent formatter={formatValue} />} />
            {visible.map((s) => (
              <Bar
                key={s.key}
                yAxisId={s.axis}
                dataKey={s.key}
                name={s.key}
                fill={s.color}
                stackId={ids}
                maxBarSize={28}
              />
            ))}
          </BarChart>
        )}
      </ChartContainer>
      {withAxis.length > 1 && (
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 pt-3">
          {withAxis.map((s) => {
            const dimmed = focus !== null && focus !== s.key
            return (
              <button
                key={s.key}
                onClick={() => setFocus((f) => (f === s.key ? null : s.key))}
                title={focus === s.key ? "Mostrar todas" : `Filtrar por ${s.label}`}
                className="text-muted-foreground flex items-center gap-1.5 text-xs transition-opacity hover:opacity-100"
                style={{ opacity: dimmed ? 0.4 : 1 }}
              >
                <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ backgroundColor: s.color }} />
                {s.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <div className="text-muted-foreground text-[11px]">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  )
}

function Table({
  title,
  rows,
  name,
  currency,
}: {
  title: string
  rows: (SpendBucket & Record<string, string | number>)[]
  name: string
  currency: string
}) {
  if (!rows.length) return null
  return (
    <div>
      <h4 className="text-muted-foreground mb-1 text-[11px] font-medium tracking-wider uppercase">{title}</h4>
      <div className="border-border overflow-hidden rounded-md border">
        {rows.map((row) => (
          <div
            key={String(row[name])}
            className="border-border flex items-center gap-2 border-b px-2 py-1 text-xs last:border-0"
          >
            <span className="min-w-0 flex-1 truncate" title={String(row[name])}>
              {String(row[name])}
            </span>
            <span className="text-muted-foreground shrink-0">{tokens(row.total_tokens)}</span>
            <span className="w-24 shrink-0 text-right">
              <Money value={row.cost} currency={currency} />
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ToolCard({ tool, metric, kind }: { tool: SpendTool; metric: Metric; kind: ChartKind }) {
  return (
    <section className="border-border bg-card mb-4 rounded-lg border p-4">
      <div className="mb-3 flex items-center gap-2">
        <ToolIcon id={tool.id} className="size-4" />
        <h3 className="text-sm font-semibold">{tool.label}</h3>
        <span className="text-muted-foreground text-[11px]">
          {tool.currency === "AIU" ? <AiuNote /> : tool.currency}
        </span>
      </div>
      {!tool.available ? (
        <p className="text-muted-foreground text-xs">{tool.error ?? tool.note}</p>
      ) : tool.total.requests === 0 ? (
        <p className="text-muted-foreground text-xs">Nenhum uso no período. {tool.note}</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="custo" value={<Money value={tool.total.cost} currency={tool.currency} />} />
            <Stat label="tokens" value={tokens(tool.total.total_tokens)} />
            <Stat label="chamadas" value={String(tool.total.requests)} />
            <Stat label="tempo ativo" value={duration(tool.total.active_seconds)} />
          </div>
          <div className="mb-4">
            <SpendTrend tools={[tool]} metric={metric} kind={kind} height={220} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Table title="por modelo" rows={tool.by_model} name="model" currency={tool.currency} />
            <Table title="por projeto" rows={tool.by_project} name="project" currency={tool.currency} />
          </div>
          {tool.unknown_models.length > 0 && (
            <p className="text-muted-foreground mt-3 text-[11px]">
              Sem preço de tabela: {tool.unknown_models.join(", ")}. O custo desses modelos está zerado.
            </p>
          )}
          <p className="text-muted-foreground mt-3 text-[11px]">{tool.note}</p>
        </>
      )}
    </section>
  )
}

export function SpendChartCard({ tool }: { tool: string }) {
  const { data, isPending } = useSpend(30, tool)
  const row = data?.tools[tool]
  if (isPending) return <div className="bg-muted mb-5 h-44 animate-pulse rounded-lg" />
  if (!row || !row.available || row.total.requests === 0) return null
  return (
    <div className="border-border bg-card mb-5 rounded-lg border p-4">
      <div className="mb-2 flex flex-wrap items-center gap-3 text-sm">
        <span className="font-medium">Consumo · 30 dias</span>
        <span>
          <Money value={row.total.cost} currency={row.currency} />
        </span>
        <span className="text-muted-foreground">{tokens(row.total.total_tokens)} tokens</span>
        <Link to={`/consumo?tool=${tool}&days=30`} className="text-muted-foreground ml-auto text-xs hover:underline">
          ver detalhe
        </Link>
      </div>
      <SpendTrend tools={[row]} metric="cost" kind="area" height={180} />
    </div>
  )
}

function Toggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <Button
          key={opt.value}
          size="sm"
          variant={value === opt.value ? "secondary" : "outline"}
          className="rounded-full"
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  )
}

const OVERVIEW_PERIODS = [
  { days: 7, label: "7 dias" },
  { days: 30, label: "30 dias" },
  { days: 0, label: "Tudo" },
]

export function SpendOverviewCard() {
  const [days, setDays] = useState(30)
  const { data, isPending } = useSpend(days)
  const tools = data ? Object.values(data.tools) : []
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  if (isPending) return <div className="bg-muted h-40 animate-pulse rounded-lg" />
  if (!active.length) return null
  const usd = active.filter((t) => t.currency !== "AIU").reduce((sum, t) => sum + t.total.cost, 0)
  const aiu = active.filter((t) => t.currency === "AIU").reduce((sum, t) => sum + t.total.cost, 0)
  return (
    <div className="border-border overflow-hidden rounded-lg border">
      <div className="bg-card flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
        <span className="font-medium">Consumo · {OVERVIEW_PERIODS.find((p) => p.days === days)?.label}</span>
        <span>{money(usd, "USD")}</span>
        {aiu > 0 && (
          <span className="text-muted-foreground">
            <Money value={aiu} currency="AIU" />
          </span>
        )}
        <span className="ml-auto flex items-center gap-1.5">
          {OVERVIEW_PERIODS.map((period) => (
            <Button
              key={period.days}
              size="sm"
              variant={days === period.days ? "secondary" : "outline"}
              className="h-6 rounded-full px-2.5 text-xs"
              onClick={() => setDays(period.days)}
            >
              {period.label}
            </Button>
          ))}
          <Link to="/consumo" className="text-muted-foreground ml-1 text-xs hover:underline">
            ver Consumo
          </Link>
        </span>
      </div>
      <div className="bg-card px-2 pb-2">
        <SpendTrend tools={active} metric="cost" kind="area" height={180} />
      </div>
    </div>
  )
}

export default function SpendView() {
  const [params, setParams] = useSearchParams()
  const days = Number(params.get("days") ?? 30)
  const tool = params.get("tool") || undefined
  const selected = tool && TOOLS.includes(tool) ? tool : undefined
  const [metric, setMetric] = useState<Metric>("cost")
  const [kind, setKind] = useState<ChartKind>("area")
  const { data, isPending, isError } = useSpend(Number.isFinite(days) ? days : 30, selected)
  const set = (next: { days?: number; tool?: string }) =>
    setParams(
      (prev) => {
        const out = new URLSearchParams(prev)
        if (next.days != null) out.set("days", String(next.days))
        if (next.tool === "") out.delete("tool")
        else if (next.tool) out.set("tool", next.tool)
        return out
      },
      { replace: true },
    )

  const tools = data ? Object.values(data.tools) : []
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  return (
    <div>
      <h2 className="text-lg font-semibold">Consumo</h2>
      <p className="text-muted-foreground mb-4 text-sm">
        Tokens e custo lidos dos logs locais. A primeira leitura do período pode levar alguns segundos.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        {PERIODS.map((period) => (
          <Button
            key={period.days}
            size="sm"
            variant={days === period.days ? "secondary" : "outline"}
            className="rounded-full"
            onClick={() => set({ days: period.days })}
          >
            {period.label}
          </Button>
        ))}
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={!selected ? "secondary" : "outline"}
          className="rounded-full"
          onClick={() => set({ tool: "" })}
        >
          Todas
        </Button>
        {TOOLS.map((id) => (
          <Button
            key={id}
            size="sm"
            variant={selected === id ? "secondary" : "outline"}
            className="rounded-full"
            onClick={() => set({ tool: id })}
          >
            <ToolIcon id={id} className="size-3.5" />
            {id}
          </Button>
        ))}
      </div>
      <div className="mb-5 flex flex-wrap gap-4">
        <Toggle
          value={metric}
          onChange={setMetric}
          options={[
            { value: "cost", label: "Custo" },
            { value: "tokens", label: "Tokens" },
          ]}
        />
        <Toggle
          value={kind}
          onChange={setKind}
          options={[
            { value: "area", label: "Área" },
            { value: "bar", label: "Barra" },
          ]}
        />
      </div>
      {isPending ? (
        <ViewSkeleton rows={4} />
      ) : isError ? (
        <p className="text-muted-foreground text-sm">Não foi possível ler o consumo local.</p>
      ) : (
        <>
          {!selected && active.length > 1 && (
            <section className="border-border bg-card mb-4 rounded-lg border p-4">
              <h3 className="mb-3 text-sm font-semibold">
                Todas as IAs · {metric === "cost" ? "custo por dia" : "tokens por dia"}
              </h3>
              <SpendTrend tools={active} metric={metric} kind={kind} height={260} />
              {metric === "cost" && active.some((t) => t.currency === "AIU") && (
                <p className="text-muted-foreground mt-2 text-[11px]">
                  Copilot em AIU no eixo da direita; as demais em USD no eixo da esquerda.
                </p>
              )}
            </section>
          )}
          {tools.map((row) => (
            <ToolCard key={row.id} tool={row} metric={metric} kind={kind} />
          ))}
        </>
      )}
    </div>
  )
}
