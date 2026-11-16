"""Aktywne źródła zakładki NISZOWE.

adapter:
  jsonld   – strona publikuje wydarzenia jako dane strukturalne schema.org Event
  tribe    – WordPress z wtyczką The Events Calendar (gotowe API)
  snapshot – zwykła strona; zapisujemy oczyszczony tekst, a wydarzenia wyciąga z niego AI

pages:    strony z programem do zapisania (dla snapshot) lub odczytu (dla jsonld);
          {m0_start}/{m0_end} i {m1_start}/{m1_end} to pierwszy i ostatni dzień bieżącego i następnego miesiąca
parser:   nazwa funkcji w collector/parsers.py, gdy stronę da się odczytać bez AI
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
        "parser": "waw4free", "adapter": "snapshot", "pages": ["https://waw4free.pl/warszawa-darmowe-koncerty", "https://waw4free.pl/warszawa-darmowe-imprezy", "https://waw4free.pl/warszawa-darmowe-teatr", "https://waw4free.pl/warszawa-darmowe-standup", "https://waw4free.pl/warszawa-darmowe-wystawy", "https://waw4free.pl/warszawa-darmowe-spotkania", "https://waw4free.pl/warszawa-darmowe-wyklady", "https://waw4free.pl/warszawa-darmowe-filmy", "https://waw4free.pl/warszawa-darmowe-warsztaty"],
    },
    {
        "id": "muzea", "name": "muzea.waw.pl (wystawy)", "area": "Warszawa",
        "adapter": "snapshot", "pages": ["https://muzea.waw.pl/en/exhibitions/"],
    },
    {
        "id": "alternatywy", "name": "UCK Alternatywy", "area": "Ursynów",
        "parser": "alternatywy", "adapter": "snapshot", "pages": ["https://alternatywy.art/"],
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
        "adapter": "snapshot", "pages": ["https://nowyteatr.org/pl/kalendarz?date_from={m0_start}&date_to={m0_end}", "https://nowyteatr.org/pl/kalendarz?date_from={m1_start}&date_to={m1_end}"],
    },
    {
        "id": "kadr", "name": "Dom Kultury Kadr", "area": "Mokotów",
        "adapter": "snapshot", "pages": ["https://dkkadr.waw.pl/repertuar/"],
    },
    {
        "id": "sdk", "name": "Służewski Dom Kultury", "area": "Mokotów",
        "adapter": "snapshot", "pages": ["https://sdk.waw.pl/wydarzenia/dla-kogo/dorosli"],
    },
    {
        "id": "domsztuki", "name": "Dom Sztuki SMB Jary", "area": "Ursynów",
        "adapter": "snapshot", "pages": ["https://domsztuki.art.pl/", "https://domsztuki.art.pl/kino"],
    },
    {
        "id": "dks", "name": "Dom Kultury Śródmieście", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://dks.art.pl/wydarzenia"],
    },
    {
        "id": "teatrstudio", "name": "Teatr Studio i Galeria Studio", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://teatrstudio.pl/pl/repertuar/", "https://teatrstudio.pl/"],
    },
    {
        "id": "msn", "name": "Muzeum Sztuki Nowoczesnej", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://artmuseum.pl/program", "https://artmuseum.pl/wystawy-aktualne"],
    },
    {
        "id": "filharmonia", "name": "Filharmonia Narodowa", "area": "Śródmieście",
        "adapter": "snapshot", "pages": ["https://filharmonia.pl/repertuar"],
    },
]
