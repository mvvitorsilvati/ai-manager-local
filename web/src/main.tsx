import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { CollapseAllProvider } from "@/components/collapse"
import { TooltipProvider } from "@/components/ui/tooltip"
import { createLog } from "@/lib/log"

import "./index.css"
import App from "./App"

const log = createLog("app")
window.addEventListener("error", (event) => log.error("erro não tratado", { message: event.message }))
window.addEventListener("unhandledrejection", (event) =>
  log.error("promise rejeitada sem catch", { reason: String(event.reason) }),
)

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: 1 } },
})

const basename = window.location.pathname.startsWith("/novo") ? "/novo" : "/"
const router = createBrowserRouter([{ path: "*", element: <App /> }], { basename })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <CollapseAllProvider>
          <RouterProvider router={router} />
        </CollapseAllProvider>
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
