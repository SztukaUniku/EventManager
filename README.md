# EventManager

Prywatny przewodnik po niszowych wydarzeniach kulturalnych w Warszawie i okolicach.

## Co tu jest

- `sources/sources.csv` – lista źródeł (domy kultury, agregatory, muzea, galerie, kina).
- `scripts/probe_sources.py` – test wykonalności: sprawdza, które źródła da się czytać automatycznie i jak.
- `.github/workflows/probe-sources.yml` – uruchamia test na serwerze GitHuba.
- `reports/` – wyniki testów.

## Zasady

- Nie zmyślamy wydarzeń: każde ma link do źródła.
- Szanujemy `robots.txt` i odczytujemy strony spokojnym tempem.
- Preferencje użytkowniczki zostają na jej telefonie, nie w tym repozytorium.
