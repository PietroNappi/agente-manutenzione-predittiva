#!/usr/bin/env python3
"""
Analisi di somiglianza energetica tra modelli IFC.

Estrae i 14 parametri dal Pset_InformazioniProgetto:
  Altezza massima/minima fuoriterra, Anno di costruzione,
  Classe di esposizione, Distanza dal mare, Profondita' carbonatazione,
  Rapporto di porosita', Superficie involucro, Tipologia costruttiva,
  Volume elementi strutturali, Zona climatica, Zona sismica,
  Configurazione planimetrica b1=a/l e b2=b/l

Schema pesi UNICO (scala empirica intera 1..5) applicato a tutti gli edifici.
I parametri mancanti in un file IFC vengono ignorati (NaN) e l'algoritmo
normalizza la similarita' sui pesi effettivamente applicati.

Output: 3 fogli Excel (struttura come file di riferimento)
  - Matrice Totale Energetica
  - Classifica coppie
  - Confronto singolo edificio (focus Ferraris)

Uso:
    python Script_Analisi_Energetica.py
    python Script_Analisi_Energetica.py --target ferraris
    python Script_Analisi_Energetica.py --verbose
"""

import os
import re
import sys
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import ifcopenshell
except ImportError:
    print("[ERRORE] ifcopenshell non installato. Esegui: pip install ifcopenshell")
    sys.exit(1)


# ============================================================
# CONFIGURAZIONE
# ============================================================

DEFAULT_IFC_FOLDER = r"C:\Users\pietr\Desktop\Scuole ifc parametri"
DEFAULT_OUTPUT_SUBFOLDER = "output"
DEFAULT_PSET = "Pset_InformazioniProgetto"
DEFAULT_TARGET = "ferraris"


# ============================================================
# MAPPING PROPRIETA' IFC (match via substring case-insensitive)
# ============================================================
# (chiave di ricerca, nome canonico usato nei pesi e nel DataFrame)

PROP_MAP = [
    ("altezza_massima", "Altezza massima fuoriterra valutata in gronda"),
    ("altezza_minima",  "Altezza minima fuoriterra valutata in gronda"),
    ("anno",            "Anno di costruzione"),
    ("esposizione",     "Classe di esposizione"),
    ("mare",            "Distanza dal mare"),
    ("carbonatazione",  "Profondita di carbonatazione stimata"),
    ("porosita",        "Rapporto di porosita teorica"),
    ("involucro",       "Superficie involucro esterna"),
    ("tipologia",       "Tipologia costruttiva"),
    ("volume",          "Volume degli elementi strutturali"),
    ("climatica",       "Zona climatica"),
    ("sismica",         "Zona sismica"),
    ("beta1",           "Configurazione planimetrica rapporto \u03b21 = a/l"),
    ("beta2",           "Configurazione planimetrica rapporto \u03b22 = b/l"),
]


# ============================================================
# PESI UNICI - 14 parametri, scala empirica intera 1..5
# ============================================================
# Stesso schema applicato a tutti gli edifici (MURATURA, C.A., C.A.P.).
# I parametri mancanti in un file IFC vengono ignorati automaticamente.
# Il totale qui e' indicativo: lo script normalizza la similarita' sui pesi
# effettivamente applicati, quindi l'output e' sempre in [0, 1].

PESI = {
    "Zona climatica":                                         1,
    "Distanza dal mare":                                      1,
    "Anno di costruzione":                                    5,
    "Superficie involucro esterna":                           2,
    "Rapporto di porosita teorica":                           5,
    "Profondita di carbonatazione stimata":                   5,
    "Altezza massima fuoriterra valutata in gronda":          1,
    "Altezza minima fuoriterra valutata in gronda":           1,
    "Tipologia costruttiva":                                  5,
    "Volume degli elementi strutturali":                      5,
    "Configurazione planimetrica rapporto \u03b21 = a/l":     3,
    "Configurazione planimetrica rapporto \u03b22 = b/l":     3,
    "Classe di esposizione":                                  4,
    "Zona sismica":                                           2,
}
# Totale = 25 (indicativo)


