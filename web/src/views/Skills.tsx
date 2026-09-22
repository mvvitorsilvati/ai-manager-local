import { useQuery } from "@tanstack/react-query"
import { Trophy, Zap } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { Bar, BarChart, LabelList, XAxis, YAxis } from "recharts"

import { ViewSkeleton } from "@/components/bits"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { useCatalog } from "@/hooks/useCatalog"
import { api, type SkillRow } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { tokens } from "@/views/Spend"

export function useSkillUsage(days: number, tool?: string, enabled = true) {
  return useQuery({
    queryKey: ["skill-usage", days, tool ?? ""],
    queryFn: () => api.skillUsage(days, tool),
    staleTime: 60_000,
    enabled,
  })
}

const MEDALS = ["#F5C518", "#C0C0C0", "#CD7F32"]

export function TopSkillBadge({ skill, rank, window }: { skill: string; rank: number; window: string }) {
  const { t } = useI18n()
  if (rank < 0) return null
  return (
    <Badge
      variant="secondary"
      className="border-amber-400/40 font-normal text-amber-300"
      title={t("skills.topBadge", { skill, n: rank + 1, window })}
    >
      <Trophy className="size-3" style={rank < MEDALS.length ? { color: MEDALS[rank] } : undefined} />
      Top {rank + 1}
    </Badge>
  )
}

export function SkillTable({ rows, showTools, days = 7 }: { rows: SkillRow[]; showTools: boolean; days?: number }) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const { data: catalog } = useCatalog()
  const targetOf = (name: string) => {
    const needle = name.toLowerCase()
    const candidates = (catalog?.skills ?? []).filter(
      (s) => s.skill_name.toLowerCase() === needle || s.r.toLowerCase().endsWith(`/${needle}/skill.md`),
    )
    // cópias de backup têm o mesmo skill_name: prefere o arquivo canônico (pasta com o nome exato, fora de backups)
    const live = candidates.filter((s) => !s.r.toLowerCase().includes("backup"))
    return live.find((s) => s.r.toLowerCase().endsWith(`/${needle}/skill.md`)) ?? live[0] ?? candidates[0]
  }
  if (!rows.length) return null
  return (
    <div className="border-border overflow-hidden rounded-md border">
      {rows.map((row, i) => (
        <div key={row.skill} className="border-border flex items-center gap-2 border-b px-2 py-1 text-xs last:border-0">
          {i < MEDALS.length ? (
            <span className="flex w-6 shrink-0 justify-end" title={`#${i + 1} skill mais usada`}>
              <Trophy className="size-3.5" style={{ color: MEDALS[i] }} />
            </span>
          ) : (
            <span className="text-muted-foreground w-6 shrink-0 text-right">{i + 1}</span>
          )}
          <Zap className="text-muted-foreground size-3 shrink-0" />
          <span className="flex min-w-0 flex-1 items-center gap-1.5">
            {(() => {
              const target = targetOf(row.skill)
              return target ? (
                <button
                  onClick={() =>
                    navigate(`/f?s=${encodeURIComponent(target.s)}&r=${encodeURIComponent(target.r)}&skilldays=${days}`)
                  }
                  className="min-w-0 shrink truncate text-left font-mono hover:underline"
                  title={t("skills.viewFile", { skill: row.skill })}
                >
                  {row.skill}
                </button>
              ) : (
                <span className="min-w-0 shrink truncate font-mono" title={row.skill}>
                  {row.skill}
                </span>
              )
            })()}
            {!targetOf(row.skill) ? (
              <Badge
                variant="outline"
                className="shrink-0 border-zinc-500/40 px-1 py-0 text-[9px] font-normal text-zinc-400"
                title={t("skills.noFileTitle")}
              >
                {t("skills.noFile")}
              </Badge>
            ) : null}
            {row.by_origin.user > 0 && (
              <Badge
                variant="outline"
                className="shrink-0 border-sky-400/40 px-1 py-0 text-[9px] font-normal text-sky-400"
                title={t("skills.userTitle", { n: row.by_origin.user })}
              >
                {t("skills.user")}
              </Badge>
            )}
            {row.by_origin.model > 0 && (
              <Badge
                variant="outline"
                className="shrink-0 border-violet-400/40 px-1 py-0 text-[9px] font-normal text-violet-400"
                title={t("skills.modelTitle", { n: row.by_origin.model })}
              >
                {t("skills.model")}
              </Badge>
            )}
          </span>
          {showTools && row.tools ? (
            <span className="flex shrink-0 items-center gap-1.5">
              {Object.entries(row.tools).map(([id, n]) => (
                <span key={id} title={`${id}: ${n}`} className="flex items-center gap-1">
                  <ToolIcon id={id} className="size-3" />
                  <span className="text-muted-foreground">{n}</span>
                </span>
              ))}
            </span>
          ) : null}
          <span className="text-muted-foreground w-16 shrink-0 text-right">{row.invocations}×</span>
          <span className="text-muted-foreground w-20 shrink-0 text-right">{tokens(row.context_tokens)}</span>
        </div>
      ))}
    </div>
  )
}

