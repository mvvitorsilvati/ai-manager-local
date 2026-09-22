import { useQuery } from "@tanstack/react-query"
import { ChartArea, ChartBar, ChartBarStacked, TrendingDown, TrendingUp } from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Label, Pie, PieChart, XAxis, YAxis } from "recharts"

import { ViewSkeleton } from "@/components/bits"
import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api, type SpendBucket, type SpendTool } from "@/lib/api"
import { getLang, getLocale, useI18n } from "@/lib/i18n"
import SpendSkills, { SkillTable, useSkillUsage } from "@/views/Skills"

const PERIODS: { days: number; labelKey: "spend.p7" | "spend.p30" | "spend.pAll" }[] = [
  { days: 7, labelKey: "spend.p7" },
  { days: 30, labelKey: "spend.p30" },
  { days: 0, labelKey: "spend.pAll" },
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
type ChartKind = "area" | "bar" | "stacked"

export function useSpend(days: number, tool?: string) {
  return useQuery({
    queryKey: ["spend", days, tool ?? ""],
    queryFn: () => api.spend(days, tool),
    staleTime: 60_000,
  })
}

export function money(value: number, currency: string) {
  if (currency === "AIU") return `${value.toLocaleString(getLocale(), { maximumFractionDigits: 3 })} AIU`
  return new Intl.NumberFormat(getLocale(), { style: "currency", currency: "USD" }).format(value)
}

function AiuNote() {
  const { t } = useI18n()
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className="cursor-help underline decoration-dotted underline-offset-2">AIU</span>}
      />
      <TooltipContent className="max-w-60">{t("spend.aiuNote")}</TooltipContent>
    </Tooltip>
  )
}

export function Money({ value, currency }: { value: number; currency: string }) {
  if (currency !== "AIU") return <>{money(value, currency)}</>
  return (
    <>
      {value.toLocaleString(getLocale(), { maximumFractionDigits: 3 })} <AiuNote />
    </>
  )
}

function TooltipRow({ color, label, formatted }: { color?: string; label: string; formatted: string }) {
  return (
    <div className="flex w-full items-center gap-2">
      <div className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: color }} />
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-auto pl-4 font-mono font-medium tabular-nums">{formatted}</span>
    </div>
  )
}

export function tokens(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}

const fmtDay = (day: string) =>
  getLang() === "pt" ? day.slice(8, 10) + "/" + day.slice(5, 7) : day.slice(5, 7) + "/" + day.slice(8, 10)