# ============================================================
# UTILITY
# ============================================================

def try_parse_number(val):
    """Converte una stringa con unita' di misura in numero, gestendo None/NaN."""
    if pd.isna(val) or val is None:
        return np.nan
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val)
    s = str(val).strip()
    s_clean = re.sub(
        r'\s*(m|m2|m3|m\xc2\xb2|m\xc2\xb3|cm|mm|kg|%|km|years|anni|\u00b0C|W/m2K|W/m\xc2\xb2K)\s*$',
        '', s, flags=re.IGNORECASE
    ).strip()
    s_clean = s_clean.replace(',', '.')
    try:
        return float(s_clean)
    except (ValueError, TypeError):
        return str(val).strip()


def detect_building_type(tipologia_value):
    """Ritorna 'MURATURA', 'CA' o 'UNKNOWN' dalla Tipologia costruttiva (solo per display)."""
    if pd.isna(tipologia_value):
        return "UNKNOWN"
    s = str(tipologia_value).strip().upper().replace('.', '').replace(' ', '')
    if "MURATURA" in s:
        return "MURATURA"
    if "CAP" in s or "CA" in s:
        return "CA"
    return "UNKNOWN"


# ============================================================
# ESTRAZIONE PARAMETRI
# ============================================================

def extract_project_parameters(model, pset_name, prop_map=PROP_MAP, verbose=False):
    """
    Estrae i parametri dal Pset indicato (sia da IfcProject che IfcBuilding).
    Match via substring case-insensitive sulle chiavi di prop_map.
    Ritorna dict {nome_canonico: valore} o None se Pset non trovato.
    """
    pset_data = {nome: None for _, nome in prop_map}
    pset_found = False

    for ent_type in ["IfcProject", "IfcBuilding"]:
        for entity in model.by_type(ent_type):
            if not hasattr(entity, "IsDefinedBy") or not entity.IsDefinedBy:
                continue
            for rel in entity.IsDefinedBy:
                if not rel.is_a("IfcRelDefinesByProperties"):
                    continue
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                    pset_found = True
                    for prop in (pdef.HasProperties or []):
                        if not prop.is_a("IfcPropertySingleValue"):
                            continue
                        if prop.NominalValue is None:
                            continue
                        ifc_prop_name = str(prop.Name).strip().lower()
                        for chiave, nome in prop_map:
                            if chiave in ifc_prop_name:
                                pset_data[nome] = try_parse_number(prop.NominalValue.wrappedValue)
                                if verbose:
                                    print(f"        {nome} = {pset_data[nome]!r}")
                                break

    if not pset_found:
        return None
    non_null = sum(
        1 for v in pset_data.values() if v is not None and not (isinstance(v, float) and np.isnan(v))
    )
    if non_null == 0 and verbose:
        print("        [Pset trovato ma nessuna proprieta' corrisponde al mapping]")
    return pset_data


# ============================================================
# CALCOLO SIMILARITA' PESATA
# ============================================================

def similarity_for_value(v1, v2):
    """Similarita' fra due valori (0..1). NaN su almeno uno -> 0 (parametro non informativo)."""
    if pd.isna(v1) or pd.isna(v2):
        return 0.0
    if isinstance(v1, (int, float, np.integer, np.floating)) and \
       isinstance(v2, (int, float, np.integer, np.floating)):
        v1, v2 = float(v1), float(v2)
        max_abs = max(abs(v1), abs(v2))
        if max_abs == 0:
            return 1.0
        return max(0.0, 1.0 - abs(v1 - v2) / max_abs)
    return 1.0 if str(v1).strip().lower() == str(v2).strip().lower() else 0.0


def build_similarity_matrix(df_features):
    """
    Costruisce la matrice di similarita' pesata (0..1).
    Schema pesi unico: ogni parametro mancante (NaN) viene saltato,
    la similarita' viene normalizzata sui pesi effettivamente applicati.
    """
    models = df_features.index.tolist()
    n = len(models)
    M = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            punteggio = 0.0
            somma = 0.0
            for param, peso in PESI.items():
                if param not in df_features.columns:
                    continue
                v1 = df_features.iloc[i].get(param, np.nan)
                v2 = df_features.iloc[j].get(param, np.nan)
                if pd.isna(v1) or pd.isna(v2):
                    continue
                sim = similarity_for_value(v1, v2)
                punteggio += sim * peso
                somma += peso
            M[i, j] = punteggio / somma if somma > 0 else 0.0

    return pd.DataFrame(M, index=models, columns=models)


