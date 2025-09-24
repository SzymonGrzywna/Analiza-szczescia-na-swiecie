from flask import Flask, render_template, request, abort, make_response
import csv
import io

app = Flask(__name__)

SCIEZKA_DANYCH = "dane/dane_szczescie.csv"

def wczytaj_dane():
    #wczytanie CSV
    rekordy = []
    with open(SCIEZKA_DANYCH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rekordy.append({
                    "kraj": r["kraj"],
                    "wynik_szczescia": float(r["wynik_szczescia"]),
                    "pkb_na_osobe": float(r["pkb_na_osobe"]),
                    "zdrowe_zycie": float(r["zdrowe_zycie"]),
                })
            except Exception:
                continue
    return rekordy

DANE = wczytaj_dane()

@app.template_filter("plfloat")
def plfloat_wyswietl(v):
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except Exception:
        return str(v)

def posortuj(rekordy, klucz, malejaco=True):
    return sorted(rekordy, key=lambda r: r.get(klucz, 0), reverse=malejaco)

def filtruj_i_sortuj(args, dane_src):
    sortuj = args.get("sortuj", "wynik_szczescia")
    kierunek = args.get("kierunek", "malejaco")
    filtr_kraj = (args.get("kraj") or "").strip().lower()
    min_wynik = args.get("min_wynik")

    dane = dane_src
    if filtr_kraj:
        dane = [r for r in dane if filtr_kraj in r["kraj"].lower()]
    if min_wynik:
        try:
            prog = float(min_wynik)
            dane = [r for r in dane if r["wynik_szczescia"] >= prog]
        except Exception:
            pass

    if sortuj not in {"wynik_szczescia", "pkb_na_osobe", "zdrowe_zycie"}:
        sortuj = "wynik_szczescia"
    malejaco = (kierunek != "rosnaco")
    dane = posortuj(dane, sortuj, malejaco)
    return dane

@app.route("/")
def strona_glowna():
    top10 = posortuj(DANE, "wynik_szczescia", True)[:10]
    return render_template("strona_glowna.html", top10=top10)

@app.route("/ranking")
def ranking():
    dane = filtruj_i_sortuj(request.args, DANE)
    return render_template("ranking.html",
                           dane=dane,
                           sortuj=request.args.get("sortuj", "wynik_szczescia"),
                           kierunek=request.args.get("kierunek", "malejaco"),
                           filtr_kraj=(request.args.get("kraj") or "").strip().lower(),
                           min_wynik=request.args.get("min_wynik"))

@app.route("/kraj/<nazwa>")
def kraj(nazwa):
    for r in DANE:
        if r["kraj"].lower() == nazwa.lower():
            return render_template("kraj.html", r=r)
    abort(404, description="Nie znaleziono takiego kraju.")

@app.route("/analiza")
def analiza():
    return render_template("analiza.html")

@app.route("/pomoc")
def pomoc():
    return render_template("pomoc.html")


@app.route("/export", endpoint="export")
def export_csv():
    dane = filtruj_i_sortuj(request.args, DANE)
    bufor = io.StringIO()
    writer = csv.writer(bufor)
    writer.writerow(["kraj", "wynik_szczescia", "pkb_na_osobe_tys_usd", "zdrowe_zycie_lata"])
    for r in dane:
        writer.writerow([r["kraj"],
                         f"{r['wynik_szczescia']:.2f}",
                         f"{r['pkb_na_osobe']:.2f}",
                         f"{r['zdrowe_zycie']:.2f}"])
    resp = make_response(bufor.getvalue().encode("utf-8"))
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=ranking.csv"
    return resp

@app.route("/favicon.ico")
def favicon():
    #-404
    return ("", 204)

@app.errorhandler(404)
def blad_404(e):
    return render_template("404.html", opis=str(e)), 404

if __name__ == "__main__":
    app.run(debug=True)
