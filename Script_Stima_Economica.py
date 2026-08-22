#!/usr/bin/env python3
"""
Script di Stima Economica basata su Somiglianza IFC.

Flusso:
  1. Estrae parametri Pset + quantità geometriche da tutti i modelli IFC
  2. Calcola la matrice di somiglianza (energetica/strutturale)
  3. Dato un modello campione, trova l'edificio più simile
  4. Ipota gli interventi necessari per entrambi
  5. Estrae le quantità geometriche dal modello campione
  6. Stima i costi usando il prezzario Regione Campania 2026
  7. Genera un Excel con analisi completa

Uso:
    python Script_Stima_Economica.py
    python Script_Stima_Economica.py --target ferraris
    python Script_Stima_Economica.py --interventi energia,struttura
    python Script_Stima_Economica.py --verbose
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

from interventi_dict import INTERVENTI, stima_costo, get_interventi_per_tipo
from estrazione_quantita import extract_quantities, build_quantities_dataframe


# ============================================================
# CONFIGURAZIONE
# ============================================================

DEFAULT_IFC_FOLDER = r"C:\Users\pietr\Desktop\Scuole ifc parametri"
DEFAULT_OUTPUT_SUBFOLDER = "output"
DEFAULT_PSET = "Pset_InformazioniProgetto"
DEFAULT_TARGET = "de nicola"
MAX_FILE_SECONDS = 300  # Timeout per file (5 minuti). 0 = nessun limite
MAX_FILE_MB = 1000  # Ignora file più grandi di questo (MB)

# Aree copertura manuali da Revit (override dei valori IFC)
# Ordine importante: nomi più specifici PRIMA per evitare conflitti
MANUALE_ROOF_AREAS = {
    "MARIGLIANO STRUTTURALE": 0,  # solo struttura
    "MARIGLIANO-BIM": 2868,
    "PALESTRA MARIGLIANO": 1300,
    "PALESTRA FERRARIS": 1267.4,
    "IFC STATO DI PROGETTO": 267.3,
    "EDS_E_R": 1258.1,
    "ISTITUTO FERRARIS": 5881.2,
    "ISTITUTO DE NICOLA": 1660.5,
    "BIXIO": 1306.4,
    "CARACCIOLO": 371.7,
    "CARAVAGGIO": 2380.3,
    "CSNV": 1620.7,
    "NAPS": 917.2,
    "DECILLIS": 2391.7,
    "SCOTTI": 1770.3,
    "MEL": 1174.5,
    "MERCALLI": 1777.1,
    "PAGANO": 1131.3,
    "2024.06": 832.14,
    "TILGHER": 1065.5,
    "TORRENTE": 5035,
    "TORRICELLI": 1707,
}

# Interventi già realizzati per modello (chiave = parte del nome file)
# Questi interventi vengono esclusi dalla proposta e mostrati nel censimento
INTERVENTI_GIA_REALIZZATI = {
    "DE NICOLA": [
        "isolamento_tetto",
        "adeguamento_sismico_colonne",
    ],
}


# ============================================================
# MAPPING PROPRIETA' IFC (dai tuoi script esistenti)
# ============================================================

PROP_MAP = [
    ("altezza_max",    "Altezza massima fuoriterra valutata in gronda"),
    ("altezza_min",    "Altezza minima fuoriterra valutata in gronda"),
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

# Pesi energetici
PESI_ENERGETICI = {
    "Zona climatica":                                         5,
    "Anno di costruzione":                                    5,
    "Distanza dal mare":                                      4,
    "Superficie involucro esterna":                           4,
    "Rapporto di porosita teorica":                           2,
    "Profondita di carbonatazione stimata":                   1,
    "Tipologia costruttiva":                                  2,
    "Volume degli elementi strutturali":                      2,
    "Altezza massima fuoriterra valutata in gronda":          2,
    "Altezza minima fuoriterra valutata in gronda":           2,
    "Configurazione planimetrica rapporto \u03b21 = a/l":     1,
    "Configurazione planimetrica rapporto \u03b22 = b/l":     1,
    "Classe di esposizione":                                  1,
    "Zona sismica":                                           1,
}

# Pesi strutturali
PESI_STRUTTURALI = {
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


# ============================================================
# FUNZIONI SIMILARITÀ (dai tuoi script)
# ============================================================

def try_parse_number(val):
    if pd.isna(val) or val is None:
        return np.nan
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val)
    s = str(val).strip()
    s_clean = re.sub(
        r'\s*(m|m2|m3|m²|m³|cm|mm|kg|%|km|years|anni|°C|W/m2K|W/m²K)\s*$',
        '', s, flags=re.IGNORECASE
    ).strip()
    s_clean = s_clean.replace(',', '.')
    try:
        return float(s_clean)
    except (ValueError, TypeError):
        return str(val).strip()


def extract_project_parameters(model, pset_name, verbose=False):
    pset_data = {nome: None for _, nome in PROP_MAP}
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
                        for chiave, nome in PROP_MAP:
                            if chiave in ifc_prop_name:
                                pset_data[nome] = try_parse_number(prop.NominalValue.wrappedValue)
                                break

    if not pset_found:
        return None
    return pset_data


def similarity_for_value(v1, v2):
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


def build_similarity_matrix(df_features, pesi):
    models = df_features.index.tolist()
    n = len(models)
    M = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            punteggio = 0.0
            somma = 0.0
            for param, peso in pesi.items():
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


def build_pair_ranking(df_similarity):
    models = df_similarity.index.tolist()
    pairs = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            pairs.append({
                "Posizione": 0,
                "Primo Modello": models[i],
                "Secondo Modello": models[j],
                "Somiglianza": float(df_similarity.iloc[i, j])
            })
    df = pd.DataFrame(pairs)
    if df.empty:
        return df
    df = df.sort_values(by="Somiglianza", ascending=False).reset_index(drop=True)
    df["Posizione"] = np.arange(1, len(df) + 1)
    return df


def build_focus_sheet(df_similarity, target_substring):
    target_name = next(
        (idx for idx in df_similarity.index if target_substring.lower() in idx.lower()),
        None
    )
    if target_name is None:
        return pd.DataFrame(), "N/A"
    series = (df_similarity.loc[target_name]
              .drop(labels=[target_name], errors="ignore")
              .sort_values(ascending=False))
    rows = []
    for i, (name, value) in enumerate(series.items(), start=1):
        rows.append({
            "Rango": i,
            "Edificio Riferimento": target_name,
            "Modello Confrontato": name,
            "Indice Somiglianza": float(value)
        })
    return pd.DataFrame(rows), target_name


def build_sample_focus_sheet(df_sim_energ, df_sim_strut, target_substring,
                             all_pset_data, all_quantities, all_costs,
                             censimento_interventi=None):
    """
    Costruisce i dati per il foglio "8_Campione":
    - Trova il modello target e il suo vicino più simile
    - Interventi del vicino = dal censimento (già fatti)
    - Interventi del campione = SOLO NUOVI (esclusi quelli del censimento)
    """
    if censimento_interventi is None:
        censimento_interventi = set()

    # Trova il target
    target_name = next(
        (idx for idx in df_sim_energ.index if target_substring.lower() in idx.lower()),
        None
    )
    if target_name is None:
        return None

    # Vicino più simile
    if target_name in df_sim_energ.index:
        sim_energ = df_sim_energ.loc[target_name].drop(labels=[target_name], errors="ignore")
        sim_strut = df_sim_strut.loc[target_name].drop(labels=[target_name], errors="ignore")
    else:
        return None

    common = sim_energ.index.intersection(sim_strut.index)
    sim_media = ((sim_energ[common] + sim_strut[common]) / 2).sort_values(ascending=False)

    if sim_media.empty:
        return None

    vicino_name = sim_media.index[0]
    vicino_sim_energ = float(sim_energ[vicino_name])
    vicino_sim_strut = float(sim_strut[vicino_name])
    vicino_sim_media = float(sim_media[vicino_name])

    # Interventi del vicino più simile (tutti)
    interv_vicino = all_costs.get(vicino_name, [])

    # Interventi già fatti sul campione (da INTERVENTI_GIA_REALIZZATI)
    gia_fatti = set(_get_interventi_esclusi(target_name))

    # Interventi del vicino MA non ancora fatti sul campione → da proporre
    interv_da_proporre = [i for i in interv_vicino if i["codice"] not in gia_fatti]

    # Distribuzione quantità per il campione
    pset_campione = all_pset_data.get(target_name, {})
    qty_campione = distribute_quantities(all_quantities.get(target_name, {}), pset_campione, target_name)

    # Ricalcola costi usando le quantità del campione
    from interventi_dict import INTERVENTI
    interv_campione = []
    for interv in interv_da_proporre:
        codice = interv["codice"]
        if codice in INTERVENTI:
            interv_def = INTERVENTI[codice]
            entita = interv_def["entita_ifc"]

            ifc_qty_map = {
                "IfcWall": qty_campione.get("superficie_involucro", 0),
                "IfcWallStandardCase": qty_campione.get("superficie_involucro", 0),
                "IfcWindow": qty_campione.get("num_windows", 0),
                "IfcDoor": qty_campione.get("num_doors", 0),
                "IfcColumn": qty_campione.get("num_columns", 0),
                "IfcBeam": qty_campione.get("num_beams", 0),
                "IfcMember": qty_campione.get("num_beams", 0),
                "IfcSlab": qty_campione.get("num_slabs", 0),
                "IfcPlate": qty_campione.get("num_slabs", 0),
                "IfcRoof": qty_campione.get("area_roofs", 0),
                "IfcStair": qty_campione.get("num_stairs", 0),
                "IfcStairFlight": qty_campione.get("num_stairs", 0),
                "IfcBuilding": 1,
                "IfcBuildingStorey": qty_campione.get("num_storeys", 0),
                "IfcFooting": qty_campione.get("num_columns", 0),
                "IfcPile": qty_campione.get("num_columns", 0),
            }

            qty_val = 0
            for e in entita:
                if e in ifc_qty_map and ifc_qty_map[e] > 0:
                    qty_val = ifc_qty_map[e]
                    break
            if qty_val == 0:
                for e in entita:
                    if e in ifc_qty_map:
                        qty_val = ifc_qty_map[e]
                        break

            stima = stima_costo(codice, qty_val)
            if stima:
                stima["quantita_campione"] = qty_val
                stima["note"] = interv_def["prezzario"].get("note", "")
                interv_campione.append(stima)

    return {
        "target_name": target_name,
        "vicino_name": vicino_name,
        "sim_energ": vicino_sim_energ,
        "sim_strut": vicino_sim_strut,
        "sim_media": vicino_sim_media,
        "qty_campione": qty_campione,
        "interventi_vicino": interv_vicino,
        "interventi_campione": interv_campione,
        "totale_energetico": sum(c["costo_totale"] for c in interv_campione if c["tipo"] == "energetico"),
        "totale_strutturale": sum(c["costo_totale"] for c in interv_campione if c["tipo"] == "strutturale"),
        "totale_complessivo": sum(c["costo_totale"] for c in interv_campione),
    }


# ============================================================
# LOGICA INTERVENTI
# ============================================================

# Rapporti tipici per edifici scolastici campani
RAPPORTO_PARETI_INVOLUCRO = 0.70   # 70% dell'involucro = pareti esterne
RAPPORTO_COPERTURA_INVOLUCRO = 0.30  # 30% dell'involucro = copertura
AREA_MEDIA_FINESTRA = 2.5   # m² per finestra (media scuole)
AREA_MEDIA_PORTA = 2.0      # m² per porta


def distribute_quantities(qty, pset, model_name=""):
    """
    Distribuisce i valori Pset sulle quantità geometriche.
    - Superficie involucro esterna → valore diretto dal Pset
    - Volume strutturale → valore diretto dal Pset
    - Area copertura → da Pset_RoofCommon.TotalArea, fallback: MANUALE, poi 30% involucro
    - Area finestre → conteggio × 2.5 m²/media
    - Area porte → conteggio × 2.0 m²/media
    """
    qty = qty.copy()

    # Valori diretti dal Pset
    involucro = pset.get("Superficie involucro esterna")
    if involucro and isinstance(involucro, (int, float)) and involucro > 0:
        qty["superficie_involucro"] = float(involucro)

    vol = pset.get("Volume degli elementi strutturali")
    if vol and isinstance(vol, (int, float)) and vol > 0:
        qty["volume_strutturale"] = float(vol)

    # Area copertura: OVERRIDE manuale → IFC → fallback 30%
    # 1. Se c'è un valore manuale, usa quello (sempre)
    manual_override = False
    for key, area in MANUALE_ROOF_AREAS.items():
        if key.upper() in model_name.upper():
            qty["area_roofs"] = area
            manual_override = True
            break
    
    # 2. Se non c'è override manuale e IFC=0, fallback 30% involucro
    if not manual_override and qty.get("area_roofs", 0) == 0 and involucro:
        has_roof_elements = qty.get("num_roofs", 0) > 0 or qty.get("num_beams", 0) > 0
        is_structural_only = qty.get("num_walls_ext", 0) == 0 and qty.get("num_windows", 0) == 0
        if has_roof_elements and not is_structural_only:
            qty["area_roofs"] = float(involucro) * 0.30

    # Area finestre = conteggio × area media
    qty["area_windows"] = qty.get("num_windows", 0) * AREA_MEDIA_FINESTRA
    qty["area_doors"] = qty.get("num_doors", 0) * AREA_MEDIA_PORTA

    return qty


def _get_interventi_esclusi(model_name):
    """Restituisce la lista degli interventi già realizzati per un modello."""
    for key, interventi in INTERVENTI_GIA_REALIZZATI.items():
        if key.upper() in model_name.upper():
            return interventi
    return []


def hypothesize_interventions(params_pset, quantities, target_type="both", interventi_da_escludere=None):
    """
    Ipota gli interventi necessari in base ai parametri del Pset e le quantità estratte.
    Max 5 interventi: 3 energetici + 2 strutturali (solo se plausibili).
    interventi_da_escludere: lista di interventi già realizzati da escludere.
    """
    if interventi_da_escludere is None:
        interventi_da_escludere = set()
    else:
        interventi_da_escludere = set(interventi_da_escludere)
    interventions = {}

    anno = params_pset.get("Anno di costruzione")
    sismica = params_pset.get("Zona sismica")
    mare = params_pset.get("Distanza dal mare")

    involucro = quantities.get("superficie_involucro", 0)
    has_walls = involucro > 100
    has_roofs = quantities.get("area_roofs", 0) > 50
    has_windows = quantities.get("num_windows", 0) > 5
    has_cols = quantities.get("num_columns", 0) > 3
    has_beams = quantities.get("num_beams", 0) > 3

    vecchio = anno and isinstance(anno, (int, float)) and anno < 2000
    molto_vecchio = anno and isinstance(anno, (int, float)) and anno < 1970
    zona_sismica = sismica and isinstance(sismica, (int, float)) and sismica >= 2

    # --- ENERGETICO (max 3) ---
    if target_type in ["energetico", "both"]:
        if vecchio and has_walls and "isolamento_pareti_esterne" not in interventi_da_escludere:
            interventions["isolamento_pareti_esterne"] = involucro
        if vecchio and has_roofs and "isolamento_tetto" not in interventi_da_escludere:
            interventions["isolamento_tetto"] = quantities["area_roofs"]
        if has_windows and "sostituzione_infissi" not in interventi_da_escludere:
            interventions["sostituzione_infissi"] = quantities["num_windows"]

    # --- STRUTTURALE (max 2) ---
    if target_type in ["strutturale", "both"]:
        if zona_sismica and has_cols and "adeguamento_sismico_colonne" not in interventi_da_escludere:
            interventions["adeguamento_sismico_colonne"] = quantities["num_columns"]
        if molto_vecchio and has_beams and "adeguamento_sismico_travi" not in interventi_da_escludere:
            interventions["adeguamento_sismico_travi"] = quantities["num_beams"]

    return interventions


def estimate_costs(interventions, quantities):
    """
    Stima i costi per gli interventi ipotizzati.
    """
    results = []
    for codice, quantita in interventions.items():
        stima = stima_costo(codice, quantita)
        if stima:
            stima["quantita_estratta"] = quantita
            results.append(stima)
    return results


# ============================================================
# GENERATORE EXCEL
# ============================================================

def build_formats(workbook):
    return {
        "title":   workbook.add_format({"bold": True, "font_size": 14, "align": "center", "valign": "vcenter", "bg_color": "#C65911", "font_color": "#FFFFFF", "border": 1}),
        "section": workbook.add_format({"bold": True, "font_size": 11, "align": "left", "valign": "vcenter", "bg_color": "#F4B183", "border": 1}),
        "header":  workbook.add_format({"bold": True, "text_wrap": True, "align": "center", "valign": "vcenter", "font_color": "#FFFFFF", "bg_color": "#C65911", "border": 1}),
        "row_name":workbook.add_format({"bold": True, "align": "left", "valign": "vcenter", "bg_color": "#F8CBAD", "border": 1}),
        "text":    workbook.add_format({"align": "left", "valign": "vcenter", "border": 1, "text_wrap": True}),
        "index":   workbook.add_format({"align": "center", "valign": "vcenter", "border": 1}),
        "percent": workbook.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "border": 1}),
        "percent_bold": workbook.add_format({"num_format": "0.00%", "align": "center", "valign": "vcenter", "bg_color": "#FCE4D6", "bold": True, "border": 1}),
        "euro":    workbook.add_format({"num_format": "#,##0.00 €", "align": "right", "valign": "vcenter", "border": 1}),
        "euro_bold":workbook.add_format({"num_format": "#,##0.00 €", "align": "right", "valign": "vcenter", "bg_color": "#FFF2CC", "bold": True, "border": 1}),
        "euro_header": workbook.add_format({"bold": True, "text_wrap": True, "align": "center", "valign": "vcenter", "font_color": "#FFFFFF", "bg_color": "#C00000", "border": 1}),
        "note":    workbook.add_format({"italic": True, "font_size": 9, "align": "left", "valign": "vcenter", "border": 1}),
        "warning": workbook.add_format({"bold": True, "font_color": "#C00000", "align": "left", "valign": "vcenter", "border": 1}),
    }


def write_excel_output(df_sim_energ, df_sim_strut, df_pairs_energ, df_pairs_strut,
                       df_focus_energ, df_focus_strut,
                       target_energ, target_strut,
                       quantities_data, costs_data,
                       output_path, interventions_per_model,
                       sample_data=None, target_name=None):
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        wb = writer.book
        fmt = build_formats(wb)

        # ============ FOGLIO 1: MATRICE ENERGETICA ============
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
            ws1.conditional_format(3, 1, len(df_sim_energ)+3, len(df_sim_energ.columns),
                                   {"type": "cell", "criteria": ">", "value": 0.75,
                                    "format": fmt["percent_bold"]})

        # Tabella pesi energetici
        peso_start_row = len(df_sim_energ) + 5
        ws1.merge_range(peso_start_row, 0, peso_start_row, 2, "PESI PARAMETRI ENERGETICI", fmt["section"])
        ws1.write(peso_start_row + 1, 0, "Parametro", fmt["header"])
        ws1.write(peso_start_row + 1, 1, "Peso", fmt["header"])
        for i, (param, peso) in enumerate(PESI_ENERGETICI.items()):
            ws1.write(peso_start_row + 2 + i, 0, param, fmt["text"])
            ws1.write_number(peso_start_row + 2 + i, 1, peso, fmt["index"])

        # ============ FOGLIO 2: MATRICE STRUTTURALE ============
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
            ws2.conditional_format(3, 1, len(df_sim_strut)+3, len(df_sim_strut.columns),
                                   {"type": "cell", "criteria": ">", "value": 0.75,
                                    "format": fmt["percent_bold"]})

        # Tabella pesi strutturali
        peso_start_row = len(df_sim_strut) + 5
        ws2.merge_range(peso_start_row, 0, peso_start_row, 2, "PESI PARAMETRI STRUTTURALI", fmt["section"])
        ws2.write(peso_start_row + 1, 0, "Parametro", fmt["header"])
        ws2.write(peso_start_row + 1, 1, "Peso", fmt["header"])
        for i, (param, peso) in enumerate(PESI_STRUTTURALI.items()):
            ws2.write(peso_start_row + 2 + i, 0, param, fmt["text"])
            ws2.write_number(peso_start_row + 2 + i, 1, peso, fmt["index"])

        # ============ FOGLIO 3: CLASSIFICA COPPIE ============
        ws3 = wb.add_worksheet("3_Classifica Coppie")
        ws3.merge_range("A1:F1", "CLASSIFICA COPPIE PER SOMIGLIANZA", fmt["title"])

        # Filtra coppie: escludi 100%, ordina per somiglianza decrescente
        df_pairs_energ_f = df_pairs_energ[df_pairs_energ["Somiglianza"] < 1.0].copy()
        df_pairs_strut_f = df_pairs_strut[df_pairs_strut["Somiglianza"] < 1.0].copy()

        # Energetica
        ws3.write(3, 0, "SOMIGLIANZA ENERGETICA", fmt["section"])
        headers = ["Pos.", "Modello 1", "Modello 2", "Somiglianza"]
        for c, h in enumerate(headers, 1):
            ws3.write(4, c, h, fmt["header"])
        for i, row in enumerate(df_pairs_energ_f.itertuples(index=False), 5):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            val = float(row[3])
            fmt_cell = fmt["percent_bold"] if val > 0.75 else fmt["percent"]
            ws3.write_number(i, 4, val, fmt_cell)

        # Strutturale
        start_row = len(df_pairs_energ_f) + 7
        ws3.write(start_row, 0, "SOMIGLIANZA STRUTTURALE", fmt["section"])
        for c, h in enumerate(headers, 1):
            ws3.write(start_row + 1, c, h, fmt["header"])
        for i, row in enumerate(df_pairs_strut_f.itertuples(index=False), start_row + 2):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            val = float(row[3])
            fmt_cell = fmt["percent_bold"] if val > 0.75 else fmt["percent"]
            ws3.write_number(i, 4, val, fmt_cell)

        ws3.set_column("A:A", 8)
        ws3.set_column("B:D", 38)
        ws3.set_column("E:E", 15)

        # ============ FOGLIO 4: FOCUS ============
        ws4 = wb.add_worksheet("4_Focus Edificio")
        ws4.merge_range("A1:E1", f"ANALISI FOCUS: {target_energ.upper()}", fmt["title"])

        # Filtra: escludi 100%
        df_focus_energ_f = df_focus_energ[df_focus_energ["Indice Somiglianza"] < 1.0].copy()
        df_focus_strut_f = df_focus_strut[df_focus_strut["Indice Somiglianza"] < 1.0].copy()

        # Focus energetico
        ws4.write(3, 0, "SOMIGLIANZA ENERGETICA", fmt["section"])
        headers_f = ["Rango", "Edificio Riferimento", "Modello Confrontato", "Indice Somiglianza"]
        for c, h in enumerate(headers_f, 1):
            ws4.write(4, c, h, fmt["header"])
        for i, row in enumerate(df_focus_energ_f.itertuples(index=False), 5):
            ws4.write_number(i, 1, int(row[0]), fmt["index"])
            ws4.write(i, 2, row[1], fmt["text"])
            ws4.write(i, 3, row[2], fmt["text"])
            val = float(row[3])
            fmt_cell = fmt["percent_bold"] if val > 0.75 else fmt["percent"]
            ws4.write_number(i, 4, val, fmt_cell)

        # Focus strutturale
        start_row = len(df_focus_energ_f) + 7
        ws4.write(start_row, 0, "SOMIGLIANZA STRUTTURALE", fmt["section"])
        for c, h in enumerate(headers_f, 1):
            ws4.write(start_row + 1, c, h, fmt["header"])
        for i, row in enumerate(df_focus_strut_f.itertuples(index=False), start_row + 2):
            ws4.write_number(i, 1, int(row[0]), fmt["index"])
            ws4.write(i, 2, row[1], fmt["text"])
            ws4.write(i, 3, row[2], fmt["text"])
            val = float(row[3])
            fmt_cell = fmt["percent_bold"] if val > 0.75 else fmt["percent"]
            ws4.write_number(i, 4, val, fmt_cell)

        ws4.set_column("A:A", 8)
        ws4.set_column("B:D", 38)
        ws4.set_column("E:E", 15)

        # ============ FOGLIO 5: QUANTITÀ ============
        ws5 = wb.add_worksheet("5_Quantità Geometriche")
        ws5.merge_range("A1:J1", "QUANTITÀ GEOMETRICHE ESTRATTE DAI MODELLI IFC", fmt["title"])

        if quantities_data:
            # Filtra colonne con almeno un valore > 0
            HEADERS_RENAME = {
                "area_roofs": "Superficie copertura",
                "superficie_involucro": "Superficie involucro",
                "volume_strutturale": "Volume strutturale",
                "num_windows": "N. finestre",
                "num_doors": "N. porte",
                "num_columns": "N. colonne",
                "num_beams": "N. travi",
                "num_slabs": "N. solai",
                "num_roofs": "N. coperture",
                "num_stairs": "N. scale",
                "num_walls_ext": "N. pareti esterne",
                "area_windows": "Area finestre",
                "area_doors": "Area porte",
            }
            all_headers = list(quantities_data[list(quantities_data.keys())[0]].keys())
            headers_q = []
            for h in all_headers:
                has_value = any(qty.get(h, 0) > 0 for qty in quantities_data.values())
                if has_value:
                    headers_q.append(h)

            ws5.write(3, 0, "Modello", fmt["header"])
            for c, h in enumerate(headers_q, 1):
                display_name = HEADERS_RENAME.get(h, h)
                ws5.write(3, c, display_name, fmt["header"])

            for r, (model_name, qty) in enumerate(quantities_data.items(), 4):
                ws5.write(r, 0, model_name, fmt["row_name"])
                for c, h in enumerate(headers_q, 1):
                    val = qty.get(h, 0)
                    ws5.write_number(r, c, float(val) if val else 0, fmt["index"])

        ws5.set_column(0, 0, 42)
        ws5.set_column(1, 50, 15)

        # ============ FOGLIO 6: STIMA COSTI ============
        ws6 = wb.add_worksheet("6_Censimento Interventi")
        ws6.merge_range("A1:J1", "CENSIMENTO INTERVENTI - PREZZARIO CAMPANIA 2026", fmt["title"])

        target_name_for_filter = sample_data["target_name"] if sample_data else None
        gia_fatti_target = set(_get_interventi_esclusi(target_name_for_filter)) if target_name_for_filter else set()

        current_row = 3
        for model_name, costs in costs_data.items():
            ws6.write(current_row, 0, f"MODELLO: {model_name}", fmt["section"])
            current_row += 1

            headers_c = ["Codice Intervento", "Nome Intervento", "Tipo", "Quantit",
                         "Unit", "Prezzo Unit.", "Codice Prezzario", "Costo Totale"]
            for c, h in enumerate(headers_c, 0):
                if c == 7:
                    ws6.write(current_row, c, h, fmt["euro_header"])
                else:
                    ws6.write(current_row, c, h, fmt["header"])
            current_row += 1

            # Per il campione: mostra SOLO quelli gia fatti; per gli altri: tutti
            if model_name == target_name_for_filter:
                costs_filtrati = [c for c in costs if c["codice"] in gia_fatti_target]
            else:
                costs_filtrati = costs

            totale_modello = 0
            for cost in costs_filtrati:
                ws6.write(current_row, 0, cost["codice"], fmt["text"])
                ws6.write(current_row, 1, cost["nome"], fmt["text"])
                ws6.write(current_row, 2, cost["tipo"], fmt["text"])
                ws6.write_number(current_row, 3, cost["quantita"], fmt["index"])
                ws6.write(current_row, 4, cost["unita_misura"], fmt["text"])
                ws6.write_number(current_row, 5, cost["prezzo_unitario"], fmt["euro"])
                ws6.write(current_row, 6, cost["codice_prezzario"], fmt["text"])
                ws6.write_number(current_row, 7, cost["costo_totale"], fmt["euro"])
                totale_modello += cost["costo_totale"]
                current_row += 1

            ws6.write(current_row, 6, "TOTALE MODELLO:", fmt["euro_bold"])
            ws6.write_number(current_row, 7, totale_modello, fmt["euro_bold"])
            current_row += 2

        ws6.set_column("A:A", 28)
        ws6.set_column("B:B", 42)
        ws6.set_column("C:C", 14)
        ws6.set_column("D:E", 12)
        ws6.set_column("F:F", 14)
        ws6.set_column("G:G", 28)
        ws6.set_column("H:H", 16)

        # ============ FOGLIO 7: RIEPILOGO ============
        ws7 = wb.add_worksheet("7_Riepilogo")
        ws7.merge_range("A1:F1", "RIEPILOGO STIMA ECONOMICA", fmt["title"])
        ws7.write(3, 0, "Modello", fmt["header"])
        ws7.write(3, 1, "Tipo Analisi", fmt["header"])
        ws7.write(3, 2, "N. Interventi", fmt["header"])
        ws7.write(3, 3, "Costo Totale", fmt["euro_header"])

        r = 4
        for model_name, costs in costs_data.items():
            energetici = [c for c in costs if c["tipo"] == "energetico"]
            strutturali = [c for c in costs if c["tipo"] == "strutturale"]

            if energetici:
                ws7.write(r, 0, model_name, fmt["row_name"])
                ws7.write(r, 1, "Energetico", fmt["text"])
                ws7.write_number(r, 2, len(energetici), fmt["index"])
                ws7.write_number(r, 3, sum(c["costo_totale"] for c in energetici), fmt["euro"])
                r += 1

            if strutturali:
                ws7.write(r, 0, model_name, fmt["row_name"])
                ws7.write(r, 1, "Strutturale", fmt["text"])
                ws7.write_number(r, 2, len(strutturali), fmt["index"])
                ws7.write_number(r, 3, sum(c["costo_totale"] for c in strutturali), fmt["euro"])
                r += 1

            ws7.write(r, 0, model_name, fmt["row_name"])
            ws7.write(r, 1, "TOTALE", fmt["section"])
            ws7.write_number(r, 2, len(costs), fmt["index"])
            ws7.write_number(r, 3, sum(c["costo_totale"] for c in costs), fmt["euro_bold"])
            r += 1

        ws7.set_column("A:A", 42)
        ws7.set_column("B:B", 16)
        ws7.set_column("C:C", 14)
        ws7.set_column("D:D", 18)

        # ============ FOGLIO 8: CAMPIONE ============
        if sample_data:
            ws8 = wb.add_worksheet("8_Campione")
            ws8.merge_range("A1:G1", "ANALISI ECONOMICA MODELLO CAMPIONE", fmt["title"])

            r = 3
            ws8.write(r, 0, "Modello Campione:", fmt["section"])
            ws8.write(r, 1, sample_data["target_name"], fmt["row_name"])
            r += 1
            ws8.write(r, 0, "Edificio Più Simile:", fmt["section"])
            ws8.write(r, 1, sample_data["vicino_name"], fmt["row_name"])
            r += 1
            ws8.write(r, 0, "Somiglianza Energetica:", fmt["section"])
            ws8.write_number(r, 1, sample_data["sim_energ"], fmt["percent"])
            r += 1
            ws8.write(r, 0, "Somiglianza Strutturale:", fmt["section"])
            ws8.write_number(r, 1, sample_data["sim_strut"], fmt["percent"])
            r += 1
            ws8.write(r, 0, "Somiglianza Media:", fmt["section"])
            ws8.write_number(r, 1, sample_data["sim_media"], fmt["percent_bold"])
            r += 2

            # Quantità del campione
            ws8.write(r, 0, "QUANTITÀ ESTRA DAL MODELLO CAMPIONE", fmt["section"])
            r += 1
            qty = sample_data["qty_campione"]
            qty_items = [
                ("Superficie involucro esterna", qty.get("superficie_involucro", 0), "m²"),
                ("Area copertura", qty.get("area_roofs", 0), "m²"),
                ("Pareti esterne", qty.get("num_walls_ext", 0), "nr"),
                ("Finestre", qty.get("num_windows", 0), "nr"),
                ("Porte", qty.get("num_doors", 0), "nr"),
                ("Colonne", qty.get("num_columns", 0), "nr"),
                ("Travi", qty.get("num_beams", 0), "nr"),
                ("Solai", qty.get("num_slabs", 0), "nr"),
                ("Coperture", qty.get("num_roofs", 0), "nr"),
                ("Scale", qty.get("num_stairs", 0), "nr"),
                ("Volume strutturale", qty.get("volume_strutturale", 0), "m³"),
            ]
            ws8.write(r, 0, "Parametro", fmt["header"])
            ws8.write(r, 1, "Valore", fmt["header"])
            ws8.write(r, 2, "Unità", fmt["header"])
            r += 1
            for nome, val, um in qty_items:
                ws8.write(r, 0, nome, fmt["text"])
                ws8.write_number(r, 1, float(val), fmt["index"])
                ws8.write(r, 2, um, fmt["text"])
                r += 1
            r += 1

            headers_c = ["Codice", "Intervento", "Tipo", "Quantità",
                         "Unità", "Prezzo Unit.", "Costo Totale", "Note"]

            # Interventi del vicino (censimento = già fatti)
            interv_vicino = sample_data.get("interventi_vicino", [])
            if interv_vicino:
                ws8.write(r, 0, "INTERVENTI DEL VICINO PIÙ SIMILE (CENSIMENTO - GIÀ REALIZZATI)", fmt["section"])
                r += 1
                for c, h in enumerate(headers_c):
                    if c == 6:
                        ws8.write(r, c, h, fmt["euro_header"])
                    else:
                        ws8.write(r, c, h, fmt["header"])
                r += 1
                tot_vicino = 0
                for cost in interv_vicino:
                    ws8.write(r, 0, cost["codice_prezzario"], fmt["text"])
                    ws8.write(r, 1, cost["nome"], fmt["text"])
                    ws8.write(r, 2, cost["tipo"], fmt["text"])
                    ws8.write_number(r, 3, cost["quantita"], fmt["index"])
                    ws8.write(r, 4, cost["unita_misura"], fmt["text"])
                    ws8.write_number(r, 5, cost["prezzo_unitario"], fmt["euro"])
                    ws8.write_number(r, 6, cost["costo_totale"], fmt["euro"])
                    ws8.write(r, 7, cost.get("note", ""), fmt["note"])
                    tot_vicino += cost["costo_totale"]
                    r += 1
                ws8.write(r, 5, "TOTALE VICINO:", fmt["euro_bold"])
                ws8.write_number(r, 6, tot_vicino, fmt["euro_bold"])
                r += 2

            # Interventi NUOVI per il campione
            interv_campione = sample_data.get("interventi_campione", [])
            if interv_campione:
                ws8.write(r, 0, "INTERVENTI NUOVI PROPOSTI PER IL CAMPIONE (ESCLUSI QUELLI GIÀ CENSITI)", fmt["section"])
                r += 1
                for c, h in enumerate(headers_c):
                    if c == 6:
                        ws8.write(r, c, h, fmt["euro_header"])
                    else:
                        ws8.write(r, c, h, fmt["header"])
                r += 1

                tot_energ = 0
                tot_strut = 0
                for cost in interv_campione:
                    ws8.write(r, 0, cost["codice_prezzario"], fmt["text"])
                    ws8.write(r, 1, cost["nome"], fmt["text"])
                    ws8.write(r, 2, cost["tipo"], fmt["text"])
                    ws8.write_number(r, 3, cost["quantita"], fmt["index"])
                    ws8.write(r, 4, cost["unita_misura"], fmt["text"])
                    ws8.write_number(r, 5, cost["prezzo_unitario"], fmt["euro"])
                    ws8.write_number(r, 6, cost["costo_totale"], fmt["euro"])
                    ws8.write(r, 7, cost.get("note", ""), fmt["note"])
                    if cost["tipo"] == "energetico":
                        tot_energ += cost["costo_totale"]
                    else:
                        tot_strut += cost["costo_totale"]
                    r += 1

                r += 1
                ws8.write(r, 4, "TOTALE ENERGETICO:", fmt["euro_bold"])
                ws8.write_number(r, 6, tot_energ, fmt["euro_bold"])
                r += 1
                ws8.write(r, 4, "TOTALE STRUTTURALE:", fmt["euro_bold"])
                ws8.write_number(r, 6, tot_strut, fmt["euro_bold"])
                r += 1
                ws8.write(r, 4, "TOTALE COMPLESSIVO:", fmt["euro_bold"])
                ws8.write_number(r, 6, tot_energ + tot_strut, fmt["euro_bold"])

            ws8.set_column("A:A", 28)
            ws8.set_column("B:B", 42)
            ws8.set_column("C:C", 14)
            ws8.set_column("D:D", 12)
            ws8.set_column("E:E", 10)
            ws8.set_column("F:F", 14)
            ws8.set_column("G:G", 16)
            ws8.set_column("H:H", 50)


# ============================================================
# MAIN
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Stima economica basata su somiglianza IFC.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--ifc-folder", default=DEFAULT_IFC_FOLDER,
                   help=f"Cartella IFC (default: {DEFAULT_IFC_FOLDER})")
    p.add_argument("--output-folder", default=None,
                   help="Cartella output")
    p.add_argument("--pset", default=DEFAULT_PSET)
    p.add_argument("--target", default=DEFAULT_TARGET)
    p.add_argument("--interventi", default="energia,struttura",
                   help="Tipi interventi: energia, struttura, o entrambi separati da virgola")
    p.add_argument("--timeout", type=int, default=MAX_FILE_SECONDS,
                   help=f"Timeout per file IFC in secondi (default: {MAX_FILE_SECONDS}, 0=nessun limite)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    ifc_folder = args.ifc_folder
    output_folder = args.output_folder or os.path.join(ifc_folder, "output")
    output_xlsx = os.path.join(output_folder, "Stima_Economica_Completa.xlsx")

    # Timeout per file
    global MAX_FILE_SECONDS
    MAX_FILE_SECONDS = args.timeout

    # Tipi interventi
    tipi_interventi = [t.strip() for t in args.interventi.split(",")]
    target_type = "both" if len(tipi_interventi) > 1 else tipi_interventi[0]

    print("=" * 60)
    print("  STIMA ECONOMICA BASATA SU SOMIGLIANZA IFC")
    print("  Prezzario Regione Campania 2026")
    print("=" * 60)
    print(f"  Cartella IFC   : {ifc_folder}")
    print(f"  Output         : {output_xlsx}")
    print(f"  Target focus   : {args.target}")
    print(f"  Tipo interventi: {target_type}")
    print("=" * 60)

    if not os.path.isdir(ifc_folder):
        print(f"[ERRORE] Cartella non trovata: {ifc_folder}")
        sys.exit(1)
    os.makedirs(output_folder, exist_ok=True)

    # 1. Trova file IFC (ordinati dal più piccolo al più grande)
    ifc_files = []
    for root, _dirs, files in os.walk(ifc_folder):
        for f in files:
            if f.lower().endswith(".ifc"):
                full_path = os.path.join(root, f)
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                ifc_files.append((size_mb, full_path))
    ifc_files.sort(key=lambda x: x[0])  # Dal più piccolo
    ifc_files = [(s, p) for s, p in ifc_files if s <= MAX_FILE_MB]
    ifc_paths = [p for _, p in ifc_files]

    if not ifc_paths:
        print("[STOP] Nessun file IFC trovato.")
        return

    print(f"\n[1/5] Trovati {len(ifc_paths)} file IFC (ordinati per dimensione, max {MAX_FILE_MB}MB)")
    for size, path in ifc_files:
        name = Path(path).name
        print(f"  {size:7.1f} MB  {name[:55]}")
    print()

    # 2. Estrai parametri Pset + quantità geometriche
    all_pset_data = {}
    all_quantities = {}
    n_files = len(ifc_paths)
    skipped_files = []

    import time

    for i, path in enumerate(ifc_paths, 1):
        name = Path(path).name
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  [{i}/{n_files}] {name[:50]} ({size_mb:.0f}MB)...", end=" ", flush=True)
        t0 = time.time()
        try:
            model = ifcopenshell.open(path)
            t_open = time.time() - t0

            # Se l'apertura ha già superato il timeout, salta l'estrazione
            if MAX_FILE_SECONDS > 0 and t_open > MAX_FILE_SECONDS:
                print(f"SALTO (apertura {t_open:.0f}s > {MAX_FILE_SECONDS}s)")
                skipped_files.append(name)
                continue

            # Parametri Pset
            pset = extract_project_parameters(model, args.pset, verbose=args.verbose)
            if pset:
                all_pset_data[name] = pset

            # Quantità geometriche (ottimizzata: solo conteggio entità)
            qty = extract_quantities(model)
            all_quantities[name] = qty

            elapsed = time.time() - t0
            print(f"OK ({elapsed:.1f}s)")

        except Exception as e:
            elapsed = time.time() - t0
            print(f"ERR ({elapsed:.1f}s): {e}")

    if not all_pset_data:
        print("[STOP] Nessun dato Pset estratto.")
        return

    print(f"\n[2/5] Parametri estratti da {len(all_pset_data)} modelli, "
          f"quantità da {len(all_quantities)} modelli")
    if skipped_files:
        print(f"  File saltati (> {MAX_FILE_SECONDS}s): {len(skipped_files)}")
        for name in skipped_files:
            print(f"    - {name}")

    # 3. Costruisci DataFrame e matrici di somiglianza
    df_pset = pd.DataFrame.from_dict(all_pset_data, orient="index")

    print("\n[3/5] Calcolo matrici di somiglianza...")
    df_sim_energ = build_similarity_matrix(df_pset, PESI_ENERGETICI).round(4)
    df_sim_strut = build_similarity_matrix(df_pset, PESI_STRUTTURALI).round(4)

    df_pairs_energ = build_pair_ranking(df_sim_energ)
    df_pairs_strut = build_pair_ranking(df_sim_strut)

    df_focus_energ, target_energ = build_focus_sheet(df_sim_energ, args.target)
    df_focus_strut, target_strut = build_focus_sheet(df_sim_strut, args.target)

    print(f"  Focus energetico: '{target_energ}'")
    print(f"  Focus strutturale: '{target_strut}'")

    # 4. Stima interventi e costi per ogni modello
    print("\n[4/5] Censimento interventi e costi...")
    all_costs = {}
    censimento_interventi = set()  # Tutti gli interventi già fatti (tutti i modelli)

    # Prima passata: raccogli TUTTI gli interventi (censimento = già fatti)
    for model_name, pset in all_pset_data.items():
        qty = distribute_quantities(all_quantities.get(model_name, {}), pset, model_name)
        all_quantities[model_name] = qty
        interventions = hypothesize_interventions(pset, qty, target_type=target_type)
        if interventions:
            censimento_interventi.update(interventions.keys())
            costs = estimate_costs(interventions, qty)
            all_costs[model_name] = costs

    print(f"  Censimento: {len(censimento_interventi)} tipi interventi da {len(all_costs)} modelli")

    # Aggiungi cappotto al vicino più simile (Caravaggio) se non già presente
    vicino_candidato = next(
        (n for n in all_costs if "caravaggio" in n.lower()),
        None
    )
    if vicino_candidato:
        gia_liquidi = {c["codice"] for c in all_costs.get(vicino_candidato, [])}
        if "isolamento_pareti_esterne" not in gia_liquidi:
            qty_v = all_quantities.get(vicino_candidato, {})
            stima = stima_costo("isolamento_pareti_esterne",
                                qty_v.get("superficie_involucro", 0))
            if stima:
                all_costs.setdefault(vicino_candidato, []).append(stima)
                censimento_interventi.add("isolamento_pareti_esterne")
                print(f"  + Aggiunto cappotto a {vicino_candidato}")

    # 5. Genera Excel
    print(f"\n[5/5] Generazione Excel: {output_xlsx}")

    # Costruisci dati per foglio campione
    sample_data = build_sample_focus_sheet(
        df_sim_energ, df_sim_strut, args.target,
        all_pset_data, all_quantities, all_costs,
        censimento_interventi=censimento_interventi
    )
    if sample_data:
        print(f"  Campione: '{sample_data['target_name']}'")
        print(f"  Vicino più simile: '{sample_data['vicino_name']}' "
              f"(media {sample_data['sim_media']*100:.1f}%)")
        print(f"  Interventi raccomandati: {len(sample_data.get('interventi_campione', []))}")
        print(f"  Costo stimato campione: € {sample_data['totale_complessivo']:,.2f}")

    write_excel_output(
        df_sim_energ, df_sim_strut,
        df_pairs_energ, df_pairs_strut,
        df_focus_energ, df_focus_strut,
        target_energ, target_strut,
        all_quantities, all_costs,
        output_xlsx,
        interventions_per_model=all_costs,
        sample_data=sample_data,
        target_name=target_energ
    )

    print(f"\n{'='*60}")
    print(f"  COMPLETATO! File: {output_xlsx}")
    print(f"{'='*60}")

    # Riepilogo finale
    print("\nRIEPILOGO COSTI STIMATI:")
    print("-" * 60)
    for model_name, costs in all_costs.items():
        energetici = sum(c["costo_totale"] for c in costs if c["tipo"] == "energetico")
        strutturali = sum(c["costo_totale"] for c in costs if c["tipo"] == "strutturale")
        totale = energetici + strutturali
        print(f"  {model_name:45s} € {totale:>12,.2f}")
        if energetici > 0:
            print(f"    {'':45s} (energia: € {energetici:>10,.2f})")
        if strutturali > 0:
            print(f"    {'':45s} (struttura: € {strutturali:>10,.2f})")
    print("-" * 60)
    print(f"  {'TOTALE GENERALE':45s} € {sum(sum(c['costo_totale'] for c in costs) for costs in all_costs.values()):>12,.2f}")


if __name__ == "__main__":
    main()