# ============================================================
# COSTRUZIONE FOGLI
# ============================================================

def build_pair_ranking(df_similarity):
    models = df_similarity.index.tolist()
    pairs = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            pairs.append({
                "Posizione": 0,
                "Primo Modello IFC": models[i],
                "Secondo Modello IFC": models[j],
                "Somiglianza Pesata": float(df_similarity.iloc[i, j])
            })
    df_pairs = pd.DataFrame(pairs)
    if df_pairs.empty:
        return df_pairs
    df_pairs = (df_pairs
                .sort_values(by="Somiglianza Pesata", ascending=False)
                .reset_index(drop=True))
    df_pairs["Posizione"] = np.arange(1, len(df_pairs) + 1)
    return df_pairs


def build_focus_sheet(df_similarity, target_substring):
    target_name = next(
        (idx for idx in df_similarity.index if target_substring.lower() in idx.lower()),
        None
    )
    if target_name is None:
        return pd.DataFrame(columns=[
            "Rango", "Scuola di Riferimento", "Modello IFC Confrontato", "Indice di Somiglianza"
        ]), f"{target_substring} - MODELLO BIM"
    series = (df_similarity.loc[target_name]
              .drop(labels=[target_name], errors="ignore")
              .sort_values(ascending=False))
    rows = []
    for i, (name, value) in enumerate(series.items(), start=1):
        rows.append({
            "Rango": i,
            "Scuola di Riferimento": target_name,
            "Modello IFC Confrontato": name,
            "Indice di Somiglianza": float(value)
        })
    return pd.DataFrame(rows), target_name


# ============================================================
# GENERATORE EXCEL
# ============================================================

def build_formats(workbook):
    return {
        "title":   workbook.add_format({"bold": True, "font_size": 14, "align": "center", "valign": "vcenter", "bg_color": "#F4B183", "border": 1}),
        "section": workbook.add_format({"bold": True, "font_size": 11, "align": "left", "valign": "vcenter", "bg_color": "#FCE4D6", "border": 1}),
        "note":    workbook.add_format({"italic": True, "font_size": 10, "align": "left", "valign": "vcenter", "border": 1}),
        "header":  workbook.add_format({"bold": True, "text_wrap": True, "align": "center", "valign": "vcenter", "font_color": "#FFFFFF", "bg_color": "#ED7D31", "border": 1}),
        "row_name":workbook.add_format({"bold": True, "align": "left", "valign": "vcenter", "bg_color": "#D9EAF7", "border": 1}),
        "text":    workbook.add_format({"align": "left", "valign": "vcenter", "border": 1}),
        "index":   workbook.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        "percent": workbook.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "border": 1}),
        "percent_bold": workbook.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "bold": True, "border": 1}),
    }


def _write_weights_legend(ws, fmt, start_row, start_col, schema, title="PESI PARAMETRI (scala 1..5)"):
    """Scrive la legenda pesi unica (un solo schema)."""
    cur = start_row
    ws.write(cur, start_col, title, fmt["section"])
    cur += 1
    for param, peso in schema.items():
        ws.write(cur, start_col, f"{param}: {peso}", fmt["note"])
        cur += 1
    return cur + 1  # riga vuota di separazione


