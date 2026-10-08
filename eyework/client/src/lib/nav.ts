/*
 * بنود التنقّل من بوابة صاحب الجلسة
 * =================================
 * من ردّ /api/portal وحده: «العمل» لا يظهر إلا لمهنةٍ لها أداة، ووجهات البنود مسارات
 * التطبيق القائمة (static/app.js وportal.js).
 */

import { BookOpen, GraduationCap, LayoutGrid, ListChecks, LogOut, Megaphone, UserRound } from "lucide-react"

import type { NavItem } from "@/components/ui/dorpdown-navigation"

export interface Portal {
  profession: string
  name: string
  tools: string[]
}

export function navItemsFor(portal: Portal): NavItem[] {
  const items: NavItem[] = [
    {
      id: 1,
      label: "بوابتي",
      subMenus: [
        {
          title: `بوابة ${portal.name}`,
          items: [
            { label: "المهامّ", description: "ما تتطلّبه المهنة، من مصادر رسمية", icon: ListChecks, href: "/#/tasks/1" },
            { label: "المهارات", description: "ما يحتاجه أداء المهامّ", icon: GraduationCap, href: "/#/skills/1" },
          ],
        },
      ],
    },
  ]
  if (portal.tools.includes("CAMPAIGN")) {
    items.push({
      id: 2,
      label: "العمل",
      subMenus: [
        {
          title: "أدوات المهنة",
          items: [
            { label: "حملة جديدة", description: "عنوانٌ ووصفٌ لمنتجٍ من صورته، تراجعهما ثم تعتمد", icon: Megaphone, href: "/#/new" },
            { label: "حملاتي", description: "ما كتبتَه وما اعتمدتَه", icon: LayoutGrid, href: "/#/" },
          ],
        },
      ],
    })
  }
  items.push({
    id: 3,
    label: "حسابي",
    subMenus: [
      {
        title: "الحساب",
        items: [
          { label: "حسابي", description: "الاسم والمهنة ومفتاح المرور", icon: UserRound, href: "/#/account" },
          { label: "المصادر", description: "من أين جاءت المهامّ والمهارات", icon: BookOpen, href: "/#/account/sources" },
          { label: "تسجيل الخروج", description: "بخطوة تأكيدٍ قبل الخروج", icon: LogOut, href: "/#/account/logout" },
        ],
      },
    ],
  })
  return items
}
