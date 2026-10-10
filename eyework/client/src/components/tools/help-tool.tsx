/*
 * مساعدة
 * ======
 * ما يفعله القسم الحالي (من lib/workspace.ts)، وكيف يعمل سيمبول، وبمن تتّصل. نصٌّ يُقرأ
 * بلا أهداف: لا يزيد ما يُضغط في الورقة.
 */

import { SymbolMark } from "@/components/brand/marks"
import type { Workspace } from "@/lib/workspace"

export function HelpTool({ workspace, screen, contact }: { workspace: Workspace; screen: string | null; contact: string | null }) {
  const help = screen ? workspace.help[screen] : null
  return (
    <div className="text-flow flex flex-col gap-tg">
      {help ? (
        <section aria-labelledby="help-section" className="flex flex-col gap-1.5">
          <h3 id="help-section" className="text-lead font-semibold">
            {help.title}
          </h3>
          <ul className="flex list-disc flex-col gap-1 ps-5">
            {help.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <section aria-labelledby="help-symbol" className="flex flex-col gap-1.5 rounded-card border border-primary-line/40 bg-secondary p-pad">
        <h3 id="help-symbol" className="flex items-center gap-2 text-lead font-semibold">
          <SymbolMark className="size-4" />
          سيمبول يقترح، وأنت تقرّر
        </h3>
        <p>يراجع سيمبول ما تسجّله. إن رأى ما يُستغرب ناداك باسمك وقال السبب، ولك أن تعدّل أو تتابع.</p>
        <p>واسأله من زرّه في كل شاشة: يجيب من مهامّ مهنتك وشاشتك، ويقرأ بأدواته ما يلزم من بوابتك.</p>
        <p>لا يغيّر سيمبول شيئاً بنفسه، ولا يصله اسمك.</p>
      </section>
      {contact ? (
        <p className="text-small text-muted-foreground">
          لمشكلةٍ في الحساب اكتب إلى{" "}
          <bdi dir="ltr" className="num font-semibold text-foreground">
            {contact}
          </bdi>
          .
        </p>
      ) : null}
    </div>
  )
}