def write_excel_output(df_sim, df_pairs, df_focus, target_focus, output_path,
                       focus_type="-"):
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        wb = writer.book
        fmt = build_formats(wb)

        # ============== SHEET 1: MATRICE TOTALE ENERGETICA ==============
        ws1 = wb.add_worksheet("Matrice Totale Energetica")
        ws1.merge_range(0, 0, 0, len(df_sim.columns),
                        "FILE 1: Matrice di Somiglianza Totale Incrociata (Scenario Energetico)",
                        fmt["title"])
        for c, name in enumerate(df_sim.columns, 1):
            ws1.write(2, c, name, fmt["header"])
        for r, name in enumerate(df_sim.index, 3):
            ws1.write(r, 0, name, fmt["row_name"])
        for r in range(len(df_sim.index)):
            for c in range(len(df_sim.columns)):
                ws1.write_number(r + 3, c + 1, float(df_sim.iloc[r, c]), fmt["percent"])

        ws1.set_column(0, 0, 42)
        ws1.set_column(1, len(df_sim.columns), 15)
        ws1.freeze_panes(3, 1)
        if not df_sim.empty:
            ws1.conditional_format(3, 1, len(df_sim)+3, len(df_sim.columns),
                                   {"type": "cell", "criteria": ">", "value": 0.75,
                                    "format": fmt["percent_bold"]})

        # Legenda pesi sotto la matrice
        legend_start = 3 + len(df_sim) + 3
        _write_weights_legend(ws1, fmt, legend_start, 0, PESI)

        # ============== SHEET 2: CLASSIFICA COPPIE ==============
        ws2 = wb.add_worksheet("Classifica coppie")
        ws2.merge_range("B1:E1",
                        "FILE 2: Graduatoria Generale delle Coppie per Somiglianza Energetica",
                        fmt["title"])
        headers2 = ["Posizione", "Primo Modello IFC", "Secondo Modello IFC", "Somiglianza Pesata"]
        for c, h in enumerate(headers2, 1):
            ws2.write(3, c, h, fmt["header"])
        for i, row in enumerate(df_pairs.itertuples(index=False), 4):
            ws2.write_number(i, 1, int(row[0]), fmt["index"])
            ws2.write(i, 2, row[1], fmt["text"])
            ws2.write(i, 3, row[2], fmt["text"])
            ws2.write_number(i, 4, float(row[3]), fmt["percent"])

        # Legenda pesi in colonna H
        _write_weights_legend(ws2, fmt, 3, 7, PESI)

        ws2.set_column("B:B", 12)
        ws2.set_column("C:D", 38)
        ws2.set_column("E:E", 18)
        ws2.set_column("H:H", 55)
        ws2.freeze_panes(4, 1)
        if not df_pairs.empty:
            ws2.conditional_format(4, 4, len(df_pairs)+4, 4,
                                   {"type": "cell", "criteria": ">", "value": 0.75,
                                    "format": fmt["percent_bold"]})

        # ============== SHEET 3: CONFRONTO SINGOLO EDIFICIO ==============
        ws3 = wb.add_worksheet("Confronto singolo edificio")
        ws3.merge_range("B1:E1",
                        f"FILE 3: Analisi energetica - Focus su {target_focus}",
                        fmt["title"])
        headers3 = ["Rango", "Scuola di Riferimento", "Modello IFC Confrontato", "Indice di Somiglianza"]
        for c, h in enumerate(headers3, 1):
            ws3.write(3, c, h, fmt["header"])
        for i, row in enumerate(df_focus.itertuples(index=False), 4):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            ws3.write_number(i, 4, float(row[3]), fmt["percent"])

        # Legenda pesi in colonna J
        _write_weights_legend(ws3, fmt, 3, 9, PESI)

        ws3.set_column("B:B", 12)
        ws3.set_column("C:D", 38)
        ws3.set_column("E:E", 18)
        ws3.set_column("J:J", 55)
        ws3.freeze_panes(4, 1)
        if not df_focus.empty:
            ws3.conditional_format(4, 4, len(df_focus)+4, 4,
                                   {"type": "cell", "criteria": ">", "value": 0.75,
                                    "format": fmt["percent_bold"]})


# ============================================================
# MAIN
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Analisi di somiglianza energetica tra modelli IFC.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Esempi:
  %(prog)s
  %(prog)s --target ferraris --verbose
  %(prog)s --ifc-folder "C:/mie_ifc" --output-folder "./risultati"
