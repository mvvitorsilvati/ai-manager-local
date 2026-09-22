import { beforeEach, describe, expect, it, vi } from "vitest"

import { createLog, getLogs, isDebugEnabled } from "@/lib/log"

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("log", () => {
  it("sem debug: warn vai ao console e ao buffer, debug só ao buffer", () => {
    expect(isDebugEnabled()).toBe(false)
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    const debug = vi.spyOn(console, "debug").mockImplementation(() => {})
    const before = getLogs().length
    const log = createLog("teste")
    log.warn("algo estranho", { rota: "/api/x" })
    log.debug("detalhe silencioso")
    expect(warn).toHaveBeenCalledOnce()
    expect(debug).not.toHaveBeenCalled()
    const entries = getLogs().slice(before)
    expect(entries.map((e) => [e.scope, e.level, e.message])).toEqual([
      ["teste", "warn", "algo estranho"],
      ["teste", "debug", "detalhe silencioso"],
    ])
    expect(entries[0].data).toEqual({ rota: "/api/x" })
    expect(typeof entries[0].ts).toBe("string")
  })

  it("error sempre vai ao console mesmo sem debug", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {})
    createLog("teste").error("quebrou")
    expect(error).toHaveBeenCalledOnce()
  })
})
