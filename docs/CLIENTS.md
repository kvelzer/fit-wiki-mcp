# Připojení klientů

Server běží přes stdio. Společný spouštěcí příkaz používá **absolutní cestu** k `.venv/bin/python` a `mcp_server.py`. Launcher načítá `.env` z projektu; heslo není potřeba kopírovat do konfigurace klienta. Výstupy generátoru je nutné sloučit se stávajícím souborem, ne jím přepsat ostatní servery.

```bash
.venv/bin/python scripts/client_config.py codex
```

Poslední argument nahraď `claude`, `opencode`, `pi` nebo `antigravity`. Konfigurace je určená pro zde ověřené současné distribuce; u jiné verze zkontroluj její `--help`. Skutečně provedené zkoušky a jejich hranice uvádí [VALIDATION.md](VALIDATION.md).

## Codex

Fragment TOML patří do `~/.codex/config.toml`. Alternativně zaregistruj server pomocí absolutních cest:

```bash
codex mcp add fitwiki -- /ABS/fit-wiki-mcp/.venv/bin/python /ABS/fit-wiki-mcp/mcp_server.py
codex mcp get fitwiki
```

Otevři novou relaci a ověř dostupnost nástrojů. Doporučené timeouty v generátoru jsou startup 20 s a tool 120 s. Oficiální [OpenAI Docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) popisují stdio konfiguraci i pravidla schvalování.

Nástroje pro přílohy a ukládání přepisů jsou správně označené jako lokálně zapisující; v headless testu může klient jejich spuštění odmítnout, pokud čekají na interaktivní souhlas. Pro konkrétní uživatelem schválené workflow lze nastavit pouze potřebné nástroje, například:

```toml
[mcp_servers.fitwiki.tools.get_material_image]
approval_mode = "approve"

[mcp_servers.fitwiki.tools.save_transcription]
approval_mode = "approve"
```

Běžný generátor toto rozhodnutí za uživatele nemění. Nepotřebuješ vypínat sandbox nebo schvalování ostatních nástrojů.

## Claude Code

Zvol rozsah registrace podle projektu; zde je projektový server:

```bash
claude mcp add --transport stdio --scope project fitwiki -- /ABS/fit-wiki-mcp/.venv/bin/python /ABS/fit-wiki-mcp/mcp_server.py
claude mcp list
```

JSON z generátoru odpovídá `.mcp.json`. Claude Code může nejprve vyžádat schválení projektového serveru. MCP health check nepotřebuje přihlášení modelu, modelové/vision workflow ano. V izolovaném testu bylo připojení ověřeno s dočasným `CLAUDE_CONFIG_DIR` a explicitně povolenou testovací `.mcp.json`; osobní nastavení zůstalo zachované. [Dokumentace](https://code.claude.com/docs/en/mcp).

## OpenCode v2

Použij `opencode.json(c)` nebo `.opencode/opencode.json(c)` v projektu. **V2 používá `mcp.servers`**, příkaz je pole a prostředí se jmenuje `environment`; starší příklady s přímým mapováním pod `mcp` nepřebírej. Generátor nastaví protokol `auto`, který zkusí současné MCP a umožní fallback.

```bash
opencode mcp add fitwiki -- /ABS/fit-wiki-mcp/.venv/bin/python /ABS/fit-wiki-mcp/mcp_server.py
opencode mcp list
```

V relaci ověř nástroje, případně přes Code Mode. Lokální spravovaná/background služba může používat vlastní kontext a konfiguraci; „No MCP servers configured“ bez připojení nelze zaměnit za úspěšný serverový test. Testy této implementace se nedotýkají cizí běžící služby. [MCP](https://opencode.ai/docs/mcp-servers/), [konfigurace](https://opencode.ai/docs/config/).

## pi

Návod cílí na současný `@earendil-works/pi-coding-agent` (testována verze 1.5.0). Ten má nativní MCP; jiná či starší distribuce pi nemusí mít stejné rozhraní. Pro zkoušku byl instalován pouze pod ignorovanou `.private/pi`, nikoliv globálně.

```bash
pi mcp add fitwiki -- /ABS/fit-wiki-mcp/.venv/bin/python /ABS/fit-wiki-mcp/mcp_server.py
pi mcp list --json
```

JSON z generátoru patří do `~/.pi/agent/mcp.json`, případně `.pi/mcp.json` v důvěryhodném projektu. `PI_CODING_AGENT_DIR` umožňuje samostatný testovací profil. Vlastní modelový účet je samostatná podmínka; připojené MCP samo model nezajišťuje. [MCP dokumentace pi](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/mcp.md).

## Google Antigravity

CLI:

```bash
agy mcp add --type stdio fitwiki /ABS/fit-wiki-mcp/.venv/bin/python /ABS/fit-wiki-mcp/mcp_server.py
agy mcp list
```

Generovaný JSON lze použít v projektovém `.agents/mcp_config.json`; současná společná globální konfigurace je `~/.gemini/config/mcp_config.json`. CLI `mcp list` nemusí odpovídat načítání projektových serverů v modelové relaci, proto ověř také skutečné volání. IDE/App mají vlastní relaci a zobrazení MCP: úspěch CLI neprokazuje GUI.

Headless CLI neumí interaktivně potvrdit nástroj. Pro konkrétní povolený smoke test funguje dočasné `--settings` s pravidlem `permissions.allow: ["mcp(fitwiki/list_courses)"]`; pro vision a přepis je třeba samostatně povolit odpovídající nástroje. Obecné `mcp(*)` ani vypnutí všech oprávnění nejsou nutné. [MCP](https://antigravity.google/docs/mcp), [pravidla oprávnění](https://antigravity.google/docs/permissions).

## Společný kontrolní scénář

1. Nech klienta zavolat `list_courses(query="BI-DBS", limit=2)` a vrátit přesné `course_id`.
2. Projdi `get_course_index`, načti konkrétní stránku a ověř URL i stav cache.
3. Stáhni přílohu a načti jednu stranu přes `read_attachment`.
4. S modelem podporujícím obrázky zavolej `get_material_image`; ověř, že model vidí obraz, nikoliv jen metadata. Přepis ulož přes `save_transcription` s hashem originálu, u výřezu `partial=true`.
5. Při testu nečitelného obrázku, chybě přihlášení nebo omezení klienta očekávej přiznané omezení, ne domyšlený obsah. Další textové bloky/strany načítej přes vrácené pokračování.

Klient musí umět obrazový MCP obsah a zvolený model musí mít vidění; samotná podpora stdio MCP k OCR rukopisu nestačí. Výsledek přepisu je vždy neověřený a dohledatelný k originálu.
