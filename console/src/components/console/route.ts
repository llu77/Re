import * as React from "react"

/**
 * توجيهٌ بجزء الرابط بعد `#`: يعمل خلف أيّ مسار يُخدم منه الملف، ولا يحتاج
 * الخادم أن يعرف صفحات اللوحة. والرجوع في المتصفّح يرجع خطوةً في اللوحة.
 */
export type Route =
  | { name: "queue" }
  | { name: "proposal"; id: string }
  | { name: "red-flags" }

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "")
  if (path === "/red-flags") return { name: "red-flags" }
  const proposal = path.match(/^\/queue\/([^/]+)$/)
  if (proposal && UUID.test(proposal[1])) return { name: "proposal", id: proposal[1] }
  return { name: "queue" }
}

export function href(route: Route): string {
  switch (route.name) {
    case "queue":
      return "#/queue"
    case "proposal":
      return `#/queue/${route.id}`
    case "red-flags":
      return "#/red-flags"
  }
}

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = React.useState(() => parseRoute(window.location.hash))

  React.useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener("hashchange", onChange)
    return () => window.removeEventListener("hashchange", onChange)
  }, [])

  const navigate = React.useCallback((next: Route) => {
    window.location.hash = href(next)
  }, [])

  return [route, navigate]
}
