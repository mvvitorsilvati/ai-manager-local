import { cp, mkdir, rm } from "node:fs/promises"
import path from "node:path"

/**
 * Copia a fixture de projetos para um diretório temporário antes da suíte,
 * para que os testes de edição/salvamento não alterem os arquivos versionados.
 */
export default async function globalSetup() {
  const here = import.meta.dirname
  const target = path.resolve(here, ".tmp")
  await rm(target, { recursive: true, force: true })
  await mkdir(target, { recursive: true })
  await cp(path.resolve(here, "fixtures"), path.join(target, "projetos"), { recursive: true })
}
