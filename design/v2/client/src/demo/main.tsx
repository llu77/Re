import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { DemoApp } from "@/demo/demo-app"
import "@/styles/globals.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <DemoApp />
  </StrictMode>,
)
