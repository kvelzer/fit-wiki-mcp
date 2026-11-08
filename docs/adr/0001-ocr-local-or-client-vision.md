# OCR lokálně nebo prostřednictvím modelu klienta

První verze musí číst i skeny s rukopisem a matematikou, přičemž běžné lokální OCR samo tento požadavek neprokazuje. Podle uživatelovy volby použijeme lokální nástroje a vidění modelu připojeného klienta; server nebude záviset na samostatné externí OCR službě s dalším API klíčem a účtováním.

Server připraví omezený obrázek vybrané strany, klientův model vytvoří přepis a může jej uložit zpět pro lokální hledání. To vyžaduje vícekolové workflow a ověření obrazových výsledků v jednotlivých klientech; u modelu bez vidění nebude garantována srovnatelná kvalita rukopisu a matematiky. Originál, číslo strany a původ přepisu zůstávají dostupné a přijatý přepis není automaticky ověřený.

Vidění používá poskytovatele modelu zvoleného v klientu: zpracování klientovým modelem nemusí být lokální. Tato architektura neznamená slib, že obrazová data zůstanou na počítači; server sám neprovádí další upload do zvláštní OCR služby.
