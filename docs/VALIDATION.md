# Skutečně provedené ověření

Datum: 2026-11-08. Výsledky se vztahují k této implementaci a uvedeným verzím; nejde o záruku úplnosti wiki nebo bezchybného OCR.

## Automatické testy

`pytest -q`: **55 passed**, bez síťových požadavků. Testy pokrývají:

- autentizaci s hidden tokenem, chybný login a jednu obnovu expirované session;
- HTTP 200 s loginem/denied/notFound, omezení streamu, 429 a tajemství prosté síťové chyby;
- blokování cizích redirectů, wiki akcí, traversal a symlinků;
- katalog s historickou/jazykovou variantou, vnořené a duplicitně pojmenované sekce, Markdown a fulltext vs. title suggestions;
- úplné stránkování, změněný či cizí kurzor, TTL a stale fallback jen při síťové chybě;
- skutečnou extrakci syntetického PDF a lokální OCR syntetického obrázku, render/crop a hash původu;
- ochranu celostránkového přepisu před výřezem, změnu originálu a hledání v médiích odkazovaných jiným namespace;
- deset výstupních schémat, chyby nástrojů, resources a skutečný obrazový MCP blok;
- samostatný stdio subprocess s automatickým discovery i starším handshake, včetně chyby chybějící autentizace při jiném pracovním adresáři.

`ruff check src tests scripts mcp_server.py` prošel. `pip check` nehlásil rozbité závislosti.

## Živý scénář přes MCP

Příkazy `scripts/live_smoke.py --live` a `--live --mode legacy` prošly proti přihlášené wiki:

| Krok | Pozorování |
|---|---|
| Protokol | Automaticky `2026-07-28`; legacy `2025-11-25` |
| Discovery | 10 nástrojů po doplnění komentářů |
| Katalog | 287 předmětů; přes kurzory navštívených všech 287 |
| BI-DBS | 21 sekcí, 81 navigačních položek včetně příloh, 16 359 znaků Markdownu |
| BI-AG1 | 21 sekcí, 273 položek, 45 131 znaků Markdownu s pokračováním |
| BI-ASB.21 | Historická varianta zachována; 9 sekcí, 21 položek |
| Hledání SQL v BI-DBS | 2 výsledky: vlastní index i podstránka z wiki fulltextu |
| Negativní dotaz | 0 výsledků, nikoliv chyba parseru |
| PDF příloha | 95 127 B, 2 strany, 2311 znaků nativního textu první strany |
| Obrazový výstup | Skutečný image block, 1414 × 2000 px |
| Čerstvá cache | Opakované čtení přibližně 8–9 ms přes MCP |

Počty odkazů jsou navigační položky včetně typů médií a vazby na sekce, nikoliv deklarovaný počet unikátních stránek celé wiki. Žádný plošný crawl nebyl proveden. Přihlašovací údaje ani soukromé texty nejsou součástí tohoto reportu.

## Doplnění diskusí (0.1.1)

Přidán read-only `get_comments` a resource `fitwiki://pages/{page_id}/comments`. Sedm nových testů ověřuje autora/čas, odpovědi včetně vnořených vláken, anonymní příspěvky, skrytý obsah a deduplikaci příloh, odstranění formulářů, neznámé rozložení, prázdnou/nedostupnou diskusi, filtrování bez diakritiky, pokračování dlouhého textu, cache/refresh a MCP výstup.

Živý test přes skutečný stdio subprocess na stránce PST z 11. 10. 2023 našel 2 komentáře; filtr podle autora převzatého z výsledku vrátil 1 příspěvek. Odpověď měla správné `parent_id`, skrytý obrázek byl dostupný v `attachments` a přímé navazující volání `get_material_image` vrátilo skutečný image block. Prošel i resource a cache hit. Soukromý obsah komentářů není uložen v repozitáři; fixtures jsou syntetické.

Komentáře se čtou z běžného HTML, nikoliv z XHTML exportu. Jejich původní text se neplete do Markdownu hlavní stránky. Cache diskuse má TTL nejvýše 300 s a zachovává původní politiku odmítnutí přístupu a označené starší kopie při síťovém výpadku. Samostatný klient potřebuje po aktualizaci nové MCP discovery pro zobrazení nástroje.

## OCR a vision

Reprodukovatelný offline příkaz `scripts/ocr_benchmark.py` vyhodnotil malý syntetický tištěný vzorek CZ/EN: 75 normalizovaných znaků, 12 slov, Tesseract 5.5.0 `ces+eng`, **CER 2,67 %**, **WER 16,67 %**. Jde o dvě chyby na malém vzorku; metriky nepředstavují přesnost na starých skenech. Text se označuje jako neověřený i při nízké chybovosti.

Ve skutečném Codex CLI proběhlo:

