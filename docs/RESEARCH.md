# Průzkum FIT Wiki a referenčního MCP

Datum: 2026-11-08. Malý read-only vzorek; jedinou vzdálenou operací měnící session bylo uživatelem autorizované přihlášení. Obsah materiálů ani přílohy se neukládaly do projektu, cookies zůstaly v paměti. Tento zápis uvádí strukturu a technická pozorování, nikoliv tajemství nebo obsah studentských řešení.

## Wiki: ověřená fakta

| Oblast | Pozorování | Důsledek pro návrh |
|---|---|---|
| Engine | DokuWiki, šablona bootstrap3, před webem Cloudflare | Prozkoumat standardní exporty před vlastní browser automatizací |
| Anonymní přístup | Homepage i katalog vracejí HTTP 200 s `JSINFO.ACT=denied`, `mode_denied` a `#dw__login` | HTTP status neprokazuje získání materiálu |
| Přihlášení | Úspěšný standardní formulářový login s údaji z `.env` | Žádné přebírání CTU OAuth z reference |
| Ověření session | Po loginu `ACT=show`, žádný login formulář, odkaz `do=logout`; chráněný katalog dostupný | Úspěch ověřovat kombinací markerů a požadovaného obsahu |
| Identita | Např. `škola:předměty:bi-dbs`; URL používá lomítka a encoding diakritiky | Jednotné reverzibilní mapování ID/URL |
| Předměty | `bi-*`, `bie-*`, varianty `.21`, některé indexy na `/obsah` | Skutečnou URL brát z katalogu, verze nezahazovat |
| Kategorie | Hierarchie H2/H3/H4 v indexu předmětu; sekce nemusí být samostatnou stránkou/namespace | Nehardcodovat univerzální slugy kategorií |
| Vnoření | Existují cesty pod předmětem s dalšími úrovněmi, např. rok | Neomezovat model na jedinou úroveň |
| Přílohy | `/_media/{namespace}/{file}`; obrázkové detaily `/_detail/...?...id=...` | Odlišit soubor, detail obrázku a stránku |
| Správce médií | Odkaz `?do=media` není odkazem na stažitelný soubor | Nefiltrovat přílohy jen podle slova „media“ |

### Auth tok

1. Načíst `https://fit-wiki.cz/obsah?do=login`.
2. Najít formulář `#dw__login`, jeho action a hidden vstupy včetně `id`, `do`, `sectok`.
3. Ve stejné HTTP session odeslat formulář s poli `u`, `p` a načtenými hidden vstupy.
4. Ověřit zánik login formuláře, úspěšný režim a přístup k chráněnému katalogu.

Existující klíče se jmenují `COURSES_USERNAME` a `COURSES_PASSWORD`; jejich hodnoty FIT Wiki přijala. Názvy neznamenají, že autentizace funguje stejně jako courses portál. Nepřepisovat uživatelův `.env` bez konkrétní potřeby návrhu.

`requests.Session` s UA `curl/8.5.0` a běžný curl fungovaly. Výchozí urllib klient dostal 403. Příčina rozdílu nebyla izolována: nelze tvrdit, že samotná změna UA vždy problém vyřeší.

### Endpointy a malý vzorek

