// عرض DropdownNavigation وحده، ببنود بوابة التسويق كما يبنيها التطبيق.
import { DropdownNavigation } from "@/components/ui/dorpdown-navigation"
import { navItemsFor } from "@/lib/nav"

export function NavDemo() {
  return (
    <DropdownNavigation
      navItems={navItemsFor({ profession: "MARKETING", name: "التسويق", tools: ["CAMPAIGN"] })}
      label="أقسام البوابة"
    />
  )
}
