import pandas as pd
import numpy as np
from pathlib import Path

from modelo_v3_3 import calcular_score_base, calcular_penalizacion_v3, VENTANA_MEMORIA

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"
HISTORICO_FILE = DATA_DIR / "historico_precios.csv"
JUGADORES_FILE = DATA_DIR / "jugadores_laliga.csv"
BACKTEST_FILE = DATA_DIR / "backtest_v3_3_resultados.csv"
MEMORIA_FILE = DATA_DIR / "memoria_v3_3.csv"
RANKING_FILE = DATA_DIR / "ranking_actual_v3_3.csv"
PICK_FILE = DATA_DIR / "picks_diarios_v3_3.csv"
POST_FILE = DATA_DIR / "post_diario_v3_3.txt"
TOP_MEMORIA = 20

POSICIONES = {1: "POR", 2: "DEF", 3: "MED", 4: "DEL"}


def precio_en_o_antes(grupo, fecha):
    x = grupo[grupo["date"] <= fecha]
    if x.empty:
        return None
    return x.iloc[-1]["marketValue"]


def cargar_datos():
    h = pd.read_csv(HISTORICO_FILE)
    j = pd.read_csv(JUGADORES_FILE)
    h["date"] = pd.to_datetime(h["date"], errors="coerce")
    h["marketValue"] = pd.to_numeric(h["marketValue"], errors="coerce")
    h["player_id"] = pd.to_numeric(h["player_id"], errors="coerce")
    j["id"] = pd.to_numeric(j["id"], errors="coerce")
    j["positionId"] = pd.to_numeric(j["positionId"], errors="coerce")
    j["lastSeasonPoints"] = pd.to_numeric(j["lastSeasonPoints"], errors="coerce")
    h = h.dropna(subset=["date", "marketValue", "player_id"])
    h = h[h["marketValue"] > 0].sort_values(["player_id", "date"])
    j = j[j["positionId"] != 5].copy()
    valid_ids = set(j["id"].dropna())
    h = h[h["player_id"].isin(valid_ids)].copy()
    return h, j


def construir_candidatos(h, j, fecha):
    nombres = dict(zip(j["id"], j["nickname"]))
    posiciones = dict(zip(j["id"], j["positionId"]))
    last_points = dict(zip(j["id"], j["lastSeasonPoints"]))
    rows = []
    for pid, grupo in h.groupby("player_id"):
        grupo = grupo.sort_values("date").drop_duplicates("date", keep="last")
        precio = precio_en_o_antes(grupo, fecha)
        if precio is None or precio <= 0:
            continue
        p7 = precio_en_o_antes(grupo, fecha - pd.Timedelta(days=7))
        p3 = precio_en_o_antes(grupo, fecha - pd.Timedelta(days=3))
        p1 = precio_en_o_antes(grupo, fecha - pd.Timedelta(days=1))
        if any(x is None or x <= 0 for x in (p7, p3, p1)):
            continue
        v7 = (precio - p7) / p7 * 100
        v3 = (precio - p3) / p3 * 100
        v1 = (precio - p1) / p1 * 100
        pts = last_points.get(pid, 0)
        if pd.isna(pts):
            pts = 0
        score_base = calcular_score_base(precio, v7, v3, v1, pts)
        rows.append({"fecha": fecha, "player_id": pid, "nickname": nombres.get(pid, str(pid)), "positionId": posiciones.get(pid, 0), "precio": precio, "var_7d": v7, "var_3d": v3, "var_1d": v1, "score_base": score_base})
    return pd.DataFrame(rows)


def cargar_memoria(fecha):
    if MEMORIA_FILE.exists():
        m = pd.read_csv(MEMORIA_FILE)
        if not m.empty:
            m["fecha"] = pd.to_datetime(m["fecha"], errors="coerce")
            m["player_id"] = pd.to_numeric(m["player_id"], errors="coerce")
            m["rentabilidad_7d"] = pd.to_numeric(m["rentabilidad_7d"], errors="coerce")
            return m.dropna(subset=["fecha", "player_id"])
    if BACKTEST_FILE.exists():
        b = pd.read_csv(BACKTEST_FILE)
        b["fecha"] = pd.to_datetime(b["fecha"], errors="coerce")
        b["player_id"] = pd.to_numeric(b["player_id"], errors="coerce")
        b["rentabilidad_7d"] = pd.to_numeric(b["rentabilidad_7d"], errors="coerce")
        b = b.dropna(subset=["fecha", "player_id", "rentabilidad_7d"])
        b = b[b["fecha"] < fecha].copy()
        rows = []
        for d, g in b.groupby("fecha"):
            rows.append(g.sort_values("score", ascending=False).head(TOP_MEMORIA)[["fecha", "player_id", "nickname", "rentabilidad_7d", "score_base", "score"]])
        if rows:
            m = pd.concat(rows, ignore_index=True)
            m.to_csv(MEMORIA_FILE, index=False, encoding="utf-8-sig")
            return m
    return pd.DataFrame(columns=["fecha", "player_id", "nickname", "rentabilidad_7d", "score_base", "score"])


