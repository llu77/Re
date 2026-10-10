/*
 * مساعدة
 * ======
 * ما يفعله القسم الحالي (من lib/workspace.ts)، وبمن تتّصل. نصٌّ يُقرأ حين يُطلب، بلا أهداف: لا
 * يزيد ما يُضغط في الورقة.
 */

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
