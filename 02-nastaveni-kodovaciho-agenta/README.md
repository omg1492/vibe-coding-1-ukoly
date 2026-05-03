# 02 - Nastavení kódovacího agenta

Demo: project-scoped MCP server config + skill pro Claude Code.

## Co je v adresáři

- `.mcp.json` - konfigurace Playwright MCP serveru, project-scoped (commitne se do gitu, sdílí se s týmem)
- `.claude/skills/caveman/SKILL.md` - project-scoped skill `caveman` (ultra-stručný režim, ~75 % méně tokenů)
- `.claude/commands/caveman.md` - slash command `/caveman [lite|full|ultra|...]` pro přepnutí intenzity
- `.claude/hooks/` - 3 Node.js hooky (aktivace, mode tracking, sdílená konfigurace)
- `.claude/agents/page-summarizer.md` - subagent shrnující webovou stránku přes Playwright MCP
- `.claude/agents/repo-doctor.md` - subagent auditující konfiguraci přes `scripts/audit.sh`
- `scripts/audit.sh` - shell helper pro repo-doctor (PASS/WARN/FAIL kontrola artefaktů)
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

> **Důležité:** Claude Code musí být spuštěn **přímo v tomto adresáři** (`02-nastaveni-kodovaciho-agenta/`), ne v kořeni repa. Project-scoped soubory (`.mcp.json`, `.claude/commands/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`) se načítají jen z `cwd`, kde Claude Code startuje. Pokud spustíš `claude` o úroveň výš, slash command `/caveman` se nezobrazí, MCP server se nenačte a hooky se nezaregistrují.

1. `cd 02-nastaveni-kodovaciho-agenta` a spusť `claude` v terminálu.
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

Demo úkol vyžaduje navíc i **Subagenta** - ten je oddělená čtvrtá vrstva, popsaná níž.

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

## Subagent `page-summarizer`

Minimální příklad subagenta, který demonstruje koncept a zároveň využívá už nakonfigurovaný **Playwright MCP** server (synergie MCP + Subagent v jednom příkladu).

| Vlastnost | Hodnota |
|---|---|
| Soubor | `.claude/agents/page-summarizer.md` |
| Co dělá | Otevře URL přes `browser_navigate` + `browser_snapshot`, vrátí 3 odrážky (titulek, hlavní téma, klíčové sekce). |
| Vyvolání | Přirozeně: "summarize https://example.com" / "co je na ...". Explicitně: "use page-summarizer agent on ...". |
| Proč subagent | Velký HTML/accessibility snapshot zůstane v **izolovaném kontextu** subagenta, do hlavní konverzace se vrátí jen 3 odrážky. |
| Závislost | Playwright MCP (viz `.mcp.json` výš). |

Ověř, že je subagent načtený, příkazem `/agents` v Claude Code - `page-summarizer` musí být v seznamu.

## Subagent `repo-doctor`

Komplexnější subagent - místo MCP nástroje volá lokální shell skript a parsuje strukturovaný výstup. Demonstruje vzor "subagent + helper script" a self-referenčně audituje právě tu konfiguraci, kterou tento úkol učí.

| Vlastnost | Hodnota |
|---|---|
| Soubor | `.claude/agents/repo-doctor.md` |
| Helper | `scripts/audit.sh` (bash, žádné runtime závislosti kromě `node`/`python3` na JSON validaci) |
| Co dělá | Spustí `audit.sh`, který vyprodukuje řádky `[PASS\|WARN\|FAIL] <kategorie> <zpráva>`. Subagent výstup seskupí podle kategorie a ke každému WARN/FAIL přidá konkrétní návrh opravy. |
| Kontroly | platnost JSON v `.mcp.json` a `settings*.json`, `node --check` všech hooků, frontmatter v subagentech a skillech, existence cest referencovaných v `settings.json`, sekce v README. |
| Vyvolání | "audituj repo", "use repo-doctor agent", "is my Claude Code setup complete?". |
| Proč subagent | Skript produkuje desítky řádků výstupu - izolace v subagentovi udrží hlavní kontext čistý, vrací se jen finální checklist. |

Ruční spuštění bez Claude Code:

```bash
bash scripts/audit.sh
# nebo proti jinému adresáři:
bash scripts/audit.sh /path/to/other/claude-project
```

Skript vždy končí kódem 0 a tiskne `[SUMMARY] pass=N warn=N fail=N` jako poslední řádek.

## Bezpečnost

Project-scoped MCP servery vyžadují **explicitní schválení** při prvním načtení. Brání spuštění libovolných příkazů z naklonovaného repa bez vědomí uživatele.
