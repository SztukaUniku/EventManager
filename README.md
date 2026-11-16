# EventManager

Prywatny przewodnik po niszowych wydarzeniach kulturalnych w Warszawie i okolicach.
Aplikacja na telefon (PWA) + automat, który co tydzień zbiera wydarzenia.

## Jak to działa

1. **Zbieranie** (`.github/workflows/collect.yml`, czwartek rano): `collector/collect.py` odczytuje
   źródła z `collector/sources.py` — gotowe dane (schema.org, API kalendarza WordPress) albo
   migawki stron zapisane w `data/snapshots/`.
2. **Odczyt migawek**: `collector/parsers.py` ma osobny parser dla każdej strony, więc
   nie potrzeba AI ani opłat. Zmiana układu strony = poprawka parsera.
3. **Reguły** (`collector/rules.py`): dni wolne, godziny (dzień roboczy 17:00–23:00), wykluczenia
   (dzieci, seniorzy, karaoke, disco polo, metal, kabaret, tańce towarzyskie, patriotyczne,
   komercyjne, sport i kursy), tagi i kategorie.
4. **Budowa** (`collector/build.py`): scala, usuwa duplikaty, zapisuje `app/data/*.json`.
5. **Publikacja** (`.github/workflows/pages.yml`): aplikacja z folderu `app/` trafia na GitHub Pages.

## Zasady

- Nie zmyślamy wydarzeń: każde ma link do źródła; czego nie da się potwierdzić, trafia do „Do sprawdzenia”.
- Szanujemy `robots.txt` i czytamy strony spokojnym tempem, raz w tygodniu.
- Preferencje użytkowniczki („nie dla mnie”) zostają w jej przeglądarce, nie w tym repozytorium.

## Ręczne uruchomienie

Zakładka **Actions** → „Zbieranie wydarzeń” → **Run workflow**.