const fmtAxisCost = (v: number) => (Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${Math.round(v)}`)

function duration(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours ? `${hours}h ${minutes}min` : `${minutes}min`
}

type Series = { key: string; label: string; color: string; currency: string; axis: "left" | "right" }

function buildSeries(
  tools: SpendTool[],
  otherLabel: string,
): { rows: Record<string, number | string>[]; series: Series[] } {
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
    const key = top.includes(row.model) ? row.model : otherLabel
    bucket[key] = (bucket[key] ?? 0) + row.cost
    perDay.set(row.day, bucket)
  }
  if (![...perDay.values()].some((b) => b[otherLabel])) rest.clear()
  const rows = [...perDay.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([day, bucket]) => ({ day, ...bucket }))
  const names = [...top, ...(rest.size ? [otherLabel] : [])]
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

function buildTokenSeries(
  tools: SpendTool[],
  otherLabel: string,
): { rows: Record<string, number | string>[]; series: Series[] } {
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
    const key = top.includes(row.model) ? row.model : otherLabel
    bucket[key] = (bucket[key] ?? 0) + row.total_tokens
    perDay.set(row.day, bucket)
  }
  if (![...perDay.values()].some((b) => b[otherLabel])) rest.clear()
  const rows = [...perDay.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([day, bucket]) => ({ day, ...bucket }))
  const names = [...top, ...(rest.size ? [otherLabel] : [])]
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

const KIND_META: {
  value: ChartKind
  labelKey: "spend.area" | "spend.bar" | "spend.stacked"
  Icon: typeof ChartArea
}[] = [
  { value: "area", labelKey: "spend.area", Icon: ChartArea },
  { value: "bar", labelKey: "spend.bar", Icon: ChartBar },
  { value: "stacked", labelKey: "spend.stacked", Icon: ChartBarStacked },
]

function KindToggle({ value, onChange }: { value: ChartKind; onChange: (v: ChartKind) => void }) {
  const { t } = useI18n()
  return (
    <div className="flex items-center gap-1">
      {KIND_META.map(({ value: v, labelKey, Icon }) => (
        <Button
          key={v}
          size="icon-sm"
          variant={value === v ? "secondary" : "ghost"}
          title={t(labelKey)}
          aria-label={t(labelKey)}
          onClick={() => onChange(v)}
        >
          <Icon className="size-4" />
        </Button>
      ))}
    </div>
  )
}

export function SpendTrend({
  tools,
  metric,
  height = 240,
  toggle = true,
}: {
  tools: SpendTool[]
  metric: Metric
  height?: number
  toggle?: boolean
}) {
  const [kind, setKind] = useState<ChartKind>("area")
  const { t } = useI18n()
  const { rows, series } = useMemo(
    () => (metric === "cost" ? buildSeries(tools, t("spend.other")) : buildTokenSeries(tools, t("spend.other"))),
    [tools, metric, t],
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
    return (
      <TooltipRow
        color={s?.color}
        label={s?.label ?? String(name)}
        formatted={
          metric === "cost"
            ? money(Number(value), s?.currency ?? "USD")
            : `${tokens(Number(value))} ${t("spend.statTokens")}`
        }
      />
    )
  }
  const tick = metric === "cost" ? fmtAxisCost : tokens
  const rightAxis = withAxis.some((s) => s.axis === "right")
  const ids = rightAxis ? undefined : "total"
  const stacking = kind === "stacked" && ids !== undefined
  const barRadius = (i: number): number | [number, number, number, number] => {
    if (!stacking) return 0
    if (visible.length === 1) return 4
    if (i === 0) return [0, 0, 4, 4]
    if (i === visible.length - 1) return [4, 4, 0, 0]
    return 0
  }

  return (
    <div>
      {toggle && (
        <div className="mb-1 flex justify-end">
          <KindToggle value={kind} onChange={setKind} />
        </div>
      )}
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
            {visible.map((s, i) => (
              <Bar
                key={s.key}
                yAxisId={s.axis}
                dataKey={s.key}
                name={s.key}
                fill={s.color}
                stackId={stacking ? ids : undefined}
                radius={barRadius(i)}
                maxBarSize={32}
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

export function SpendDonut({
  tools,
  metric,
  periodLabel,
}: {
  tools: SpendTool[]
  metric: Metric
  periodLabel: string
}) {
  const { t } = useI18n()
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  const usd = active.filter((t) => t.currency !== "AIU")
  const aiu = active.filter((t) => t.currency === "AIU")
  const splitAiu = metric === "cost" && aiu.length > 0 && usd.length > 0
  const main = splitAiu ? usd : active
  if (!main.length) return null
  const unit = metric === "cost" ? (main[0]?.currency ?? "USD") : t("spend.statTokens")
  const slices = main.map((t) => ({
    tool: t.id,
    label: t.label,
    value: metric === "cost" ? t.total.cost : t.total.total_tokens,
    fill: TOOL_COLOR[t.id] ?? "#888888",
  }))
  const total = slices.reduce((sum, r) => sum + r.value, 0)
  const centerValue =
    metric === "cost"
      ? unit === "AIU"
        ? total.toLocaleString(getLocale(), { maximumFractionDigits: 3 })
        : new Intl.NumberFormat(getLocale(), { style: "currency", currency: "USD" }).format(total)
      : tokens(total)
  const config = Object.fromEntries(
    slices.map((r) => [r.tool, { label: r.label, color: r.fill }]),
  ) satisfies ChartConfig
  const formatSlice = (value: unknown, name: unknown) => {
    const row = slices.find((r) => r.tool === String(name))
    return (
      <TooltipRow
        color={row?.fill}
        label={row?.label ?? String(name)}
        formatted={metric === "cost" ? money(Number(value), unit) : `${tokens(Number(value))} ${t("spend.statTokens")}`}
      />
    )
  }
  return (
    <Card className="flex flex-col">
      <CardHeader className="items-center pb-0">
        <CardTitle>{metric === "cost" ? t("spend.donutCost") : t("spend.donutTokens")}</CardTitle>
        <CardDescription>{periodLabel}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 pb-0">
        <ChartContainer config={config} className="mx-auto aspect-square max-h-[250px]">
          <PieChart>
            <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel formatter={formatSlice} />} />
            <Pie data={slices} dataKey="value" nameKey="tool" innerRadius={60} strokeWidth={5}>
              <Label
                content={({ viewBox }) => {
                  if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                    return (
                      <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                        <tspan x={viewBox.cx} y={viewBox.cy} className="fill-foreground text-3xl font-bold">
                          {centerValue}
                        </tspan>
                        <tspan x={viewBox.cx} y={(viewBox.cy || 0) + 24} className="fill-muted-foreground">
                          {unit}
                        </tspan>
                      </text>
                    )
                  }
                }}
              />
            </Pie>
          </PieChart>
        </ChartContainer>
      </CardContent>
      {splitAiu && (
        <CardFooter className="flex-col items-center gap-1 text-sm">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ backgroundColor: TOOL_COLOR.copilot }} />
            Copilot · <Money value={aiu.reduce((sum, t) => sum + t.total.cost, 0)} currency="AIU" />
          </div>
          <div className="text-muted-foreground text-xs">{t("spend.aiuOutside")}</div>
        </CardFooter>
      )}
    </Card>
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
        {rows.map((row, i) => (
          <div
            key={String(row[name])}
            className="border-border flex items-center gap-2 border-b px-2 py-1 text-xs last:border-0"
          >
            <span className="text-muted-foreground w-6 shrink-0 text-right">{i + 1}</span>
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

export function ToolCard({
  id,
  initialDays = 7,
  detailLink = false,
}: {
  id: string
  initialDays?: number
  detailLink?: boolean
}) {
  const [metric, setMetric] = useState<Metric>("cost")
  const [days, setDays] = useState(initialDays)
  const { data, isPending } = useSpend(days, id)
  const tool = data?.tools[id]
  if (isPending && !tool) return <ViewSkeleton rows={3} />
  if (!tool) return null
  return (
    <ToolCardBody
      tool={tool}
      metric={metric}
      onMetric={setMetric}
      days={days}
      onDays={setDays}
      detailLink={detailLink}
    />
  )
}

function ToolSkills({ id, days }: { id: string; days: number }) {
  const { data } = useSkillUsage(days, id)
  const { t } = useI18n()
  const rows = data?.tools[id]?.rows ?? []
  if (!rows.length) return null
  return (
    <div className="mt-4">
      <h4 className="text-muted-foreground mb-1 text-[11px] font-medium tracking-wider uppercase">{t("skills.top")}</h4>
      <SkillTable rows={rows} showTools={false} />
    </div>
  )
}

function ToolCardBody({
  tool,
  metric,
  onMetric,
  days,
  onDays,
  detailLink,
}: {
  tool: SpendTool
  metric: Metric
  onMetric: (v: Metric) => void
  days: number
  onDays: (v: number) => void
  detailLink: boolean
}) {
  const { t } = useI18n()
  const pick = (row: { cost: number; total_tokens: number }) => (metric === "cost" ? row.cost : row.total_tokens)
  const peak = tool.by_day.length ? tool.by_day.reduce((a, b) => (pick(b) > pick(a) ? b : a)) : null
  const half = Math.floor(tool.by_day.length / 2)
  const sum = (rows: typeof tool.by_day) => rows.reduce((s, r) => s + pick(r), 0)
  const trendingUp = tool.by_day.length > 1 && sum(tool.by_day.slice(half)) >= sum(tool.by_day.slice(0, half))
  const TrendIcon = trendingUp ? TrendingUp : TrendingDown
  const range =
    tool.by_day.length > 1
      ? `${fmtDay(tool.by_day[0].day)} – ${fmtDay(tool.by_day[tool.by_day.length - 1].day)}`
      : tool.span && `${fmtDay(tool.span.from.slice(0, 10))} – ${fmtDay(tool.span.to.slice(0, 10))}`
  return (
    <section className="border-border bg-card mb-4 rounded-lg border p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <ToolIcon id={tool.id} className="size-4" />
        <h3 className="text-sm font-semibold">{tool.label}</h3>
        <span className="text-muted-foreground text-[11px]">
          {tool.currency === "AIU" ? <AiuNote /> : tool.currency}
        </span>
        <span className="ml-auto flex items-center gap-2">
          <MetricToggle value={metric} onChange={onMetric} />
          {detailLink && (
            <Link
              to={`/consumo?tool=${tool.id}&days=${days}`}
              className="text-muted-foreground text-xs hover:underline"
            >
              {t("spend.detail")}
            </Link>
          )}
        </span>
      </div>
      <div className="mb-3 flex items-center gap-1.5">
        <span className="ml-auto flex items-center gap-1.5">
          {OVERVIEW_PERIODS.map((period) => (
            <Button
              key={period.days}
              size="sm"
              variant={days === period.days ? "secondary" : "outline"}
              className="h-6 rounded-full px-2.5 text-xs"
              onClick={() => onDays(period.days)}
            >
              {t(period.labelKey)}
            </Button>
          ))}
        </span>
      </div>
      {!tool.available ? (
        <p className="text-muted-foreground text-xs">{tool.error ?? tool.note}</p>
      ) : tool.total.requests === 0 ? (
        <p className="text-muted-foreground text-xs">
          {t("spend.noUsage")} {tool.note}
        </p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t("spend.statCost")} value={<Money value={tool.total.cost} currency={tool.currency} />} />
            <Stat label={t("spend.statTokens")} value={tokens(tool.total.total_tokens)} />
            <Stat label={t("spend.statCalls")} value={String(tool.total.requests)} />
            <Stat label={t("spend.statActive")} value={duration(tool.total.active_seconds)} />
          </div>
          <Card className="mb-4">
            <CardHeader>
              <CardTitle>{metric === "cost" ? t("spend.dayCost") : t("spend.dayTokens")}</CardTitle>
              {range && <CardDescription>{range}</CardDescription>}
            </CardHeader>
            <CardContent>
              <SpendTrend tools={[tool]} metric={metric} height={220} />
            </CardContent>
            {peak && (
              <CardFooter className="flex-col items-start gap-1 text-sm">
                <div className="flex items-center gap-2 leading-none font-medium">
                  {t("spend.peak", {
                    day: fmtDay(peak.day),
                    value:
                      metric === "cost"
                        ? money(peak.cost, tool.currency)
                        : `${tokens(peak.total_tokens)} ${t("spend.statTokens")}`,
                  })}{" "}
                  <TrendIcon className="size-4" />
                </div>
                <div className="text-muted-foreground leading-none">
                  {tool.by_day.length > 1 ? t(trendingUp ? "spend.up" : "spend.down") : t("spend.oneDay")}
                </div>
              </CardFooter>
            )}
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Table title={t("spend.byModel")} rows={tool.by_model} name="model" currency={tool.currency} />
            <Table title={t("spend.byProject")} rows={tool.by_project} name="project" currency={tool.currency} />
          </div>
          <ToolSkills id={tool.id} days={days} />
          {tool.unknown_models.length > 0 && (
            <p className="text-muted-foreground mt-3 text-[11px]">
              {t("spend.unknown", { models: tool.unknown_models.join(", ") })}
            </p>
          )}
          <p className="text-muted-foreground mt-3 text-[11px]">{tool.note}</p>
        </>
      )}
    </section>
  )
}

export function ToolSection({ tool }: { tool: string }) {
  return (
    <div className="mb-5">
      <ToolCard id={tool} detailLink />
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

export function MetricToggle({ value, onChange }: { value: Metric; onChange: (v: Metric) => void }) {
  const { t } = useI18n()
  return (
    <Toggle
      value={value}
      onChange={onChange}
      options={[
        { value: "cost", label: t("spend.cost") },
        { value: "tokens", label: t("spend.tokens") },
      ]}
    />
  )
}

const OVERVIEW_PERIODS: { days: number; labelKey: "spend.p7" | "spend.p30" | "spend.pAll" }[] = [
  { days: 7, labelKey: "spend.p7" },
  { days: 30, labelKey: "spend.p30" },
  { days: 0, labelKey: "spend.pAll" },
]

export function SpendOverviewCard() {
  const [days, setDays] = useState(7)
  const [metric, setMetric] = useState<Metric>("cost")
  const { t } = useI18n()
  const { data, isPending } = useSpend(days)
  const tools = data ? Object.values(data.tools) : []
  const active = tools.filter((t) => t.available && t.total.requests > 0)
  if (isPending) return <div className="bg-muted h-40 animate-pulse rounded-lg" />
  if (!active.length) return null
  const usd = active.filter((t) => t.currency !== "AIU").reduce((sum, t) => sum + t.total.cost, 0)
  const aiu = active.filter((t) => t.currency === "AIU").reduce((sum, t) => sum + t.total.cost, 0)
  const totalTokens = active.reduce((sum, t) => sum + t.total.total_tokens, 0)
  return (
    <div className="border-border overflow-hidden rounded-lg border">
      <div className="bg-card flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
        <span className="font-medium">
          {t("spend.strip", { period: t(OVERVIEW_PERIODS.find((p) => p.days === days)?.labelKey ?? "spend.p7") })}
        </span>
        {metric === "cost" ? (
          <>
            <span>{money(usd, "USD")}</span>
            {aiu > 0 && (
              <span className="text-muted-foreground">
                <Money value={aiu} currency="AIU" />
              </span>
            )}
          </>
        ) : (
          <span>
            {tokens(totalTokens)} {t("spend.statTokens")}
          </span>
        )}
        <Link to="/consumo" className="text-muted-foreground ml-auto text-xs hover:underline">
          {t("spend.viewUsage")}
        </Link>
      </div>
      <div className="bg-card flex flex-wrap items-center gap-2 px-3 pb-2">
        <MetricToggle value={metric} onChange={setMetric} />
        <span className="ml-auto flex items-center gap-1.5">
          {OVERVIEW_PERIODS.map((period) => (
            <Button
              key={period.days}
              size="sm"
              variant={days === period.days ? "secondary" : "outline"}
              className="h-6 rounded-full px-2.5 text-xs"
              onClick={() => setDays(period.days)}
            >
              {t(period.labelKey)}
            </Button>
          ))}
        </span>
      </div>
      <div className="bg-card px-2 pb-2">
        <SpendTrend tools={active} metric={metric} height={180} />
      </div>
    </div>
  )
}

export default function SpendView() {
  const [params, setParams] = useSearchParams()
  const days = Number(params.get("days") ?? 7)
  const tool = params.get("tool") || undefined
  const selected = tool && TOOLS.includes(tool) ? tool : undefined
  const [metric, setMetric] = useState<Metric>("cost")
  const { t } = useI18n()
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
  const period = Number.isFinite(days) ? days : 30
  return (
    <div>
      <h2 className="text-lg font-semibold">{t("spend.title")}</h2>
      <p className="text-muted-foreground mb-4 text-sm">{t("spend.subtitle")}</p>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={!selected ? "secondary" : "outline"}
              className="rounded-full"
              onClick={() => set({ tool: "" })}
            >
              {t("spend.all")}
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
          <MetricToggle value={metric} onChange={setMetric} />
        </div>
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((period) => (
            <Button
              key={period.days}
              size="sm"
              variant={days === period.days ? "secondary" : "outline"}
              className="rounded-full"
              onClick={() => set({ days: period.days })}
            >
              {t(period.labelKey)}
            </Button>
          ))}
        </div>
      </div>
      {isPending ? (
        <ViewSkeleton rows={4} />
      ) : isError ? (
        <p className="text-muted-foreground text-sm">{t("spend.loadError")}</p>
      ) : (
        <>
          {!selected && active.length > 1 && (
            <div className="mb-4 grid gap-4 xl:grid-cols-[1fr_320px]">
              <section className="border-border bg-card rounded-lg border p-4">
                <h3 className="mb-3 text-sm font-semibold">
                  {metric === "cost" ? t("spend.allCost") : t("spend.allTokens")}
                </h3>
                <SpendTrend tools={active} metric={metric} height={260} />
                {metric === "cost" && active.some((t) => t.currency === "AIU") && (
                  <p className="text-muted-foreground mt-2 text-[11px]">{t("spend.aiuAxis")}</p>
                )}
              </section>
              <SpendDonut
                tools={active}
                metric={metric}
                periodLabel={t(PERIODS.find((p) => p.days === days)?.labelKey ?? "spend.p7")}
              />
            </div>
          )}
          <SpendSkills days={period} tool={selected} />
          {selected ? (
            <ToolCard key={`${selected}-${period}`} id={selected} initialDays={period} />
          ) : (
            TOOLS.map((id) => <ToolCard key={`${id}-${period}`} id={id} initialDays={period} />)
          )}
        </>
      )}
    </div>
  )
}
