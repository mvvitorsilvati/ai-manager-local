import { describe, expect, it } from "vitest"

import { translate } from "@/lib/i18n"
import { en, es, pt, type Key } from "@/lib/locales"

describe("i18n", () => {
  it("todo texto PT tem tradução EN", () => {
    for (const key of Object.keys(pt) as Key[]) {
      expect(en[key], key).toBeTruthy()
    }
  })

  it("todo texto PT tem tradução ES", () => {
    for (const key of Object.keys(pt) as Key[]) {
      expect(es[key], key).toBeTruthy()
    }
  })

  it("interpola variáveis e cai para PT sem tradução", () => {
    expect(translate("pt", "dash.byAuthor", { author: "fulana" })).toBe("por fulana · ")
    expect(translate("en", "dash.byAuthor", { author: "fulana" })).toBe("by fulana · ")
    expect(translate("es", "dash.byAuthor", { author: "fulana" })).toBe("por fulana · ")
    expect(translate("en", "SPEND.TITLE" as Key)).toBe("SPEND.TITLE")
    expect(translate("es", "SPEND.TITLE" as Key)).toBe("SPEND.TITLE")
  })
})

