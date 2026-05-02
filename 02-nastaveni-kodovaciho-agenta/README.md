# 02 - Nastavení kódovacího agenta

Demo: project-scoped MCP server config for Claude Code.

## Co je v adresáři

- `.mcp.json` - konfigurace Playwright MCP serveru, project-scoped (commitne se do gitu, sdílí se s týmem)

## Konfigurace

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

`npx` stáhne a spustí `@playwright/mcp` při startu - není třeba nic instalovat ručně. Browsery se stáhnou při prvním použití (~150 MB).

## Aktivace

1. Spusť Claude Code v tomto adresáři (`claude` v terminálu).
2. Při prvním startu se objeví prompt na schválení MCP serverů z `.mcp.json` - potvrď.
3. Ověř příkazem `/mcp` - `playwright` by měl být `connected`.
4. Vyzkoušej: "otevři example.com a udělej screenshot".

## Scopes MCP konfigurace

| Scope | Soubor | Sdílení |
|---|---|---|
| **project** | `.mcp.json` (root projektu) | commitne se do gitu, sdílí s týmem |
| **user** | `~/.claude.json` | jen ty, všechny projekty |
| **local** | `.claude/settings.local.json` | jen ty, jen tento projekt |

Project scope je nejvhodnější pro demo a týmovou spolupráci - každý, kdo si naklonuje repo, dostane stejné MCP nastavení (po schválení).

## Bezpečnost

Project-scoped MCP servery vyžadují **explicitní schválení** při prvním načtení. Brání spuštění libovolných příkazů z naklonovaného repa bez vědomí uživatele.
