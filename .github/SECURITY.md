# Política de segurança

## Escopo

O AI Manager Local roda **apenas na sua máquina** (`127.0.0.1`), sem autenticação e sem enviar dados para fora — exceto as consultas de uso (Claude, Codex, Copilot), que usam as credenciais já existentes no seu sistema.

Faz parte do escopo de segurança:

- Path traversal / leitura fora das fontes permitidas (`resolve_file`)
- Escrita indevida (bypass de backup, corrupção de arquivo, sobrescrita concorrente)
- CSRF contra o servidor local (rotas `POST` e o header `X-AIM`)
- Vazamento de segredos pela API (tokens de MCP, credenciais, headers)
- Injeção (XSS) no frontend pela renderização de arquivos e busca

Fora do escopo: segurança da sua própria máquina/usuário, conteúdo dos arquivos de configuração que você escolhe visualizar e falhas em ferramentas de terceiros (opencode, Claude Code, Codex, Copilot, Gemini).

## Como reportar

- Prefira o **GitHub Private Vulnerability Reporting**: aba *Security* → *Report a vulnerability* no repositório
- Não abra issue pública para vulnerabilidades
- Inclua: descrição, passos para reproduzir, impacto e, se possível, uma sugestão de correção

Retorno esperado: confirmação de recebimento em alguns dias e uma correção assim que possível (projeto pessoal, sem SLA).

## Boas práticas ao contribuir

- Nunca comite credenciais, tokens, `auth.json`, `.env`, backups ou logs de auditoria
- Toda rota `POST` deve exigir o header `X-AIM: 1` e passar pelo `resolve_file`
- Nunca devolva segredos extraídos de arquivos de configuração pela API
- Escrita de arquivos sempre com backup + validação de sintaxe + `os.replace` atômico
