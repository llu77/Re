// Dumps the lucide icon nodes the fit mock uses, from the v2 client's own lucide-react.
import { writeFileSync } from "node:fs"
const base = process.argv[2]
const names = ["scan-eye", "hand", "database", "mail", "folder-lock", "trash", "user-round-search", "globe",
  "megaphone", "headset", "package", "sparkles", "clock", "square-check", "square", "chevron-left", "chevron-right"]
const out = {}
for (const name of names) {
  const mod = await import(`${base}/${name}.mjs`)
  out[name] = mod.__iconData.node
}
writeFileSync(process.argv[3], JSON.stringify(out))
console.log("icons", Object.keys(out).length)
