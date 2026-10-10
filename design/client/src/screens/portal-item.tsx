/*
 * بندٌ واحد من المهامّ أو المهارات في كل شاشة: لا تمرير ولا نصٌّ مقصوص، وتحته سطر
 * مصدره. «السابق» و«التالي» في موضعيهما من كل بند، والموضع في قوس المكوث.
 * «اسأل سيمبول عنها» ينقل إلى المساعد بالبند سياقاً، ولا يرسل شيئاً.
 */
import * as React from "react"
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react"

import { DwellArc } from "@/components/brand/dwell-arc"
import { SourceLine } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, Step, TopBar } from "@/components/frame/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { MODE } from "@/lib/labels"
import { loadPortal } from "@/lib/portal"
import { go } from "@/lib/router"
import { getState, nextNav, useStore } from "@/lib/store"

export function PortalItem({ kind, position }: { kind: "tasks" | "skills"; position: number }) {
  const portal = useStore((s) => s.portal)

  React.useEffect(() => {
    const nav = nextNav()
    void loadPortal().then((loaded) => {
      if (nav !== getState().nav) return
      if (!loaded) {
        go("#/", { replace: true })
        return
      }
      const n = Math.min(Math.max(1, position), loaded[kind].length)
      if (n !== position) go(`#/${kind}/${n}`, { replace: true })
    })
  }, [kind, position])

  const items = portal ? portal[kind] : []
  const item = items[position - 1]
  const tasks = kind === "tasks"
  const mode = tasks && item?.mode ? MODE[item.mode] : null

  return (
    <Screen name="portal-item">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/")}>
            رجوع
          </Button>
        }
        stepId="portal-item-position"
        step={
          item ? (
            <Step arc={<DwellArc value={position} total={items.length} />}>
              {tasks ? "المهمة" : "المهارة"} {position} من {items.length}
            </Step>
          ) : null
        }
      />
      <Content>
        <h2 tabIndex={-1} id="portal-item-heading" className="font-sans text-small font-semibold text-muted-foreground">
          {portal ? (tasks ? `مهامّ ${portal.name}` : `مهارات ${portal.name}`) : ""}
        </h2>
        <Card className="gap-3">
          <p id="portal-item-text" className="title text-title font-bold leading-snug text-heading">
            {item?.text ?? ""}
          </p>
          <p id="portal-item-note" className="line" hidden={!item?.note}>
            {item?.note ?? ""}
          </p>
          {mode ? (
            <Badge
              id="portal-item-mode"
              data-mode={item?.mode}
              variant={mode.tone}
              icon={mode.icon}
              className="badge whitespace-normal"
            >
              {mode.label}
            </Badge>
          ) : null}
        </Card>
        <SourceLine id="portal-item-source">{portal ? portal.sources[kind] : ""}</SourceLine>
        <Button
          id="portal-item-ask"
          icon={Sparkles}
          className="spaced w-full flex-none justify-start"
          onClick={() => go(`#/assistant/${kind}/${position}`)}
        >
          اسأل سيمبول عنها
        </Button>
      </Content>
      <BottomBar
        start={
          <Button
            id="portal-item-previous"
            icon={ChevronRight}
            reserved={position <= 1}
            onClick={() => go(`#/${kind}/${position - 1}`)}
          >
            السابق
          </Button>
        }
        end={
          <Button
            id="portal-item-next"
            variant="secondary"
            iconEnd={ChevronLeft}
            reserved={position >= items.length}
            onClick={() => go(`#/${kind}/${position + 1}`)}
          >
            التالي
          </Button>
        }
      />
    </Screen>
  )
}
