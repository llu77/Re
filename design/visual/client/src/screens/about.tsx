/* عن المهنة: تعريفها مترجماً عن مصدره، وسطر المصدر تحته. خانة الأداة في الرئيسية لبوابةٍ بلا أداة. */
import * as React from "react"
import { ChevronRight } from "lucide-react"

import { SourceLine } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, TopBar, useCompactWhenOverflowing } from "@/components/frame/screen"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { loadPortal } from "@/lib/portal"
import { go } from "@/lib/router"
import { useStore } from "@/lib/store"

export function About() {
  const portal = useStore((s) => s.portal)
  const { ref, compact } = useCompactWhenOverflowing([portal])
  React.useEffect(() => {
    void loadPortal()
  }, [])
  return (
    <Screen name="about">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/")}>
            رجوع
          </Button>
        }
        step="عن المهنة"
      />
      <Content ref={ref}>
        <h2 tabIndex={-1} className="text-title">
          {portal?.name ?? ""}
        </h2>
        <Card compact={compact}>
          <p id="home-about">{portal?.summary ?? ""}</p>
        </Card>
        <SourceLine id="home-about-source">{portal?.sources.summary ?? ""}</SourceLine>
      </Content>
      <BottomBar />
    </Screen>
  )
}