| URL / rozhraní | Výsledek průzkumu |
|---|---|
| [Homepage](https://fit-wiki.cz/) | Veřejná informace o registraci a login; obsah vyžaduje oprávněný účet |
| [Katalog](https://fit-wiki.cz/%C5%A1kola/p%C5%99edm%C4%9Bty) | Po přihlášení skutečný index předmětů |
| [BI-AG1](https://fit-wiki.cz/%C5%A1kola/p%C5%99edm%C4%9Bty/bi-ag1) | 219 odkazů na podstránky; počet odkazů, nikoliv unikátních stránek |
| [BI-DBS](https://fit-wiki.cz/%C5%A1kola/p%C5%99edm%C4%9Bty/bi-dbs) | 45 odkazů na podstránky; stejná výhrada |
| [Mapa stránek](https://fit-wiki.cz/obsah?do=index) | HTTP 200, `ACT=index`; zahrnuje i oblasti mimo předměty |
| `/_export/raw/{page-path}` | Dva auth vzorky: HTTP 200, text/plain, 1111 a 784 B; anonymně denied HTML |
| `/_export/xhtml/{page-path}` | Dva auth vzorky: HTTP 200, text/html, přibližně 10 kB a 5,8 kB, bez navbaru |
| [Ověřená PDF příloha](https://fit-wiki.cz/_media/%C5%A1kola/p%C5%99edm%C4%9Bty/bi-dbs/zadani-a-zverejneno.pdf) | Autentizovaný stream HTTP 200, application/pdf, 95 127 B, signatura `%PDF-`, filename v Content-Disposition; bez uložení souboru |
| [Hledání](https://fit-wiki.cz/doku.php?do=search&id=bi-dbs) | Po loginu HTTP 200, ACT=search, HTML výsledky |
| [Suggestions](https://fit-wiki.cz/lib/exe/ajax.php?call=suggestions&q=bi-dbs) | HTTP 200, application/x-suggestions+json, JSON list; malá odpověď 27 B neprokazuje užitečné fulltextové výsledky |
| [OpenSearch](https://fit-wiki.cz/lib/exe/opensearch.php) | XML inzeruje search a suggestions endpointy |
| [XML-RPC](https://fit-wiki.cz/lib/exe/xmlrpc.php) | HTTP 200 s fault -32605, „XML-RPC server not enabled.“ |
| [Sitemap](https://fit-wiki.cz/sitemap.xml) | HTTP 404, DokuWiki notFound |
| [Robots](https://fit-wiki.cz/robots.txt) | HTTP 200, 1248 B; vysvětlující komentáře Cloudflare, žádné aktivní User-agent/Allow/Disallow/Content-Signal/Sitemap direktivy |

Homepage uvádí registraci studenta FIT a výchozí licenci CC BY-NC-SA 4.0 s možnými výjimkami u konkrétního obsahu. Pozorováno HTML `noindex,nofollow`; tento zápis z něj nevyvozuje oprávnění k dalším operacím. Uživatelská autorizace se vztahuje na jeho legitimně dostupný obsah.

### Dosud neověřeno

- Úplnost katalogu a jednoznačnost aliasů napříč všemi předměty.
- Kvalita XHTML/raw převodu na matematice, velkých tabulkách, kódu a materiálech tvořených převážně obrázky.
- Fulltext skutečného obsahu oproti shodě v názvu, filtrace namespace/předmětu, syntaxe dotazů, stránkování a úplnost hledání.
- Revalidace přes ETag/Last-Modified, životnost session, odebrání práv a způsob chyb u různých chráněných médií.
- Požadavky na externí přílohy, velké archivy a soubory bez Content-Length.
- Žádná tvrzení o pokrytí celé wiki nebo bezchybném převodu všech formátů.

### Doplnění: fulltext a omezení na předmět

Autentizovaně ověřeno `GET /doku.php?do=search&q=SQL%20%40škola%3Apředměty`: 16 kontejnerů `.search_fullpage_result`, z toho 14 titulků bez hledaného termínu, 29 zvýraznění `.search_hit`. Termín byl předem ověřen v raw přehledu BI-DBS. To potvrzuje hledání v obsahu, nejen v titulcích.

`q=SQL @škola:předměty:bi-dbs` vrátil podstránku s obsahovou shodou a titulkem bez hledaného termínu. Namespace filtr vynechal samotnou kořenovou stránku `škola:předměty:bi-dbs`, která přitom byla v globálním výsledku. Pro hledání v předmětu tedy doplnit kontrolu vlastního indexu a deduplikovat. Globální studijní rozsah omezit na `@škola:předměty`.

HTML odděluje `.search_quickresult`/`.search_quickhits` pro titulky a `.search_fulltextresult > .search_results > .search_fullpage_result` pro obsah. Dosud pozorované sady 16/25 výsledků neukázaly ovládání další stránky; nejde o důkaz absence limitu či stránkování. Syntax uživatelského dotazu musí projít parserem/validací tak, aby nemohla neúmyslně přepsat slíbený rozsah nástroje.

Poslední širší probe `test @škola` vrátil HTTP 200, přibližně 3,05 MB HTML a 2621 elementů `.search_fullpage_result`, bez pozorovaných next/prev nebo start/offset/page ovládacích prvků. To podporuje lokální stránkování získaných výsledků a omezení velikosti upstream odpovědi; neprokazuje univerzální absenci stránkování. `sf=1` je pozorované pole search formuláře, nikoliv prokázaný offset. Rozsah `@škola` zahrnuje také studijní oblasti mimo katalog předmětů, například státnice; `@škola:předměty` je užší filtr.

[Oficiální DokuWiki search](https://www.dokuwiki.org/search#search_within_a_namespace) dokládá namespace syntaxi a rozdíl quicksearch/fulltext. Aktuálnost a úplnost serverového indexu FIT Wiki nebyla ověřena; žádný výsledek neznamená důkaz neexistence materiálu.

## Doplnění: OCR pro první verzi

Uživatel vyžaduje OCR skenů již v první verzi. Ověřený lokální inventář: Poppler `pdfinfo`, `pdftotext`, `pdftoppm` 26.01.0. V PATH nejsou Tesseract, OCRmyPDF, Ghostscript ani qpdf; v systémovém Pythonu nebyly nalezeny kontrolované PDF/OCR knihovny. V běžných systémových adresářích nejsou `.traineddata`. Inventář se nevztahuje automaticky na všechna cizí virtuální prostředí. V této fázi se nic neinstalovalo ani neposílalo externí službě.

- [Tesseract FAQ](https://tesseract-ocr.github.io/tessdoc/FAQ.html#can-i-use-tesseract-for-handwriting-recognition): nástroj je orientovaný na tištěný text a rukopis má omezenou kvalitu.
- [Oficiální modely](https://tesseract-ocr.github.io/tessdoc/Data-Files.html): dostupné `ces`/`eng`; `equ` označuje detekci rovnic, ne garanci matematické transkripce.
- [Kvalita vstupu](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html): DPI, natočení a segmentace ovlivňují výsledky; samostatně řešit tabulky a layout.
- [OCRmyPDF introduction](https://ocrmypdf.readthedocs.io/en/latest/introduction.html) a [sidecar](https://ocrmypdf.readthedocs.io/en/latest/cookbook.html#produce-pdf-and-text-file-containing-ocr-text): standardní Tesseract pipeline a textová vrstva PDF; sidecar sám nepokrývá nativní či přeskočené stránky.
- [Mathpix](https://docs.mathpix.com/) a [Mistral OCR](https://docs.mistral.ai/studio/document-processing/basic_ocr): externí kandidáti pro navazující rozhodnutí o matematice/struktuře. Deklarované schopnosti poskytovatelů nejsou ověřením přesnosti na českých studentských materiálech. Žádný poskytovatel ani upload není zvolen či autorizován.

Pro plán: zachovat originál i stránkový původ, oddělit nativní text a OCR, hlásit částečné selhání, omezit renderovací/OCR rozpočty a vyhodnotit pilot na ručně ověřených ukázkách. OCRmyPDF samo neřeší rukopis a přidání prohledávatelné PDF vrstvy není totéž co generování nového PDF ze stránky wiki.

Po zjištění těchto variant uživatel zvolil lokální OCR nebo vidění modelu připojeného klienta, nikoliv další OCR službu. Externí poskytovatelé výše jsou záznamem zvažovaných možností, ne doporučenou závislostí výsledného plánu. Obrázky předané modelu klienta se mohou zpracovávat vzdáleně podle jeho poskytovatele.

## Cíloví klienti — dostupnost a plán ověření

| Klient | Ověřený místní stav | Primární podklad a dopad |
|---|---|---|
| Codex | CLI 0.167.0; `codex mcp add --help` potvrzuje stdio command i URL | [OpenAI Docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [CLI dokumentace](https://developers.openai.com/codex/mcp/); konkrétní spouštěcí příkaz ověřit v čistém profilu |
| Claude Code | CLI 2.1.295, lokální MCP help | [Claude Code MCP](https://code.claude.com/docs/en/mcp#option-3-add-a-local-stdio-server); nativní stdio |
| OpenCode | CLI v2.2.6, lokální MCP help | [OpenCode MCP](https://opencode.ai/docs/mcp-servers/); současný formát v2 má `mcp.servers`; ověřit i Code Mode/deferred discovery |
| pi | Příkaz `pi` není v PATH | [README původního projektu](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/README.md) odkazuje na earendil-works/pi; [současná MCP dokumentace](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/mcp.md) uvádí vestavěné MCP. Pro plán předpokládáme tuto současnou distribuci; uživatelova konkrétní verze není potvrzena |
| Google Antigravity | CLI `agy` 1.5.2, stdio/http potvrzeno helpem; `antigravity` v PATH není | [Google MCP](https://antigravity.google/docs/mcp), [headless CLI](https://antigravity.google/docs/cli/headless/); CLI a GUI/IDE ověřovat odděleně |

MCP konfigurace ani modelová autentizace jednotlivých klientů se nečetly a žádný server se neregistroval. Pi je možné v implementační fázi nainstalovat podle explicitního oprávnění uživatele instalovat potřebné nástroje; samotná instalace ale neprokáže dostupnost modelového účtu. Funkční GUI relace Antigravity nebyla potvrzena.

Antigravity dokumentace aktuálně uvádí globální `~/.gemini/config/mcp_config.json` a projektový `.agents/mcp_config.json`; starší cesty z referenčního README nekopírovat bez ověření verze. Pi dokumentuje výchozí timeout 60 s s progress prodlužováním, Antigravity 180 s a konfigurovatelné `timeoutSeconds`; dlouhé OCR proto dělit do omezených volání a skutečně ověřit přerušení/progress. Tyto hodnoty nejsou univerzální pro všechny verze.

Ověření každého klienta musí odlišit: (1) konfiguraci a protokol, (2) modelové volání nástrojů a (3) vizuální OCR. Běžný úspěšný textový MCP test nedokazuje, že konkrétní model umí přečíst vrácený obrázek. Pokud není dostupná GUI relace/modelová autentizace, výsledek bude výslovně označen jako neprovedený, nikoliv nahrazen tvrzením z dokumentace.

## Referenční projekt `../courses-mcp`

| Oblast | Ověřený stav |
|---|---|
| Stack | Python, `mcp>=2,<3`, requests, BeautifulSoup, markdownify, python-dotenv (`requirements.txt:1`) |
| Architektura | `mcp_server.py:14`, konfigurace `courses/config.py:7`, společná třída HTTP/auth/parser/cache/search/download v `courses/client.py:15` |
| MCP | 6 nástrojů, 3 resources; stdio a volitelné streamable-http |
| Auth | CTU OAuth; cookies z prostředí, automatické obnovení, zápis cookies do `.env` (`courses/client.py:68`) |
| Životní cyklus | Nová konfigurace, klient a session pro každé volání (`mcp_server.py:22`) |
| Konfigurace | `.env` má `override=True`, relativní cache vázána na projekt (`courses/config.py:33`) |
| Navigace | Parsování sidebaru, plochý seznam; normalizace kódů odstraňuje suffix za tečkou (`courses/client.py:226`) |
| Obsah | Obecné selektory main/article/div/body a markdownify (`courses/client.py:286`) |
| Hledání | Sekvenční průchod stránkami předmětu a substring search; Markdown cache (`courses/client.py:320`) |
| Cache | Bez TTL, revizí, účtu nebo metadat úplnosti; kolizní nahrazení lomítek podtržítky |
| Download | Stream po 8192 B; bez omezení velikosti, MIME/login kontroly a atomického dokončení (`courses/client.py:372`) |
| Chyby | Textové návratové hodnoty „Error …“, bez explicitního strukturovaného chybového kontraktu |
| Testy/balení | V tracked souborech nejsou testy, CI, lockfile, Docker ani pyproject.toml |

Převzít tenkou MCP vrstvu, společnou aplikační logiku pro tools/resources, navigační workflow a popis rozdílu oficiálního portálu a studentské wiki. Opravit v novém návrhu zejména HTTP timeouty, detekci login HTML, bezpečnost lokálních cest, stránkování, auth/session lifecycle, čerstvost cache a pravdivé hlášení neúplných výsledků.

Referenční download skládá lokální cestu z nevalidovaných vstupů (`mcp_server.py:190`, `courses/client.py:372`); `../` může uniknout mimo downloads. Toto je důvod pro ověření cesty a přílohové identity v novém serveru, nikoliv rozšíření této práce o opravu jiného projektu.

`../courses-mcp/AGENTS.md` popisuje také údajný server fitwiki s deseti nástroji včetně batch scrapingu a PDF generování. Jeho implementace v prozkoumaném checkoutu není. Text tedy neprokazuje existující API ani uživatelem schválený rozsah; kompatibilita s těmito názvy není automatický požadavek.

## MCP: aktuální primární zdroje

- [Python SDK](https://py.sdk.modelcontextprotocol.io/): dokumentuje současnou stabilní řadu v2, Python 3.11+ a MCPServer.
- [Protokolové verze SDK](https://py.sdk.modelcontextprotocol.io/protocol-versions/): odlišuje současné server/discover od staršího initialize a popisuje kompatibilitu. Integrační ověření se musí řídit skutečným klientem.
- [Specifikace](https://modelcontextprotocol.io/specification/2026-07-28), [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [transporty](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports): ověřeny 2026-11-08; při zahájení implementace zkontrolovat soulad zamčené SDK verze s cílovým klientem.
