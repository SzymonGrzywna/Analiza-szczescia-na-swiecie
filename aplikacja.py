from flask import Flask, render_template, request, abort, make_response
import sqlite3, csv, os, io

app = Flask(__name__)

SCIEZKA_BAZY = "baza/dane.db"
SCIEZKA_CSV  = "dane/dane_szczescie.csv"

# -

def polacz():
    os.makedirs(os.path.dirname(SCIEZKA_BAZY), exist_ok=True)
    con = sqlite3.connect(SCIEZKA_BAZY)
    con.row_factory = sqlite3.Row
    return con

def init_baza_jesli_trzeba():
    con = polacz()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kraje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kraj TEXT NOT NULL,
            wynik_szczescia REAL NOT NULL,
            pkb_na_osobe REAL NOT NULL,
            zdrowe_zycie REAL NOT NULL
        )
    """)
    con.commit()
    cur.execute("SELECT COUNT(*) AS ile FROM kraje")
    ile = cur.fetchone()["ile"]
    if ile == 0:
        wczytaj_csv_do_bazy(con)
    con.close()

def wczytaj_csv_do_bazy(con):
    if not os.path.exists(SCIEZKA_CSV):
        return
    with open(SCIEZKA_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        dane = []
        for r in reader:
            try:
                dane.append((
                    r["kraj"],
                    float(r["wynik_szczescia"]),
                    float(r["pkb_na_osobe"]),
                    float(r["zdrowe_zycie"]),
                ))
            except Exception:
                continue
    con.executemany(
        "INSERT INTO kraje (kraj, wynik_szczescia, pkb_na_osobe, zdrowe_zycie) VALUES (?,?,?,?)",
        dane
    )
    con.commit()

def fetch_top10():
    con = polacz()
    cur = con.cursor()
    cur.execute("""
        SELECT kraj, wynik_szczescia, pkb_na_osobe, zdrowe_zycie
        FROM kraje
        ORDER BY wynik_szczescia DESC
        LIMIT 10
    """)
    wiersze = cur.fetchall()
    con.close()
    return [dict(w) for w in wiersze]

def fetch_ranking(args):
    sortuj = args.get("sortuj", "wynik_szczescia")
    kierunek = args.get("kierunek", "malejaco")
    filtr_kraj = (args.get("kraj") or "").strip().lower()
    min_wynik = args.get("min_wynik")

    dozw = {"wynik_szczescia", "pkb_na_osobe", "zdrowe_zycie"}
    if sortuj not in dozw:
        sortuj = "wynik_szczescia"
    kolejnosc = "DESC" if kierunek != "rosnaco" else "ASC"

    warunki = []
    params = []

    if filtr_kraj:
        warunki.append("LOWER(kraj) LIKE ?")
        params.append(f"%{filtr_kraj}%")
    if min_wynik:
        try:
            float(min_wynik)
            warunki.append("wynik_szczescia >= ?")
            params.append(min_wynik)
        except Exception:
            pass

    where_sql = ("WHERE " + " AND ".join(warunki)) if warunki else ""
    sql = f"""
        SELECT kraj, wynik_szczescia, pkb_na_osobe, zdrowe_zycie
        FROM kraje
        {where_sql}
        ORDER BY {sortuj} {kolejnosc}
    """

    con = polacz()
    cur = con.cursor()
    cur.execute(sql, params)
    wiersze = cur.fetchall()
    con.close()
    return [dict(w) for w in wiersze], sortuj, kierunek, filtr_kraj, (min_wynik or "")

def fetch_kraj(nazwa):
    con = polacz()
    cur = con.cursor()
    cur.execute("""
        SELECT kraj, wynik_szczescia, pkb_na_osobe, zdrowe_zycie
        FROM kraje
        WHERE LOWER(kraj) = LOWER(?)
        LIMIT 1
    """, (nazwa,))
    r = cur.fetchone()
    con.close()
    return dict(r) if r else None


@app.template_filter("plfloat")
def plfloat_wyswietl(v):
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except Exception:
        return str(v)



@app.route("/")
def strona_glowna():
    init_baza_jesli_trzeba()
    top10 = fetch_top10()
    return render_template("strona_glowna.html", top10=top10)

@app.route("/ranking")
def ranking():
    init_baza_jesli_trzeba()
    dane, sortuj, kierunek, filtr_kraj, min_wynik = fetch_ranking(request.args)
    return render_template("ranking.html",
                           dane=dane,
                           sortuj=sortuj,
                           kierunek=kierunek,
                           filtr_kraj=filtr_kraj,
                           min_wynik=min_wynik)

@app.route("/kraj/<nazwa>")
def kraj(nazwa):
    init_baza_jesli_trzeba()
    r = fetch_kraj(nazwa)
    if not r:
        abort(404, description="Nie znaleziono takiego kraju.")
    return render_template("kraj.html", r=r)

@app.route("/analiza")
def analiza():

    return render_template("analiza.html")

@app.route("/pomoc")
def pomoc():
    return render_template("pomoc.html")

@app.route("/export", endpoint="export")
def export_csv():
    init_baza_jesli_trzeba()
    dane, _, _, _, _ = fetch_ranking(request.args)
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
    return ("", 204)

@app.errorhandler(404)
def blad_404(e):
    return render_template("404.html", opis=str(e)), 404

if __name__ == "__main__":
    init_baza_jesli_trzeba()
    app.run(debug=True)
