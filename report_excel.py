import io
import pandas as pd


PESI_ENERGETICI = {
    "Zona climatica": 5, "Anno di costruzione": 5,
    "Distanza dal mare": 4, "Superficie involucro esterna": 4,
    "Rapporto di porosita teorica": 2, "Profondita di carbonatazione stimata": 1,
    "Tipologia costruttiva": 2, "Volume degli elementi strutturali": 2,
    "Altezza massima fuoriterra valutata in gronda": 2,
    "Altezza minima fuoriterra valutata in gronda": 2,
    "Configurazione planimetrica rapporto \u03b21 = a/l": 1,
    "Configurazione planimetrica rapporto \u03b22 = b/l": 1,
    "Classe di esposizione": 1, "Zona sismica": 1,
}
PESI_STRUTTURALI = {
    "Zona climatica": 1, "Distanza dal mare": 1,
    "Anno di costruzione": 5, "Superficie involucro esterna": 2,
    "Rapporto di porosita teorica": 5, "Profondita di carbonatazione stimata": 5,
    "Altezza massima fuoriterra valutata in gronda": 1,
    "Altezza minima fuoriterra valutata in gronda": 1,
    "Tipologia costruttiva": 5, "Volume degli elementi strutturali": 5,
    "Configurazione planimetrica rapporto \u03b21 = a/l": 3,
    "Configurazione planimetrica rapporto \u03b22 = b/l": 3,
    "Classe di esposizione": 4, "Zona sismica": 2,
}

HEADERS_RENAME = {
    "area_roofs": "Superficie copertura",
    "superficie_involucro": "Superficie involucro",
    "volume_strutturale": "Volume strutturale",
    "num_windows": "N. finestre", "num_doors": "N. porte",
    "num_columns": "N. colonne", "num_beams": "N. travi",
    "num_slabs": "N. solai", "num_roofs": "N. coperture",
    "num_stairs": "N. scale", "num_walls_ext": "N. pareti esterne",
    "area_windows": "Area finestre", "area_doors": "Area porte",
    "area_walls_ext": "Area pareti esterne", "num_walls_int": "N. pareti interne",
}


def _build_formats(wb):
    return {
        "title":   wb.add_format({"bold": True, "font_size": 14, "align": "center", "valign": "vcenter", "bg_color": "#C65911", "font_color": "#FFFFFF", "border": 1}),
        "section": wb.add_format({"bold": True, "font_size": 11, "align": "left", "valign": "vcenter", "bg_color": "#F4B183", "border": 1}),
        "header":  wb.add_format({"bold": True, "text_wrap": True, "align": "center", "valign": "vcenter", "font_color": "#FFFFFF", "bg_color": "#C65911", "border": 1}),
        "row_name":wb.add_format({"bold": True, "align": "left", "valign": "vcenter", "bg_color": "#F8CBAD", "border": 1}),
        "text":    wb.add_format({"align": "left", "valign": "vcenter", "border": 1, "text_wrap": True}),
        "index":   wb.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        "percent": wb.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "border": 1}),
        "percent_bold": wb.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "bold": True, "border": 1}),
        "euro":    wb.add_format({"num_format": "#,##0.00 \u20ac", "align": "right", "valign": "vcenter", "border": 1}),
        "euro_bold":wb.add_format({"num_format": "#,##0.00 \u20ac", "align": "right", "valign": "vcenter", "bg_color": "#FFF2CC", "bold": True, "border": 1}),
        "euro_header": wb.add_format({"bold": True, "text_wrap": True, "align": "center", "valign": "vcenter", "font_color": "#FFFFFF", "bg_color": "#C00000", "border": 1}),
        "note":    wb.add_format({"italic": True, "font_size": 9, "align": "left", "valign": "vcenter", "border": 1}),
    }


