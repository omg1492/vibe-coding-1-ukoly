# 02 - Nastavení kódovacího agenta

Demo: project-scoped MCP server config + skill pro Claude Code.

## Co je v adresáři

- `.mcp.json` - konfigurace Playwright MCP serveru, project-scoped (commitne se do gitu, sdílí se s týmem)
- `.claude/skills/caveman/SKILL.md` - project-scoped skill `caveman` (ultra-stručný režim, ~75 % méně tokenů). Zdroj: [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (MIT)

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

## Skill `caveman`

Project-scoped skill v `.claude/skills/caveman/SKILL.md` - ultra-stručný režim, který shazuje výplňová slova (please, sure, certainly, articles a/an/the, hedging) a šetří ~75 % tokenů.

Aktivace v Claude Code:

- "use caveman", "caveman mode", "be brief"
- nebo `/caveman lite|full|ultra` (přepnutí intenzity)

Vypnutí: "stop caveman" nebo "normal mode".

Skills uložené v `.claude/skills/<name>/SKILL.md` jsou project-scoped - commitnou se do gitu a načtou se automaticky každému, kdo si repo naklonuje.

## Bezpečnost

Project-scoped MCP servery vyžadují **explicitní schválení** při prvním načtení. Brání spuštění libovolných příkazů z naklonovaného repa bez vědomí uživatele.
