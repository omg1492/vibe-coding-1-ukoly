# 02 - Nastavení kódovacího agenta

Demo: project-scoped MCP server config + skill pro Claude Code.

## Co je v adresáři

- `.mcp.json` - konfigurace Playwright MCP serveru, project-scoped (commitne se do gitu, sdílí se s týmem)
- `.claude/skills/caveman/SKILL.md` - project-scoped skill `caveman` (ultra-stručný režim, ~75 % méně tokenů)
- `.claude/commands/caveman.md` - slash command `/caveman [lite|full|ultra|...]` pro přepnutí intenzity
- `.claude/hooks/` - 3 Node.js hooky (aktivace, mode tracking, sdílená konfigurace)
- `.claude/settings.json` - registrace hooků (`SessionStart` + `UserPromptSubmit`)
- Zdroj všech caveman souborů: [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (MIT, viz `.claude/skills/caveman/LICENSE`)

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

## Skill `caveman` + hooky

Caveman je rozdělen na 3 vrstvy, které spolupracují:

| Vrstva | Soubor | Co dělá |
|---|---|---|
| **Skill** | `.claude/skills/caveman/SKILL.md` | Pravidla režimu (rules, intensity levels, examples). Načte se přes skill discovery, když uživatel zmíní caveman. |
| **Slash command** | `.claude/commands/caveman.md` | `/caveman lite\|full\|ultra` - přepnutí intenzity uvnitř session. |
| **Hooky** | `.claude/hooks/caveman-{activate,mode-tracker,config}.js` | `SessionStart` injektuje pravidla na začátku session, `UserPromptSubmit` detekuje `/caveman` příkazy a píše stav do `~/.claude/.caveman-active`. |

Vrstvy se registrují v `.claude/settings.json` (project-scoped, commitne se do gitu):

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "node \"${CLAUDE_PROJECT_DIR}/.claude/hooks/caveman-activate.js\"" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command",
      "command": "node \"${CLAUDE_PROJECT_DIR}/.claude/hooks/caveman-mode-tracker.js\"" }] }]
  }
}
```

Aktivace v Claude Code:

- přirozeným jazykem: "use caveman", "caveman mode", "be brief"
- nebo slash command: `/caveman lite|full|ultra`

Vypnutí: `/caveman off`, "stop caveman" nebo "normal mode".

Pozn.: project-scoped hooky vyžadují **explicitní schválení** při prvním spuštění Claude Code v tomto adresáři. Bez `node` v `PATH` hooky tiše selžou (best-effort design).

## Bezpečnost

Project-scoped MCP servery vyžadují **explicitní schválení** při prvním načtení. Brání spuštění libovolných příkazů z naklonovaného repa bez vědomí uživatele.
