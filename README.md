# FIT Wiki MCP

Osobní MCP server pro **studentskou, neoficiální [FIT Wiki](https://fit-wiki.cz/)**. Umí katalog předmětů, strom studijních stránek včetně státnic, navigaci podle sekcí, čtení stránek v Markdownu, diskuse pod stránkami, fulltext, stahování příloh, lokální OCR a předání obrázků modelu klienta pro rukopis a matematiku. Wiki nikdy neupravuje.

## Instalace

Ověřeno na Linuxu a Pythonu 3.14; balíček vyžaduje Python 3.11+. Z kořene projektu:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
```

Pro čtení PDF, renderování a lokální OCR potřebuješ Poppler a Tesseract s jazykovými daty. Na Ubuntu/Debianu:

```bash
sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-ces tesseract-ocr-eng
```

Navigace, stránky a hledání fungují i bez systémových OCR nástrojů. Chybějící nástroj vrátí konkrétní `DEPENDENCY_MISSING`.

## Přihlášení a spuštění

Do soukromého `.env` vlož údaje účtu **FIT Wiki**:

```dotenv
FITWIKI_USERNAME=tvuj_wiki_ucet
FITWIKI_PASSWORD=tvuj_wiki_password
```

Podporované jsou i existující aliasy `COURSES_USERNAME` a `COURSES_PASSWORD`. Jde o formulářový login na wiki, nikoliv o OAuth portálu courses. Explicitní proměnné procesu mají přednost před `.env`; v rámci stejného zdroje mají názvy `FITWIKI_*` přednost před aliasy. Cookies zůstávají pouze v paměti.

```bash
.venv/bin/python mcp_server.py --doctor
.venv/bin/python mcp_server.py
```

Druhý příkaz spustí stdio server a čeká na MCP zprávy. Logy chodí na stderr. Launcher najde `.env` podle umístění projektu i při jiném pracovním adresáři. U instalovaného `fitwiki-mcp` nastav `FITWIKI_ENV_FILE` na absolutní cestu, pokud není `.env` v pracovním adresáři.

## Klienti

Návody a výsledky ověření pro **Codex, Claude Code, OpenCode v2, pi a Google Antigravity** jsou v [docs/CLIENTS.md](docs/CLIENTS.md). Konkrétní fragment s absolutními cestami vygeneruješ takto:

```bash
.venv/bin/python scripts/client_config.py codex
.venv/bin/python scripts/client_config.py claude
.venv/bin/python scripts/client_config.py opencode
.venv/bin/python scripts/client_config.py pi
.venv/bin/python scripts/client_config.py antigravity
```

Generátor jen vypíše konfiguraci; fragment sluč se stávající konfigurací klienta. Hesla se do klientských konfigurací nekopírují.

## Nástroje a workflow

| Nástroj | Použití |
|---|---|
| `list_courses(query?, cursor?, limit?, refresh?)` | Úplný stránkovaný katalog; vyhledání kódu/názvu, zachování `.21` a jazykových variant |
| `get_namespace_index(namespace?, cursor?, limit?, refresh?)` | Přímé podstránky a podnamespaces ve studijním stromu; výchozí `škola` |
| `get_course_index(course_id, cursor?, limit?, refresh?)` | Hierarchie sekcí a seznam odkazů předmětu |
| `list_pages(course_id, section_id?, cursor?, limit?, refresh?)` | Odkazy vybrané sekce včetně podsekcí, stránek i příloh |
| `get_page(page_id, section?, cursor?, max_chars?, refresh?)` | Markdown, zdroj a pokračování dlouhé stránky |
| `get_comments(page_id, author?, comment_id?, cursor?, limit?, max_chars?, refresh?)` | Komentáře včetně autora, data, odpovědí, skrytého obsahu a příloh |
| `search(query, course_id?, cursor?, limit?, refresh?)` | Wiki fulltext a již získané přepisy; bez předmětu studijní namespace `škola` |
| `download_attachment(attachment_id, refresh?)` | Originál přílohy v soukromém lokálním úložišti |
| `read_attachment(attachment_id, page?, mode?, max_chars?, cursor?)` | Jedna strana PDF/obrázek: uložený přepis, nativní text nebo lokální OCR |
| `get_material_image(attachment_id, page?, region?)` | Skutečný obrazový blok MCP pro model klienta, plus hash originálu |
| `save_transcription(attachment_id, page, text, source_hash, model?, partial?)` | Uložení neověřeného přepisu modelu lokálně pro další čtení/hledání |

Začni `list_courses(query="BI-DBS")`, použij vrácené `course_id` v `get_course_index`, vyber sekci a načti stránku či přílohu z vráceného odkazu. Identifikátory předávej přesně, například `škola:předměty:bi-dbs`; neodvozuj URL jen ze zkratky.

Seznamy vracejí `next_cursor`, dlouhý text rovněž. Kurzor je vázaný na dotaz, obsah a proces serveru; po restartu či změně obsahu začni znovu bez něj. `read_attachment` používá čísla stran od 1 a vrací `next_page`. `mode` je `auto`, `native` nebo `local_ocr`.

Fulltext přijímá běžná slova a uvozované fráze, nikoliv operátory pro změnu namespace. Vlastní index předmětu se prohledává zvlášť, protože jej wiki namespace filtr nezahrnuje. Výsledek rozlišuje `wiki_fulltext`, `course_index` a `local_transcription`. Pole `metadata.partial` upozorňuje, že OCR index pokrývá jen již zpracované materiály a úplnost cizího wiki indexu nelze zaručit.

### Strom stránek mimo katalog předmětů

`get_namespace_index(namespace="škola")` vrací přímé podnamespaces a stránky. U položky `kind="namespace"` použij `namespace_id` v dalším volání stejného nástroje, u `kind="page"` použij `page_id` v `get_page` nebo `get_comments`. Například `namespace="škola:státnice"` zpřístupní státnicové archivy nezávisle na katalogu předmětů. `namespace="škola:předměty:bi-pst"` projde index stránek PST i tam, kde na ně jeho přehled neodkazuje.

Výsledek obsahuje jen přímé potomky viditelné účtu, podporuje kurzor/refresh a nespouští rekurzivní crawl. Prázdný výsledek vrací `namespace_exists=null`, protože neprokazuje existenci namespace ani absenci skrytých stránek. HTTP operace používá ověřený čtecí POST `call=index`; samotný GET do AJAX endpointu vrací nesprávně kořen stromu.

Externí odkazy, které wiki zabalila jako `fetch.php?media=https…`, se vracejí jako odkazy na skutečný externí cíl i v Markdownu. Nejsou vydávány za interní přílohy a server je nestahuje s wiki přihlašovacími údaji.

### Komentáře a obrázky v diskusi

Diskuse se čte samostatně přes `get_comments`, protože export používaný pro `get_page` ji neobsahuje. Například:

```json
{
  "page_id": "škola:předměty:bi-pst:pst_test_2023-10-11_novak-11-00"
}
```

Autor se filtruje podřetězcem bez ohledu na velikost písmen a diakritiku. `comment_id` vybere konkrétní komentář. Výsledek obsahuje `comment_id`, `parent_id` odpovědi, `author`, `published_at`, Markdown a přímý odkaz na komentář. Neuvedený autor nebo čas jsou `null`. Do textu se zahrne i rozbalovací obsah, ovládání formulářů a přepínače se odstraní.

Přílohy jsou v `attachments` s hotovým `attachment_id` pro `read_attachment` nebo `get_material_image`; samotný seznam komentářů jejich obrazový obsah nepřepisuje. Odkaz komentáře na médium se zaznamená pro předmětové hledání získaných přepisů.

`limit` omezuje počet vrácených částí (1–20, výchozí 10), `max_chars` délku jedné části (100–10 000, výchozí 5000). Dlouhý komentář má opakované ID a pole `part`/`parts`; přes `next_cursor` lze získat celý text. `total` je počet komentářů po filtrování, `page_total` počet všech komentářů stránky a `total_parts` počet částí po rozdělení. Filtr autora nezahrne automaticky odpovědi jiných autorů; jejich vazby zůstávají v `parent_id`.

`discussion_available=false` odlišuje stránku bez dostupné diskuse od dostupné prázdné diskuse. Nerozpoznané nebo poškozené rozložení vrátí `PARSE_ERROR` místo tichého vynechání příspěvků. Cache diskuse platí nejvýše 5 minut, `refresh=true` vynutí nové čtení. Wiki fulltext nepovažuj za úplné hledání v komentářích; k jejich čtení slouží tento nástroj. Publikování komentářů není součástí API.

### OCR a model s viděním

1. `read_attachment` nejdřív využije text PDF. U skenu/obrázku použije lokální Tesseract `ces+eng`; smíšená PDF označí varováním o rastrovém obsahu.
2. Pro rukopis, vzorce, diagramy nebo nejistý výsledek zavolej `get_material_image`. Vrací obrazový blok, ne pouze cestu či base64 v textu.
3. Model **připojeného klienta** přepíše obraz do Markdown/LaTeXu, označí nečitelné části a uloží přepis přes `save_transcription` s vráceným `source_hash`.
4. U výřezu nastav `partial=true`. Částečný přepis nepřepíše celostránkový záznam. Přepisy jsou vždy `verified=false` a originál zůstane dostupný.

`region` je `[left, top, right, bottom]` v rozsahu 0..1. Obraz pro klienta má nejvýše 2000 px na delší straně; pro drobné písmo použij výřez. Lokální render/OCR běží po jedné straně a s omezeným časem, velikostí a souběžností. Nečitelný sken může vrátit `status=needs_vision` místo vymyšleného textu.

Server nevolá samostatné OCR API. Model klienta však může běžet u vzdáleného poskytovatele; tato cesta proto není zárukou lokálního zpracování. Bez modelu s viděním je k dispozici lokální OCR a originál, kvalita rukopisu/matematiky tím není garantovaná. [Rozhodnutí a kompromisy](docs/adr/0001-ocr-local-or-client-vision.md).

## Data, cache a limity

Výchozí úložiště je `~/.cache/fitwiki-mcp/<account-hash>/`, mimo repozitář. Adresáře mají oprávnění 0700, soubory 0600; zvolené existující úložiště musí být soukromé. Účet, reprezentace, původní obsah a verze parseru/OCR konfigurace oddělují záznamy. Vazba na přečtené stránky umožňuje předmětové hledání i v přílohách uložených ve společném namespace. Server odmítá cizí URL, jiné wiki akce, nebezpečné lokální cesty a symlinky. Externí odkazy vrací jako odkazy.

Výchozí TTL: katalog/index 24 h, stránky a originály příloh 1 h, hledání 5 min. `refresh=true` vynutí obnovu tam, kde jej nástroj nabízí. Při síťovém výpadku může vrátit označenou starší kopii; při zamítnutí přístupu či selhání přihlášení se na cache neodvolává jako na úspěšné online čtení. Čerstvá cache se v rámci TTL nemusí znovu dotazovat na změny oprávnění.

Limity: 1 HTTP požadavek/s, HTML 5 MiB, příloha 50 MiB, seznam do 50 položek, textový blok do 30 000 znaků. Široké hledání wiki může stáhnout mnoho výsledků najednou; MCP stránkuje získaný seznam lokálně. Místní OCR index má limit 5000 záznamů a pokrývá pouze získané texty.

Volby prostředí a aliasy jsou v [.env.example](.env.example). `FITWIKI_DATA_DIR` nastaví soukromý datový adresář; `FITWIKI_REQUEST_INTERVAL`, `FITWIKI_PAGE_TTL`, `FITWIKI_INDEX_TTL`, `FITWIKI_SEARCH_TTL` a `FITWIKI_OCR_LANGUAGES` upraví chování. Server cookies neukládá a `.env` nepřepisuje.

## Resources

`fitwiki://courses`, `fitwiki://courses/{course_id}/index`, `fitwiki://pages/{page_id}`, `fitwiki://pages/{page_id}/comments` a `fitwiki://namespaces/{namespace_id}` vracejí JSON ze stejné služby jako nástroje. Dvojtečky v identifikátoru lze zakódovat jako `%3A`. Pro stránkování použij nástroje; základní workflow nezávisí na podpoře resources klientem.

## Ověření a řešení chyb

```bash
.venv/bin/ruff check src tests scripts mcp_server.py
.venv/bin/pytest -q
.venv/bin/python scripts/live_smoke.py --live
.venv/bin/python scripts/live_smoke.py --live --mode legacy
```

Běžné testy jsou offline a používají syntetické fixtures. Live test je explicitní a využije `.env`; vypisuje jen technická metadata. [Skutečně provedené ověření a limity](docs/VALIDATION.md).

Chyby nástroje mají `isError=true` a JSON s `error.code`, `message` a `retryable`. `AUTH_REQUIRED` znamená chybějící údaje/session, `AUTH_FAILED` neúspěšný login, `ACCESS_DENIED` zamítnutý přístup, `NOT_FOUND` chybějící materiál. `INVALID_CURSOR` vyřeš novým požadavkem bez kurzoru; `TOO_LARGE` užším rozsahem; `BUSY` opakováním po skončení jiného renderu. `PROCESS_TIMEOUT` nebo nečitelný lokální OCR řeš menším rozsahem či vision cestou. Stav HTTP 200 server nepovažuje automaticky za úspěšné čtení.

Obsah wiki je neoficiální. U požadavků, klasifikace a aktuálních oznámení ověř oficiální courses portál. Licence a případné výjimky zůstávají vlastností originálních materiálů. Hromadný archiv, generování nových PDF, samostatná OCR služba a sdílené HTTP hostování jsou mimo tuto verzi.

## Licence

Zdrojový kód a dokumentace projektu jsou dostupné pod [licencí MIT](LICENSE), Copyright (c) 2026 kvelzer. Licence projektu se nevztahuje na obsah FIT Wiki ani stažené materiály; ty si zachovávají vlastní licence a podmínky.
