"""Aktywne źródła zakładki NISZOWE.

adapter:
  jsonld   – strona publikuje wydarzenia jako dane strukturalne schema.org Event
  tribe    – WordPress z wtyczką The Events Calendar (gotowe API)
  snapshot – zwykła strona; zapisujemy oczyszczony tekst, a wydarzenia wyciąga z niego AI

pages:    strony z programem do zapisania (dla snapshot) lub odczytu (dla jsonld)
discover: słowa w adresie lub opisie linku, po których szukamy podstron z programem
"""

SOURCES = [
    {
        "id": "kulturalnie", "name": "kulturalnie.waw.pl", "area": "Warszawa",
        "adapter": "jsonld", "pages": ["https://kulturalnie.waw.pl/"],
        "discover": ["bezplatne", "tanie", "weekend", "wydarzenia", "koncerty", "wystawy", "teatr"],
    },
    {
        "id": "waw4free", "name": "waw4free", "area": "Warszawa",
        "adapter": "snapshot", "pages": ["https://waw4free.pl/"],
        "discover": ["koncert", "impre", "wystaw", "teatr", "spotkan", "warsztat", "kategoria"],
    },
    {
        "id": "muzea", "name": "muzea.waw.pl (wystawy)", "area": "Warszawa",
        "adapter": "snapshot", "pages": ["https://muzea.waw.pl/en/exhibitions/"],
        "discover": [],
    },
    {
        "id": "alternatywy", "name": "UCK Alternatywy", "area": "Ursynów",
        "adapter": "snapshot", "pages": ["https://alternatywy.art/"],
        "discover": ["repertuar", "kalendarz", "program", "wydarzenia"],
    },
    {
        "id": "terminal", "name": "Terminal Kultury Gocław", "area": "Praga-Południe",
        "adapter": "tribe", "pages": ["https://terminalkultury.pl"],
    },
    {
        "id": "lowicka", "name": "Centrum Łowicka", "area": "Mokotów",
        "adapter": "tribe", "pages": ["https://lowicka.pl"],
    },
    {
        "id": "kulturalni", "name": "CK Piaseczno (kulturalni.pl)", "area": "Piaseczno i okolice",
        "adapter": "tribe", "pages": ["https://kulturalni.pl"],
    },
    {
        "id": "nowyteatr", "name": "Nowy Teatr", "area": "Mokotów",
        "adapter": "snapshot", "pages": ["https://nowyteatr.org/pl/kalendarz"],
        "discover": ["kalendarz", "program"],
    },
    {
        "id": "kadr", "name": "Dom Kultury Kadr", "area": "Mokotów",
        "adapter": "snapshot", "pages": ["https://dkkadr.waw.pl/repertuar/", "https://dkkadr.waw.pl/"],
        "discover": ["repertuar", "kalendarz"],
    },
    {
        "id": "sdk", "name": "Służewski Dom Kultury", "area": "Mokotów",
        "adapter": "snapshot", "pages": ["https://sdk.waw.pl/wydarzenia", "https://sdk.waw.pl/"],
        "discover": ["wydarzenia", "kalendarz", "repertuar"],
    },
    {
        "id": "domsztuki", "name": "Dom Sztuki SMB Jary", "area": "Ursynów",
        "adapter": "snapshot", "pages": ["https://domsztuki.art.pl/"],
        "discover": ["repertuar", "wydarzenia", "kino", "seanse", "kalendarz"],
    },
    {
        "id": "dks", "name": "Dom Kultury Śródmieście", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://dks.art.pl/"],
        "discover": ["kalendarz", "wydarzenia", "program"],
    },
    {
        "id": "teatrstudio", "name": "Teatr Studio i Galeria Studio", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://teatrstudio.pl/"],
        "discover": ["repertuar", "kalendarz", "galeria/wydarzenia", "wydarzenia"],
    },
    {
        "id": "msn", "name": "Muzeum Sztuki Nowoczesnej", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://artmuseum.pl/"],
        "discover": ["wydarzenia", "kalendarz", "program", "wystawy"],
    },
    {
        "id": "filharmonia", "name": "Filharmonia Narodowa", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://filharmonia.pl/"],
        "discover": ["kalendarz", "koncerty", "repertuar", "program"],
    },
]
