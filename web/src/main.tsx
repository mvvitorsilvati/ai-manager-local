import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { CollapseAllProvider } from "@/components/collapse"
import { TooltipProvider } from "@/components/ui/tooltip"
import { LanguageProvider } from "@/lib/i18n"
import { getLang, translate } from "@/lib/i18n"
import { createLog, isDebugEnabled } from "@/lib/log"
import { ThemeProvider } from "@/lib/theme"

import "./index.css"
import App from "./App"

const log = createLog("app")
log.info("painel iniciado", { debug: isDebugEnabled() })
window.addEventListener("error", (event) => log.error(translate(getLang(), "log.uncaught"), { message: event.message }))
window.addEventListener("unhandledrejection", (event) =>
  log.error(translate(getLang(), "log.unhandled"), { reason: String(event.reason) }),
)

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: 1 } },
})

const basename = window.location.pathname.startsWith("/novo") ? "/novo" : "/"
const router = createBrowserRouter([{ path: "*", element: <App /> }], { basename })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <ThemeProvider>
          <TooltipProvider>
            <CollapseAllProvider>
              <RouterProvider router={router} />
            </CollapseAllProvider>
          </TooltipProvider>
        </ThemeProvider>
      </LanguageProvider>
    </QueryClientProvider>
  </StrictMode>,
)