export function SkillsTop({ days = 7 }: { days?: number }) {
  const { t } = useI18n()
  const { data, isPending } = useSkillUsage(days)
  const top = data?.top ?? []
  if (isPending) return <div className="bg-muted h-40 animate-pulse rounded-lg" />
  if (!top.length) return null
  return (
    <div className="border-border overflow-hidden rounded-lg border">
      <div className="bg-card px-2 pt-2">
        <SkillTable rows={top} showTools />
      </div>
      <div className="bg-card flex justify-end px-3 py-2">
        <Link to="/consumo" className="text-muted-foreground text-xs hover:underline">
          {t("spend.viewUsage")}
        </Link>
      </div>
    </div>
  )
}

const TOKEN_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e87ba4", "#008300"]

function SkillsTokenBars({ rows }: { rows: SkillRow[] }) {
  const { t } = useI18n()
  const top = [...rows].sort((a, b) => b.context_tokens - a.context_tokens).slice(0, 10)
  if (!top.length) return null
  const data = top.map((row, i) => ({
    skill: row.skill.length > 18 ? `${row.skill.slice(0, 17)}…` : row.skill,
    full: row.skill,
    tokens: row.context_tokens,
    fill: TOKEN_COLORS[i % TOKEN_COLORS.length],
  }))
  const config = { tokens: { label: t("spend.statTokens") } } satisfies ChartConfig
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("skills.tokensTitle")}</CardTitle>
        <CardDescription>{t("skills.tokensSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="h-[320px] w-full">
          <BarChart accessibilityLayer data={data} layout="vertical" margin={{ left: 0, right: 12 }}>
            <YAxis
              dataKey="skill"
              type="category"
              tickLine={false}
              tickMargin={10}
              axisLine={false}
              width={140}
              tick={{ fontSize: 11 }}
            />
            <XAxis dataKey="tokens" type="number" hide />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.full ?? ""}
                  formatter={(value) => `${tokens(Number(value))} ${t("spend.statTokens")}`}
                />
              }
            />
            <Bar dataKey="tokens" radius={5}>
              <LabelList
                dataKey="tokens"
                position="right"
                formatter={(value: unknown) => tokens(Number(value))}
                fontSize={11}
                fill="var(--muted-foreground)"
              />
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

export default function SpendSkills({ days, tool }: { days: number; tool?: string }) {
  const { t } = useI18n()
  const { data, isPending, isError } = useSkillUsage(days, tool)
  if (isPending) return <ViewSkeleton rows={3} />
  if (isError || !data || !data.top.length) return null
  return (
    <section className="border-border bg-card mb-4 rounded-lg border p-4">
      <h3 className="mb-1 text-sm font-semibold">
        {t("skills.top")} — {t("skills.topGlobal")}
      </h3>
      <p className="text-muted-foreground mb-3 text-[11px]">{t("skills.note")}</p>
      <div className="grid items-start gap-4 xl:grid-cols-2">
        <SkillTable rows={data.top} showTools />
        <SkillsTokenBars rows={data.top} />
      </div>
    </section>
  )
}
