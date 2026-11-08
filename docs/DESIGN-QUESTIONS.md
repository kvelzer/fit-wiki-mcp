# Rozhodovací strom

Stav 2026-11-08. Tento soubor odděluje potvrzené odpovědi od doporučení. Další kolo obsahuje všechny otázky, jejichž předpoklady jsou již vyřešené; otázky závislé na otevřené odpovědi počkají.

## Potvrzeno uživatelem

- Q1: hlavní cíl je najít předmět, projít materiály, hledat a číst konkrétní stránku či přílohu s odkazem na zdroj.
- Q2: začít osobním lokálním MCP přes stdio. Rozdíl proti HTTP byl vysvětlen a uživatel potvrdil doporučení.
- Q3: wiki pouze číst, lokální ukládání dovoleno; bez úprav wiki, komentářů a uploadů.
- Q4: celý katalog a oba rozsahy hledání, globálně ve studijní části i s omezením na předmět.
- Q5: OCR skenů je nutné už v první verzi. Doporučení odložit OCR nebylo přijato; kvalita pro ruční písmo a matematiku a způsob zpracování jsou navazující rozhodnutí.
- Q6: hromadný offline archiv a generování nových PDF odložit po první verzi.
- Q7: soukromá disková cache dle účtu s TTL a refresh; cookies v paměti, stale při síťové chybě označit, při zamítnutí práv chyba.
- Q8: Codex, Claude Code, OpenCode a pi; následně uživatel doplnil Google Antigravity.
- Q9: OCR zahrne rukopis a matematiku včetně LaTeXu, s originálem a označením nejistot.
- Q10: lokální OCR nebo vidění modelu připojeného klienta. Samostatná externí OCR služba není zvolená.
- Q11: OCR na vyžádání; hledání doplnit o už získané texty a neúplnost lokálního indexu uvádět.
- Existující `.env` smí být použit pro přihlášený průzkum a následný MCP. Hodnoty se nezapisují do dokumentace.

## Strom navazujících rozhodnutí

```text
Cíl: studijní asistent [potvrzeno]
├── Rozsah materiálů [potvrzeno]
│   ├── celý katalog
│   ├── textové PDF + OCR rukopisu a matematiky
│   │   └── lokální OCR nebo vidění modelu klienta
│   └── hromadný archiv a generování PDF později
├── Hledání [potvrzeno]
│   ├── globální studijní část + omezení na předmět
│   └── wiki fulltext + dosud získané OCR texty
├── Provoz: osobní stdio [potvrzeno]
│   ├── Codex, Claude Code, OpenCode, pi, Google Antigravity
│   └── disková cache dle účtu, cookies v paměti, označený stale
└── Oprávnění: čtení a místní ukládání [potvrzeno]
    ├── konkrétní úložiště a limity: návrh PLAN.md
    └── první verze stahuje ověřená wiki média; externí zdroje vrátí jako odkazy [technický návrh k závěrečné kontrole]

Uzavření: kontrola scénářů, omezení a potvrzení společného porozumění.
```

## Druhé kolo — průběžný stav

| Otázka | Doporučení předložené uživateli | Předpoklad |
|---|---|---|
| Q4: rozsah katalogu a hledání — potvrzeno | Celý katalog; studijní část wiki globálně i po předmětu, primárně wiki search s pravdivou informací o úplnosti | Q1 potvrzeno, endpoint search ověřen; filtrování/stránkování zůstává technickým průzkumem |
| Q5: čtení příloh — změna proti doporučení | Uživatel vyžaduje OCR skenů již v první verzi; dořešit engine, ruční písmo/matematiku a kvalitu | Q1 a read-only rozsah potvrzeny, PDF stream ověřen |
| Q6: exporty — potvrzeno | Hromadný archiv a generování nových PDF odložit | Q1 potvrzeno; jednotlivý download v rozsahu |
| Q7: lokální data — potvrzeno | Soukromá disková cache dle účtu, TTL/refresh, cookies jen v paměti; stale při síťové chybě označit, při zamítnutí práv chyba | Osobní stdio a lokální ukládání potvrzeno |
| Q8: klienti — rozšířeno uživatelem | Codex, Claude Code, OpenCode, pi a Google Antigravity | Q2 potvrzeno |

Q4–Q8 jsou zodpovězené. Textová extrakce PDF a OCR jsou záměrně samostatná otázka: download souboru neznamená, že asistent už obdržel jeho obsah.

## Navazující kola OCR — uzavřená produktová rozhodnutí

Q9–Q11 jsou zodpovězené podle zápisu výše. Technický návrh předává vybranou stranu jako obrazový výsledek MCP vidícímu modelu klienta; asistent přepisuje a může přepis uložit zpět s původem. Model bez vidění dostane lokální OCR a výslovné omezení u rukopisu/matematiky, nikoliv falešný příslib stejné kvality.

## Závěrečná kontrola společného porozumění

Uživatel potvrdil společné zadání pokynem „pokud je plan prirpaveny, tak zacni implementaci“. Rozhovor je uzavřený a implementace autorizovaná. Rutinní technická rozhodnutí a výsledky pilotu se řeší v implementaci; zásadní změna rozsahu by se vrátila do návrhu.

## Stav doporučení

Technické členění, jména nástrojů, TTL, síťové limity a resource URI v PLAN.md jsou pracovní návrhy. Nejsou tvrzením o existující implementaci ani již odsouhlaseným veřejným API. Před zveřejněním kontraktu se uzavřou související produktové volby; rutinní implementační detaily se řeší technickým úsudkem a ověřením.
