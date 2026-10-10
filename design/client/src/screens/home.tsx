/*
 * الرئيسية: تحيّة سيمبول، ثم خانتان ثابتتان — أداة البوابة والمساعد — ثم المهامّ
 * والمهارات. البلاطات تملأ ما بقي من الارتفاع: الهدف الأكبر أسهل على النظر، ولا
 * ينزل أيٌّ منها عن 72. «حسابي» أعلى النهاية، وتحته في «حسابي» خانةٌ فارغة.
 */
import * as React from "react"
import { BookOpen, GraduationCap, ListChecks, Sparkles, UserRound } from "lucide-react"

import { PersonaMark, Tile } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, TopBar } from "@/components/frame/screen"
import { Button } from "@/components/ui/button"
import { GENERIC } from "@/lib/api"
import { countLabel, greeting } from "@/lib/labels"
import { loadPortal } from "@/lib/portal"
import { go } from "@/lib/router"
import { getState, nextNav, showAlert, useStore } from "@/lib/store"
import { TOOL_TILES } from "@/lib/tools"
import { cn } from "@/lib/utils"

export function Home() {
  const portal = useStore((s) => s.portal)
  const name = useStore((s) => s.displayName)

  const refresh = React.useCallback(async () => {
    const nav = nextNav()
    const fresh = await loadPortal({ fresh: true })
    if (nav !== getState().nav) return
    if (!fresh) showAlert("home", `${GENERIC} «حسناً» تعيد المحاولة.`)
  }, [])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const tool = portal?.tools.map((code) => TOOL_TILES[code]).find(Boolean) ?? null

  return (
    <Screen name="home" onAck={() => !getState().portal && void refresh()}>
      <TopBar
        stepId="home-portal"
        step={portal ? `بوابة ${portal.name}` : ""}
        end={
          <Button id="home-account" icon={UserRound} onClick={() => go("#/account")}>
            حسابي
          </Button>
        }
      />
      <Content>
        <div className="flex flex-none items-center gap-3">
          <PersonaMark />
          <h2 tabIndex={-1} id="home-greeting" className="text-title">
            {greeting(name)}
          </h2>
        </div>
        <div
          id="home-actions"
          hidden={!portal}
          className="mt-2 grid min-h-0 flex-1 grid-cols-2 grid-rows-[repeat(2,minmax(min-content,1fr))] gap-gap"
        >
          {tool ? (
            <Tile
              id="home-tool"
              layout="stack"
              icon={tool.icon}
              title={tool.title}
              description={tool.description}
              onClick={() => go(tool.route)}
            />
          ) : null}
          <Tile
            id="home-assistant"
            variant="secondary"
            layout={tool ? "stack" : "row"}
            icon={Sparkles}
            title="اسأل سيمبول"
            description={tool ? "يقترح، وأنت تقرّر" : "يقترح خطواتٍ من مهامّ مهنتك، بمصادرها"}
            className={cn(!tool && "col-span-2")}
            onClick={() => go("#/assistant")}
          />
          <Tile
            id="home-tasks"
            layout="stack"
            icon={ListChecks}
            title="المهامّ"
            description={portal ? countLabel(portal.tasks.length, "مهمة واحدة", "مهمتان", "مهامّ", "مهمة") : ""}
            onClick={() => go("#/tasks/1")}
          />
          <Tile
            id="home-skills"
            layout="stack"
            icon={GraduationCap}
            title="المهارات"
            description={portal ? countLabel(portal.skills.length, "مهارة واحدة", "مهارتان", "مهارات", "مهارة") : ""}
            onClick={() => go("#/skills/1")}
          />
        </div>
        <Button
          id="home-about-open"
          icon={BookOpen}
          hidden={!portal}
          className="spaced w-full flex-none justify-start"
          onClick={() => go("#/about")}
        >
          عن المهنة ومصادرها
        </Button>
      </Content>
      <BottomBar
        start={
          <Button id="home-older" reserved>
            الأقدم
          </Button>
        }
        end={
          <Button id="home-newer" reserved>
            الأحدث
          </Button>
        }
      />
    </Screen>
  )
}
