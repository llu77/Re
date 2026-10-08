import * as React from "react"

const MOBILE_BREAKPOINT = 768
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

/**
 * تطبيقٌ من جهة العميل وحدها، فالقيمة الأولى تُقرأ من النافذة مباشرةً: لا
 * يُرسم الشريط مرةً بهيئة سطح المكتب ثم يُستبدل على الهاتف.
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState(() => window.matchMedia(QUERY).matches)

  React.useEffect(() => {
    const query = window.matchMedia(QUERY)
    const onChange = () => setIsMobile(query.matches)
    query.addEventListener("change", onChange)
    onChange()
    return () => query.removeEventListener("change", onChange)
  }, [])

  return isMobile
}
