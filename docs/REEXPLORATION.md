# Opakovaný průzkum a plán vylepšení — 2026-11-08

Rozsah: přihlášený, omezený průzkum studijní části FIT Wiki, srovnání s MCP 0.1.1 a ověření ve skutečném prohlížeči. Účet je používán pouze pro čtení; soukromé materiály, HTML, cookies a přihlašovací údaje nejsou fixtures ani součást tohoto dokumentu.

## Ověřená zjištění před implementací

| Oblast | Pozorování | Mezery serveru |
|---|---|---|
| Strom wiki | AJAX `call=index` čte namespace z POST pole `idx`. GET vrací kořen, nikoliv požadované podstránky. Na vzorku `škola` 38 položek, `škola:státnice` 94, `škola:předměty:bi-pst` 318 | Katalog a odkazy na indexu předmětu nepředstavují celý strom; chybí přímé procházení studijních namespaces a státnic |
| Externí média | PST obsahuje odkazy na Overleaf zabalené do `lib/exe/fetch.php?media=https…` | Normalizace je zahazuje jako neplatné ID média; mají zůstat externími odkazy a nesmějí se stahovat s wiki session |
| Výběr obsahu | Na běžné stránce `škola` současný CSS union vybere vnější `body.dokuwiki` s třemi navigacemi | Pořadí selektorů v CSS seznamu není priorita; izolace hlavního obsahu musí být explicitní |
| HTTP hranice | Kontrola akcí zkoumá query URL, ale ne query předanou přes `params` ani POST payload | Před přidáním čtecího POST indexu sjednotit kontrolu všech skutečně odesílaných parametrů a povolit jen konkrétní login/index operace |
| Diskuse | Předchozí živé ověření komentáře PST funguje včetně skryté přílohy | Zachovat jako regresní scénář; index ani export nesmí být mylně vydáván za hledání všech komentářů |

Rozhraní indexu odpovídá čtecí větvi `callIndex` v [primárním zdrojovém kódu DokuWiki](https://github.com/dokuwiki/dokuwiki/blob/master/inc/Ajax.php). Výsledky GET a POST byly ověřeny samostatně; úspěšný HTTP status sám neprokazuje správný namespace.

## Plán provedení

1. Přidat kořenový `AGENTS.md`: účel, skutečná architektura, hranice čtení, ochrana údajů, testovací příkazy, MCP kontrakty a pravidla průzkumu.
2. Doplnit bezpečnou čtecí operaci indexu: pouze POST na přesný AJAX endpoint s `call=index` a validovaným studijním namespace. Parametry `do` kontrolovat v URL, query i těle před prvním požadavkem i při přesměrování.
3. Přidat `get_namespace_index` a resource se stránkováním přímých podstránek/podnamespaces. Žádná automatická rekurze ani crawl; identifikátory vycházejí z ověřených odkazů, výstup zůstává v `škola`.
4. Opravit výběr kontejneru podle priority a zachovat externí odkazy zabalené jako média. Změnit verzi parser cache, aby opravený parser nepoužil staré chybné výsledky.
5. Ověřit v Playwrightu rozbalování indexu, běžnou stránku, rozbalovací komentář a původní obrazovou přílohu. Přenášet autentizaci jen v paměti, bez sledovacích záznamů či autentizačních dumpů.
6. Přidat syntetické regresní fixtures/testy pro index, bezpečnost parametrů, externí media odkazy a výběr hlavního obsahu. Spustit offline testy, současný i legacy stdio a malý živý scénář.
7. Aktualizovat README, schémata, instrukce serveru, verzi a validační report. Výslovně odlišit ověřenou funkci od omezení. Repozitář musí zůstat bez údajů z `.env` a soukromých materiálů.

## Hranice změny

Historie revizí, editace, uploady, profily uživatelů, hromadný archiv, další OCR API a sdílené HTTP hostování se nepřidávají. Čtecí POST indexu není publikování obsahu. Externí odkaz se pouze vrací, jeho obsah se pod wiki účtem nenačítá. Průzkum neznamená záruku pokrytí všech pluginů nebo všech stránek wiki.

## Provedení a výsledek

Všech sedm kroků bylo dokončeno ve verzi **0.2.0**. Přibyl [AGENTS.md](../AGENTS.md), stránkovaný nástroj `get_namespace_index` a resource `fitwiki://namespaces/{namespace_id}`. Opravené externí cíle jsou zachovány i v Markdownu, hlavní obsah se vybírá podle explicitní priority a změna verze cache zneplatní staré parsované výsledky. HTTP hranice kontroluje skutečnou URL, query i POST payload a odmítá jiné AJAX operace; čtecí POST podporuje obnovu session a omezené opakování při výpadku.

Živý SDK scénář prošel s automatickým protokolem `2026-07-28` i legacy `2025-11-25`: discovery 11 nástrojů, celý katalog 287 předmětů, tři výše uvedené namespaces, čtení tří předmětů, fulltext, PDF, obrazový blok a diskuse včetně přílohy/odpovědi. Samostatná kontrola prázdného namespace potvrdila `namespace_exists=null`.

Skutečný prohlížeč Playwright / Chromium 156.0.8078.4 potvrdil přihlášení, rozbalení `škola` a `škola:státnice` pomocí POST `call=index`. Ve stránce s dvěma komentáři byl obrazový obsah komentáře před kliknutím skrytý a po rozbalení viditelný; obsahoval jeden obrázek. Prohlížeč nepředával autentizaci externím doménám a neukládal profil, cookies, screenshoty ani trace do repozitáře.

Offline sada: **77 passed**. Prošly lint, formátování a sestavení balíčku. Syntetické testy zahrnují strukturované MCP výsledky/resource, stránkování a cache indexu, chybný scope/markup, prioritu kontejneru, externí cíle a ochranu HTTP operací. Souhrnný report je v [VALIDATION.md](VALIDATION.md).

Průzkum byl reprezentativní, nikoliv úplný crawl. Dvě vzorkované stránky s matematickým obsahem neobsahovaly prvky MathML/latex skriptů; nelze z toho odvozovat úplné pokrytí matematických pluginů na celé wiki. Hledání dosud neotevřených skenů ani všech komentářů se netvrdí. Strom vrací přímé viditelné potomky; prázdný výsledek nepotvrzuje existenci namespace ani přístup ke skrytým stránkám.
