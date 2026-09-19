## O que muda

<!-- Descreva o problema e a solução em 2-4 linhas. Linke a issue, se houver: Closes #123 -->

## Como validar

<!-- Comandos e resultado esperado. Ex.: `just check`, abrir /ia?tool=codex e conferir o card -->

```bash
just check
```

## Checklist

- [ ] Commits seguem Conventional Commits (um assunto por commit)
- [ ] `just check` passa (pytest, vitest, ruff, pyright, oxlint, oxfmt)
- [ ] Testes no nível certo (unit / integration / e2e) para o que mudou
- [ ] Sem segredos, tokens, `.env`, backups ou logs no diff
- [ ] README/CONTRIBUTING atualizados, se o comportamento mudou

## Tipo

- [ ] `feat` — nova funcionalidade
- [ ] `fix` — correção de bug
- [ ] `chore` / `docs` / `test` / `ci` — sem mudança de comportamento
- [ ] `refactor` — mudança interna sem alterar comportamento

## Capturas (opcional)

<!-- Antes/depois, quando for mudança visual -->