1. `get_material_image` na vybraný výřez existujícího materiálu s tištěným matematickým vzorcem.
2. Přepis vzorce modelem do LaTeXu a ruční porovnání s originálním výřezem.
3. `save_transcription` se skutečným hashem originálu a `partial=true`; uložení uspělo.
4. Samostatný výřez fotografie tabule: model přečetl krátkou rukopisnou číselnou posloupnost, výsledek byl porovnán s výřezem. Tento přepis nebyl automaticky označen za ověřený ani uložen jako celé zadání.

To dokládá funkčnost obrazové cesty a ukládání, nikoliv univerzální rozpoznávání rukopisu, vzorců či diagramů. Pro nečitelný či nejednoznačný obsah zůstává originál rozhodujícím podkladem. Server další OCR API nepoužil.

## Klienti

| Klient / verze | Skutečný výsledek | Hranice ověření |
|---|---|---|
| Codex 0.167.0 | Živé volání katalogu, image block, matematický přepis a uložení částečného přepisu; samostatná zkouška rukopisu | Dočasná konfigurace, bez změn uživatelského configu; pouze potřebné zápisové nástroje schválené pro tento test |
| Claude Code 2.1.295 | Nativní MCP health check `Connected` v izolovaném profilu | Není přihlášený modelový účet; modelové/vision volání neprovedeno |
| pi 1.5.0 | Nativní stdio `connected`, všech 9 nástrojů, resources dostupné | Modelový pokus skončil chybějícím API klíčem/přihlášením; vision model nebyl v pi ověřen |
| Antigravity CLI 1.5.2 | Model úspěšně zavolal katalog a vrátil správné `course_id` | Projektový MCP a dočasné oprávnění pouze k potřebnému nástroji; GUI/IDE a vision cesta tohoto klienta nejsou ověřené |
| OpenCode 2.2.6 | Formát konfigurace ověřen jeho vlastní registrací v izolovaném projektu; zdroj konfigurace byl načten | `mcp list` v testovaných kontextech neprokázal spojení; modelový pokus zastavila provider 429 / vyčerpaná bezplatná kvóta. Plný MCP/vision scénář v OpenCode nelze označit za ověřený |

První headless pokusy Codexu/Antigravity správně odmítly nástroje vyžadující souhlas. Následný test použil jen dočasné, konkrétní výjimky pro již autorizované operace, nikoliv vypnutí všech oprávnění. Návody jsou v [CLIENTS.md](CLIENTS.md). Cizí běžící služba OpenCode nebyla zastavována ani přenastavována.

## Balení a instalace

- Python 3.14.4 na Linux aarch64, oficiální MCP SDK 2.3.0, závislosti v `requirements.lock`.
- `python -m build` vytvořil sdist i univerzální wheel; build backend setuptools 84.2.1 je připnutý.
- Wheel byl instalován do samostatného čistého venv se zamčenými závislostmi; kontrola CLI a testů se provádí vůči instalovanému balíčku.
- Sdist zahrnuje dokumentaci, launcher, skripty a syntetické fixtures. Wheel ani sdist nezahrnují `.env`, cookies, cache, stažené materiály nebo privátní klientské logy.

## Zbývající omezení

- Verze runtime Pythonu 3.11–3.13 nebyly samostatně spuštěné; deklarované minimum je 3.11, zmrazené prostředí bylo ověřeno na 3.14.
- Cache používá TTL a explicitní refresh; ETag/Last-Modified ani číslo revize zdroje se zatím neuplatňují. Neznámá revize je `null`, čerstvý cache hit nemusí ověřit aktuální ACL na síti.
- Nativní text PDF může vynechat obsah rasterových částí; přítomnost obrázků vrací varování/`needs_vision`. Vyber příslušnou stranu pro lokální OCR nebo vidění modelu.
- Lokální OCR není spolehlivý přepis rukopisu a matematiky. Modelová cesta vyžaduje model s viděním a podporu obrazových MCP výsledků konkrétním klientem.
- Náhled výstupního obrázku má nejvýše 2000 px; pro drobný text je nutný výřez. Dekódování originálu má limit 20 MP. Nepodporované/poškozené či šifrované PDF a nečitelné obrázky vracejí chybu.
- Lokální index přepisů je omezen na 5000 záznamů. Nevytváří úplný index všech skenů wiki. Plná historie dříve známých vazeb médií na stránky může zůstat v cache do jejího smazání; nejde o živě ověřené backlinks.
- Zrušení dlouhého synchronního čtení/OCR je omezené timeoutem lokálního procesu; nejde o záruku okamžitého přerušení každé externí knihovny. Textová/resource data vrací zdroj a stav čerstvosti.
- Plný klientský test Claude Code, pi a OpenCode vyžaduje dostupný modelový účet/kvótu; Antigravity GUI nebylo dostupné jako ověřená relace. Tyto mezery nejsou vydávány za úspěšné testy.