def actualizar_rentabilidades_memoria(m, h, fecha):
    if m.empty:
        return m
    out = m.copy()
    for idx, r in out.iterrows():
        if pd.notna(r.get("rentabilidad_7d")):
            continue
        pid = r["player_id"]
        g = h[h["player_id"] == pid].sort_values("date")
        p0 = precio_en_o_antes(g, r["fecha"])
        p7 = precio_en_o_antes(g, r["fecha"] + pd.Timedelta(days=7))
        if p0 and p7:
            out.at[idx, "rentabilidad_7d"] = (p7 - p0) / p0 * 100
    return out


def guardar_memoria(m):
    m.sort_values(["fecha", "player_id"]).to_csv(MEMORIA_FILE, index=False, encoding="utf-8-sig")


def generar_post(top):
    fecha = top.iloc[0]["fecha"].strftime("%d/%m/%Y")
    lines = [f"🔥 OPORTUNIDADES V3.3 — {fecha}", "", "Top 5 detectado por el modelo:"]
    for i, (_, r) in enumerate(top.head(5).iterrows(), 1):
        lines.append(f"{i}. {r['nickname']} — Score {r['score']:.1f} — 7d {r['var_7d']:+.1f}%")
    lines += ["", "📊 Score ≥35 = oportunidad de alta prioridad", "", "#LaLigaFantasy #Fantasy #LaLiga"]
    return "\n".join(lines)


def main():
    h, j = cargar_datos()
    fecha = h["date"].max()
    candidatos = construir_candidatos(h, j, fecha)
    if candidatos.empty:
        raise RuntimeError("No hay candidatos suficientes para calcular la V3.3")
    memoria = cargar_memoria(fecha)
    memoria = actualizar_rentabilidades_memoria(memoria, h, fecha)
    resultados = []
    for _, r in candidatos.iterrows():
        info = calcular_penalizacion_v3(r["player_id"], fecha, memoria)
        x = r.copy()
        x["penalizacion_adaptativa"] = info["penalizacion"]
        x["memoria_apariciones"] = info["apariciones"]
        x["memoria_rent_7d"] = info["rentabilidad_media_7d"]
        x["memoria_acierto_7d"] = info["acierto_7d"]
        x["memoria_fallos_consecutivos"] = info["fallos_consecutivos"]
        x["memoria_deterioro"] = info["deterioro_reciente"]
        x["score"] = np.clip(x["score_base"] - x["penalizacion_adaptativa"], 0, 100)
        resultados.append(x)
    ranking = pd.DataFrame(resultados).sort_values("score", ascending=False)
    ranking["grupo_score"] = pd.cut(ranking["score"], bins=[-np.inf,20,30,40,50,60,70,80,90,100], labels=["<20","20-30","30-40","40-50","50-60","60-70","70-80","80-90","90-100"], right=False)
    ranking.to_csv(RANKING_FILE, index=False, encoding="utf-8-sig")
    top_memoria = ranking.head(TOP_MEMORIA).copy()
    nuevas = top_memoria[["fecha","player_id","nickname","score_base","score"]].copy()
    nuevas["rentabilidad_7d"] = np.nan
    if not memoria.empty:
        memoria = pd.concat([memoria, nuevas], ignore_index=True)
    else:
        memoria = nuevas
    memoria = memoria.drop_duplicates(subset=["fecha", "player_id"], keep="last")
    guardar_memoria(memoria)
    top5 = ranking[ranking["score"] >= 35].head(5)
    post = generar_post(top5 if not top5.empty else ranking.head(5))
    POST_FILE.write_text(post, encoding="utf-8")
    pick_rows = top5.copy()
    if not pick_rows.empty:
        pick_rows["fecha_ejecucion"] = fecha
        header = not PICK_FILE.exists()
        pick_rows.to_csv(PICK_FILE, mode="a", header=header, index=False, encoding="utf-8-sig")
    print("=" * 70)
    print("MOTOR DIARIO V3.3")
    print("=" * 70)
    print(f"Fecha de corte: {fecha}")
    print(f"Candidatos: {len(ranking)}")
    print(f"Memoria: {len(memoria)} registros")
    print()
    print("TOP 10")
    for _, r in ranking.head(10).iterrows():
        print(f"{r['nickname']:<25} Score {r['score']:>6.2f} | Base {r['score_base']:>6.2f} | Pen {r['penalizacion_adaptativa']:>5.2f} | 7d {r['var_7d']:+7.2f}%")
    print()
    print(f"Ranking: {RANKING_FILE}")
    print(f"Memoria: {MEMORIA_FILE}")
    print(f"Post:    {POST_FILE}")


if __name__ == "__main__":
    main()
