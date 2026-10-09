/* عن المهنة: تعريفها مترجماً عن مصدره، وسطر المصدر، والمهن القريبة في التصنيفات. */
import * as React from "react"
import { ChevronRight } from "lucide-react"

import { SourceLine } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, TopBar } from "@/components/frame/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { loadPortal } from "@/lib/portal"
import { go } from "@/lib/router"
import { useStore } from "@/lib/store"

export function About() {
  const portal = useStore((s) => s.portal)
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
      <Content>
        <h2 tabIndex={-1} className="text-title">
          {portal?.name ?? ""}
        </h2>
        <Card>
          <p id="home-about">{portal?.summary ?? ""}</p>
        </Card>
        <SourceLine id="home-about-source">{portal?.sources.summary ?? ""}</SourceLine>
        <div className="mt-2 flex flex-wrap gap-2">
          {portal?.related.map((line) => (
            <Badge key={line} variant="outline">
              {line}
            </Badge>
          ))}
        </div>
      </Content>
      <BottomBar />
    </Screen>
  )
}