def _build_pairs(df):
    pairs = []
    cols = list(df.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append({"Pos": len(pairs) + 1, "Modello 1": cols[i], "Modello 2": cols[j], "Somiglianza": df.iloc[i, j]})
    out = pd.DataFrame(pairs).sort_values("Somiglianza", ascending=False).reset_index(drop=True)
    out["Pos"] = range(1, len(out) + 1)
    return out


def _build_focus(df, target_sub):
    target = None
    for col in df.columns:
        if target_sub.lower() in col.lower():
            target = col
            break
    if target is None and len(df.columns) > 0:
        target = df.columns[0]
    if target is None:
        return pd.DataFrame(), ""
    sims = df[target].drop(target).sort_values(ascending=False)
    rows = [{"Rango": r, "Edificio Riferimento": target, "Modello Confrontato": n, "Indice Somiglianza": v}
            for r, (n, v) in enumerate(sims.head(10).items(), 1)]
    return pd.DataFrame(rows), target


def write_report(result: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book
        fmt = _build_formats(wb)

        df_sim_energ = result["df_sim_energ"]
        df_sim_strut = result["df_sim_strut"]
        all_q = result["all_quantities"]
        all_c = result["all_costs"]
        sample = result["sample"]

        df_pairs_e = _build_pairs(df_sim_energ)
        df_pairs_s = _build_pairs(df_sim_strut)
        df_focus_e, target_e = _build_focus(df_sim_energ, sample["target_name"])
        df_focus_s, _ = _build_focus(df_sim_strut, sample["target_name"])

        # --- FOGLIO 1: MATRICE ENERGETICA ---
        ws1 = wb.add_worksheet("1_Matrice Energetica")
        ws1.merge_range(0, 0, 0, len(df_sim_energ.columns),
                        "MATRICE DI SOMIGLIANZA ENERGETICA (Pesata)", fmt["title"])
        for c, name in enumerate(df_sim_energ.columns, 1):
            ws1.write(2, c, name, fmt["header"])
        for r, name in enumerate(df_sim_energ.index, 3):
            ws1.write(r, 0, name, fmt["row_name"])
        for r in range(len(df_sim_energ.index)):
            for c in range(len(df_sim_energ.columns)):
                ws1.write_number(r + 3, c + 1, float(df_sim_energ.iloc[r, c]), fmt["percent"])
        ws1.set_column(0, 0, 42)
        ws1.set_column(1, len(df_sim_energ.columns), 14)
        ws1.freeze_panes(3, 1)
        if not df_sim_energ.empty:
            ws1.conditional_format(3, 1, len(df_sim_energ) + 3, len(df_sim_energ.columns),
                                   {"type": "cell", "criteria": ">", "value": 0.75, "format": fmt["percent_bold"]})
        pr = len(df_sim_energ) + 5
        ws1.merge_range(pr, 0, pr, 2, "PESI PARAMETRI ENERGETICI", fmt["section"])
        ws1.write(pr + 1, 0, "Parametro", fmt["header"])
        ws1.write(pr + 1, 1, "Peso", fmt["header"])
        for i, (p, w) in enumerate(PESI_ENERGETICI.items()):
            ws1.write(pr + 2 + i, 0, p, fmt["text"])
            ws1.write_number(pr + 2 + i, 1, w, fmt["index"])

        # --- FOGLIO 2: MATRICE STRUTTURALE ---
        ws2 = wb.add_worksheet("2_Matrice Strutturale")
        ws2.merge_range(0, 0, 0, len(df_sim_strut.columns),
                        "MATRICE DI SOMIGLIANZA STRUTTURALE (Pesata)", fmt["title"])
        for c, name in enumerate(df_sim_strut.columns, 1):
            ws2.write(2, c, name, fmt["header"])
        for r, name in enumerate(df_sim_strut.index, 3):
            ws2.write(r, 0, name, fmt["row_name"])
        for r in range(len(df_sim_strut.index)):
            for c in range(len(df_sim_strut.columns)):
                ws2.write_number(r + 3, c + 1, float(df_sim_strut.iloc[r, c]), fmt["percent"])
        ws2.set_column(0, 0, 42)
        ws2.set_column(1, len(df_sim_strut.columns), 14)
        ws2.freeze_panes(3, 1)
        if not df_sim_strut.empty:
            ws2.conditional_format(3, 1, len(df_sim_strut) + 3, len(df_sim_strut.columns),
                                   {"type": "cell", "criteria": ">", "value": 0.75, "format": fmt["percent_bold"]})
        pr = len(df_sim_strut) + 5
        ws2.merge_range(pr, 0, pr, 2, "PESI PARAMETRI STRUTTURALI", fmt["section"])
        ws2.write(pr + 1, 0, "Parametro", fmt["header"])
        ws2.write(pr + 1, 1, "Peso", fmt["header"])
        for i, (p, w) in enumerate(PESI_STRUTTURALI.items()):
            ws2.write(pr + 2 + i, 0, p, fmt["text"])
            ws2.write_number(pr + 2 + i, 1, w, fmt["index"])

        # --- FOGLIO 3: CLASSIFICA COPPIE ---
        ws3 = wb.add_worksheet("3_Classifica Coppie")
        ws3.merge_range("A1:F1", "CLASSIFICA COPPIE PER SOMIGLIANZA", fmt["title"])
        df_pe_f = df_pairs_e[df_pairs_e["Somiglianza"] < 1.0].copy()
        df_ps_f = df_pairs_s[df_pairs_s["Somiglianza"] < 1.0].copy()
        ws3.write(3, 0, "SOMIGLIANZA ENERGETICA", fmt["section"])
        for c, h in enumerate(["Pos.", "Modello 1", "Modello 2", "Somiglianza"], 1):
            ws3.write(4, c, h, fmt["header"])
        for i, row in enumerate(df_pe_f.itertuples(index=False), 5):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            v = float(row[3])
            ws3.write_number(i, 4, v, fmt["percent_bold"] if v > 0.75 else fmt["percent"])
        sr = len(df_pe_f) + 7
        ws3.write(sr, 0, "SOMIGLIANZA STRUTTURALE", fmt["section"])
        for c, h in enumerate(["Pos.", "Modello 1", "Modello 2", "Somiglianza"], 1):
            ws3.write(sr + 1, c, h, fmt["header"])
        for i, row in enumerate(df_ps_f.itertuples(index=False), sr + 2):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            v = float(row[3])
            ws3.write_number(i, 4, v, fmt["percent_bold"] if v > 0.75 else fmt["percent"])
        ws3.set_column("A:A", 8)
        ws3.set_column("B:D", 38)
        ws3.set_column("E:E", 15)

        # --- FOGLIO 4: FOCUS ---
        ws4 = wb.add_worksheet("4_Focus Edificio")
        ws4.merge_range("A1:E1", f"ANALISI FOCUS: {target_e.upper()}", fmt["title"])
        df_fe_f = df_focus_e[df_focus_e["Indice Somiglianza"] < 1.0].copy() if not df_focus_e.empty else df_focus_e
        df_fs_f = df_focus_s[df_focus_s["Indice Somiglianza"] < 1.0].copy() if not df_focus_s.empty else df_focus_s
        ws4.write(3, 0, "SOMIGLIANZA ENERGETICA", fmt["section"])
        for c, h in enumerate(["Rango", "Edificio Riferimento", "Modello Confrontato", "Indice Somiglianza"], 1):
            ws4.write(4, c, h, fmt["header"])
        for i, row in enumerate(df_fe_f.itertuples(index=False), 5):
            ws4.write_number(i, 1, int(row[0]), fmt["index"])
            ws4.write(i, 2, row[1], fmt["text"])
            ws4.write(i, 3, row[2], fmt["text"])
            v = float(row[3])
            ws4.write_number(i, 4, v, fmt["percent_bold"] if v > 0.75 else fmt["percent"])
        sr = len(df_fe_f) + 7
        ws4.write(sr, 0, "SOMIGLIANZA STRUTTURALE", fmt["section"])
        for c, h in enumerate(["Rango", "Edificio Riferimento", "Modello Confrontato", "Indice Somiglianza"], 1):
            ws4.write(sr + 1, c, h, fmt["header"])
        for i, row in enumerate(df_fs_f.itertuples(index=False), sr + 2):
            ws4.write_number(i, 1, int(row[0]), fmt["index"])
            ws4.write(i, 2, row[1], fmt["text"])
            ws4.write(i, 3, row[2], fmt["text"])
            v = float(row[3])
            ws4.write_number(i, 4, v, fmt["percent_bold"] if v > 0.75 else fmt["percent"])
        ws4.set_column("A:A", 8)
        ws4.set_column("B:D", 38)
        ws4.set_column("E:E", 15)

        # --- FOGLIO 5: QUANTITA ---
        ws5 = wb.add_worksheet("5_Quantita Geometriche")
        ws5.merge_range("A1:J1", "QUANTITA GEOMETRICHE ESTRATTE DAI MODELLI IFC", fmt["title"])
        if all_q:
            all_h = list(all_q[list(all_q.keys())[0]].keys())
            headers_q = [h for h in all_h if any(q.get(h, 0) > 0 for q in all_q.values())]
            ws5.write(3, 0, "Modello", fmt["header"])
            for c, h in enumerate(headers_q, 1):
                ws5.write(3, c, HEADERS_RENAME.get(h, h), fmt["header"])
            for r, (mn, qty) in enumerate(all_q.items(), 4):
                ws5.write(r, 0, mn, fmt["row_name"])
                for c, h in enumerate(headers_q, 1):
                    v = qty.get(h, 0)
                    ws5.write_number(r, c, float(v) if v else 0, fmt["index"])
        ws5.set_column(0, 0, 42)
        ws5.set_column(1, 50, 15)

        # --- FOGLIO 6: CENSIMENTO INTERVENTI ---
        ws6 = wb.add_worksheet("6_Censimento Interventi")
        ws6.merge_range("A1:J1", "CENSIMENTO INTERVENTI - PREZZARIO CAMPANIA 2026", fmt["title"])
        target_for_filter = sample["target_name"]
        gia_fatti_set = set(sample.get("gia_fatti", []))
        cr = 3
        for mn, costs in all_c.items():
            ws6.write(cr, 0, f"MODELLO: {mn}", fmt["section"])
            cr += 1
            for c, h in enumerate(["Codice Intervento", "Nome Intervento", "Tipo", "Quantita",
                                    "Unita", "Prezzo Unit.", "Codice Prezzario", "Costo Totale"]):
                ws6.write(cr, c, h, fmt["euro_header"] if c == 7 else fmt["header"])
            cr += 1
            if mn == target_for_filter:
                costs_f = [c for c in costs if c["codice"] in gia_fatti_set]
            else:
                costs_f = costs
            tot = 0
            for cost in costs_f:
                ws6.write(cr, 0, cost["codice"], fmt["text"])
                ws6.write(cr, 1, cost["nome"], fmt["text"])
                ws6.write(cr, 2, cost["tipo"], fmt["text"])
                ws6.write_number(cr, 3, cost["quantita"], fmt["index"])
                ws6.write(cr, 4, cost["unita_misura"], fmt["text"])
                ws6.write_number(cr, 5, cost["prezzo_unitario"], fmt["euro"])
                ws6.write(cr, 6, cost.get("codice_prezzario", ""), fmt["text"])
                ws6.write_number(cr, 7, cost["costo_totale"], fmt["euro"])
                tot += cost["costo_totale"]
                cr += 1
            ws6.write(cr, 6, "TOTALE MODELLO:", fmt["euro_bold"])
            ws6.write_number(cr, 7, tot, fmt["euro_bold"])
            cr += 2
        ws6.set_column("A:A", 28)
        ws6.set_column("B:B", 42)
        ws6.set_column("C:C", 14)
        ws6.set_column("D:E", 12)
        ws6.set_column("F:F", 14)
        ws6.set_column("G:G", 28)
        ws6.set_column("H:H", 16)

        # --- FOGLIO 7: RIEPILOGO ---
        ws7 = wb.add_worksheet("7_Riepilogo")
        ws7.merge_range("A1:F1", "RIEPILOGO STIMA ECONOMICA", fmt["title"])
        for c, h in enumerate(["Modello", "Tipo Analisi", "N. Interventi", "Costo Totale"]):
            ws7.write(3, c, h, fmt["euro_header"] if c == 3 else fmt["header"])
        r = 4
        for mn, costs in all_c.items():
            ener = [c for c in costs if c["tipo"] == "energetico"]
            strut = [c for c in costs if c["tipo"] == "strutturale"]
            if ener:
                ws7.write(r, 0, mn, fmt["row_name"])
                ws7.write(r, 1, "Energetico", fmt["text"])
                ws7.write_number(r, 2, len(ener), fmt["index"])
                ws7.write_number(r, 3, sum(c["costo_totale"] for c in ener), fmt["euro"])
                r += 1
            if strut:
                ws7.write(r, 0, mn, fmt["row_name"])
                ws7.write(r, 1, "Strutturale", fmt["text"])
                ws7.write_number(r, 2, len(strut), fmt["index"])
                ws7.write_number(r, 3, sum(c["costo_totale"] for c in strut), fmt["euro"])
                r += 1
            ws7.write(r, 0, mn, fmt["row_name"])
            ws7.write(r, 1, "TOTALE", fmt["section"])
            ws7.write_number(r, 2, len(costs), fmt["index"])
            ws7.write_number(r, 3, sum(c["costo_totale"] for c in costs), fmt["euro_bold"])
            r += 1
        ws7.set_column("A:A", 42)
        ws7.set_column("B:B", 16)
        ws7.set_column("C:C", 14)
        ws7.set_column("D:D", 18)

        # --- FOGLIO 8: CAMPIONE ---
        if sample:
            ws8 = wb.add_worksheet("8_Campione")
            ws8.merge_range("A1:G1", "ANALISI ECONOMICA MODELLO CAMPIONE", fmt["title"])
            r = 3
            ws8.write(r, 0, "Modello Campione:", fmt["section"])
            ws8.write(r, 1, sample["target_name"], fmt["row_name"])
            r += 1
            ws8.write(r, 0, "Edificio Piu Simile:", fmt["section"])
            ws8.write(r, 1, sample["vicino_name"], fmt["row_name"])
            r += 1
            ws8.write(r, 0, "Somiglianza Energetica:", fmt["section"])
            ws8.write_number(r, 1, sample["sim_energ"], fmt["percent"])
            r += 1
            ws8.write(r, 0, "Somiglianza Strutturale:", fmt["section"])
            ws8.write_number(r, 1, sample["sim_strut"], fmt["percent"])
            r += 1
            ws8.write(r, 0, "Somiglianza Media:", fmt["section"])
            ws8.write_number(r, 1, sample["sim_media"], fmt["percent_bold"])
            r += 2

            ws8.write(r, 0, "QUANTITA ESTRA DAL MODELLO CAMPIONE", fmt["section"])
            r += 1
            qty = sample["qty_campione"]
            qty_items = [
                ("Superficie involucro esterna", qty.get("superficie_involucro", 0), "m\u00b2"),
                ("Area copertura", qty.get("area_roofs", 0), "m\u00b2"),
                ("Pareti esterne", qty.get("num_walls_ext", 0), "nr"),
                ("Finestre", qty.get("num_windows", 0), "nr"),
                ("Porte", qty.get("num_doors", 0), "nr"),
                ("Colonne", qty.get("num_columns", 0), "nr"),
                ("Travi", qty.get("num_beams", 0), "nr"),
                ("Solai", qty.get("num_slabs", 0), "nr"),
                ("Coperture", qty.get("num_roofs", 0), "nr"),
                ("Scale", qty.get("num_stairs", 0), "nr"),
                ("Volume strutturale", qty.get("volume_strutturale", 0), "m\u00b3"),
            ]
            ws8.write(r, 0, "Parametro", fmt["header"])
            ws8.write(r, 1, "Valore", fmt["header"])
            ws8.write(r, 2, "Unita", fmt["header"])
            r += 1
            for nome, val, um in qty_items:
                ws8.write(r, 0, nome, fmt["text"])
                ws8.write_number(r, 1, float(val), fmt["index"])
                ws8.write(r, 2, um, fmt["text"])
                r += 1
            r += 1

            hdrs = ["Codice", "Intervento", "Tipo", "Quantita", "Unita", "Prezzo Unit.", "Costo Totale", "Note"]
            interv_v = sample.get("interventi_vicino", [])
            if interv_v:
                ws8.write(r, 0, "INTERVENTI DEL VICINO PIU SIMILE (CENSIMENTO - GIA REALIZZATI)", fmt["section"])
                r += 1
                for c, h in enumerate(hdrs):
                    ws8.write(r, c, h, fmt["euro_header"] if c == 6 else fmt["header"])
                r += 1
                tv = 0
                for cost in interv_v:
                    ws8.write(r, 0, cost.get("codice_prezzario", ""), fmt["text"])
                    ws8.write(r, 1, cost["nome"], fmt["text"])
                    ws8.write(r, 2, cost["tipo"], fmt["text"])
                    ws8.write_number(r, 3, cost["quantita"], fmt["index"])
                    ws8.write(r, 4, cost["unita_misura"], fmt["text"])
                    ws8.write_number(r, 5, cost["prezzo_unitario"], fmt["euro"])
                    ws8.write_number(r, 6, cost["costo_totale"], fmt["euro"])
                    ws8.write(r, 7, cost.get("note", ""), fmt["note"])
                    tv += cost["costo_totale"]
                    r += 1
                ws8.write(r, 5, "TOTALE VICINO:", fmt["euro_bold"])
                ws8.write_number(r, 6, tv, fmt["euro_bold"])
                r += 2

            interv_c = sample.get("interventi_campione", [])
            if interv_c:
                ws8.write(r, 0, "INTERVENTI NUOVI PROPOSTI PER IL CAMPIONE (ESCLUSI QUELLI GIA CENSITI)", fmt["section"])
                r += 1
                for c, h in enumerate(hdrs):
                    ws8.write(r, c, h, fmt["euro_header"] if c == 6 else fmt["header"])
                r += 1
                te = ts = 0
                for cost in interv_c:
                    ws8.write(r, 0, cost.get("codice_prezzario", ""), fmt["text"])
                    ws8.write(r, 1, cost["nome"], fmt["text"])
                    ws8.write(r, 2, cost["tipo"], fmt["text"])
                    ws8.write_number(r, 3, cost["quantita"], fmt["index"])
                    ws8.write(r, 4, cost["unita_misura"], fmt["text"])
                    ws8.write_number(r, 5, cost["prezzo_unitario"], fmt["euro"])
                    ws8.write_number(r, 6, cost["costo_totale"], fmt["euro"])
                    ws8.write(r, 7, cost.get("note", ""), fmt["note"])
                    if cost["tipo"] == "energetico":
                        te += cost["costo_totale"]
                    else:
                        ts += cost["costo_totale"]
                    r += 1
                r += 1
                ws8.write(r, 4, "TOTALE ENERGETICO:", fmt["euro_bold"])
                ws8.write_number(r, 6, te, fmt["euro_bold"])
                r += 1
                ws8.write(r, 4, "TOTALE STRUTTURALE:", fmt["euro_bold"])
                ws8.write_number(r, 6, ts, fmt["euro_bold"])
                r += 1
                ws8.write(r, 4, "TOTALE COMPLESSIVO:", fmt["euro_bold"])
                ws8.write_number(r, 6, te + ts, fmt["euro_bold"])
            ws8.set_column("A:A", 28)
            ws8.set_column("B:B", 42)
            ws8.set_column("C:C", 14)
            ws8.set_column("D:D", 12)
            ws8.set_column("E:E", 10)
            ws8.set_column("F:F", 14)
            ws8.set_column("G:G", 16)

    return buf.getvalue()
