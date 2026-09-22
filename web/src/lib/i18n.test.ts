import { describe, expect, it } from "vitest"

import { translate } from "@/lib/i18n"
import { en, pt, type Key } from "@/lib/locales"

describe("i18n", () => {
  it("todo texto PT tem tradução EN", () => {
    for (const key of Object.keys(pt) as Key[]) {
      expect(en[key], key).toBeTruthy()
    }
  })

  it("interpola variáveis e cai para PT sem tradução", () => {
    expect(translate("pt", "dash.byAuthor", { author: "fulana" })).toBe("por fulana · ")
    expect(translate("en", "dash.byAuthor", { author: "fulana" })).toBe("by fulana · ")
    expect(translate("en", "SPEND.TITLE" as Key)).toBe("SPEND.TITLE")
  })
})