"""
    )
    p.add_argument("--ifc-folder", default=DEFAULT_IFC_FOLDER,
                   help=f"Cartella con i file IFC (default: {DEFAULT_IFC_FOLDER})")
    p.add_argument("--output-folder", default=None,
                   help="Cartella di output (default: <ifc-folder>/output)")
    p.add_argument("--pset", default=DEFAULT_PSET,
                   help=f"Nome del Pset (default: {DEFAULT_PSET})")
    p.add_argument("--target", default=DEFAULT_TARGET,
                   help=f"Modello target per il focus (default: {DEFAULT_TARGET})")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Log dettagliato per ogni file")
    return p.parse_args()


def main():
    args = parse_args()

    ifc_folder = args.ifc_folder
    output_folder = args.output_folder or os.path.join(ifc_folder, DEFAULT_OUTPUT_SUBFOLDER)
    output_xlsx = os.path.join(output_folder, "1_matrice_totale_energetica.xlsx")

    print(f"[INFO] Cartella IFC   : {ifc_folder}")
    print(f"[INFO] Output         : {output_xlsx}")
    print(f"[INFO] Pset           : {args.pset}")
    print(f"[INFO] Target focus   : {args.target}")
    print(f"[INFO] Schema pesi    : unico (totale = {sum(PESI.values())})")

    if not os.path.isdir(ifc_folder):
        print(f"[ERRORE] Cartella IFC non trovata: {ifc_folder}")
        sys.exit(1)
    os.makedirs(output_folder, exist_ok=True)

    # --- Ricerca RICORSIVA dei file IFC ---
    ifc_files = []
    for root, _dirs, files in os.walk(ifc_folder):
        for f in files:
            if f.lower().endswith(".ifc"):
                ifc_files.append(os.path.join(root, f))
    ifc_files = sorted(ifc_files)

    if not ifc_files:
        print(f"[STOP] Nessun file IFC trovato in {ifc_folder} (ricerca ricorsiva).")
        return
    print(f"[INFO] Trovati {len(ifc_files)} file IFC (ricerca ricorsiva)")

    # --- Estrazione parametri ---
    all_data = {}
    types_map = {}
    for path in ifc_files:
        file_name = Path(path).name
        try:
            if args.verbose:
                print(f"\n[FILE] {file_name}")
            model = ifcopenshell.open(path)
            feats = extract_project_parameters(model, args.pset, verbose=args.verbose)
            if feats:
                all_data[file_name] = feats
                types_map[file_name] = detect_building_type(feats.get("Tipologia costruttiva"))
                if args.verbose:
                    n_ok = sum(1 for v in feats.values() if v is not None and
                               not (isinstance(v, float) and np.isnan(v)))
                    print(f"  -> tipo={types_map[file_name]}, {n_ok}/{len(feats)} parametri valorizzati")
        except Exception as e:
            print(f"[ERR] {file_name}: {e}")

    if not all_data:
        print("\n[STOP] Nessun dato valido estratto.")
        print(f"  Verifica che il Pset '{args.pset}' esista nei file IFC.")
        print(f"  Usa --verbose per dettagli.")
        return

    print(f"\n[INFO] Dati validi estratti da {len(all_data)}/{len(ifc_files)} file")
    from collections import Counter
    cnt = Counter(types_map.values())
    print(f"[INFO] Tipologie rilevate (solo info): {dict(cnt)}")

    # --- DataFrame ---
    df_features = pd.DataFrame.from_dict(all_data, orient="index")
    if args.verbose:
        print(f"\n[DEBUG] Colonne: {list(df_features.columns)}")

    # --- Matrice di similarita' pesata (schema unico) ---
    df_sim = build_similarity_matrix(df_features).round(6)

    # --- Coppie + Focus ---
    df_pairs = build_pair_ranking(df_sim)
    df_focus, target_used = build_focus_sheet(df_sim, args.target)
    focus_type = types_map.get(target_used, "-")

    # --- Excel ---
    write_excel_output(df_sim, df_pairs, df_focus, target_used, output_xlsx,
                       focus_type=focus_type)
    print(f"\n[OK] File generato: {output_xlsx}")
    if target_used in df_sim.index:
        print(f"[OK] Focus: '{target_used}'")


if __name__ == "__main__":
    main()