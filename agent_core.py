"""
agent_core.py - Modulo Python importabile per la stima economica basata su somiglianza IFC.
Usage:
    from agent_core import run_analysis
    results = run_analysis(r"C:\\Scuole", target="de nicola", gia_fatti=["isolamento_tetto"])
"""

import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import ifcopenshell
except ImportError:
    raise ImportError("ifcopenshell non installato. Esegui: pip install ifcopenshell")

from interventi_dict import INTERVENTI, stima_costo
from estrazione_quantita import extract_quantities

# ============================================================
# CONFIGURAZIONE
# ============================================================

MAX_FILE_SECONDS = 300
MAX_FILE_MB = 1000
DEFAULT_PSET = "Pset_InformazioniProgetto"

MANUALE_ROOF_AREAS = {
    "MARIGLIANO STRUTTURALE": 0,
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

PROP_MAP = [
    ("altezza_max",    "Altezza massima fuoriterra valutata in gronda"),
    ("altezza_min",    "Altezza minima fuoriterra valutata in gronda"),
    ("anno",           "Anno di costruzione"),
    ("esposizione",    "Classe di esposizione"),
    ("mare",           "Distanza dal mare"),
    ("carbonatazione", "Profondita di carbonatazione stimata"),
    ("porosita",       "Rapporto di porosita teorica"),
    ("involucro",      "Superficie involucro esterna"),
    ("tipologia",      "Tipologia costruttiva"),
    ("volume",         "Volume degli elementi strutturali"),
    ("climatica",      "Zona climatica"),
    ("sismica",        "Zona sismica"),
    ("beta1",          "Configurazione planimetrica rapporto \u03b21 = a/l"),
    ("beta2",          "Configurazione planimetrica rapporto \u03b22 = b/l"),
]

PESI_ENERGETICI = {
    "Zona climatica": 5, "Anno di costruzione": 5, "Distanza dal mare": 4,
    "Superficie involucro esterna": 4, "Rapporto di porosita teorica": 2,
    "Profondita di carbonatazione stimata": 1, "Tipologia costruttiva": 2,
    "Volume degli elementi strutturali": 2,
    "Altezza massima fuoriterra valutata in gronda": 2,
    "Altezza minima fuoriterra valutata in gronda": 2,
    "Configurazione planimetrica rapporto \u03b21 = a/l": 1,
    "Configurazione planimetrica rapporto \u03b22 = b/l": 1,
    "Classe di esposizione": 1, "Zona sismica": 1,
}

PESI_STRUTTURALI = {
    "Zona climatica": 1, "Distanza dal mare": 1, "Anno di costruzione": 5,
    "Superficie involucro esterna": 2, "Rapporto di porosita teorica": 5,
    "Profondita di carbonatazione stimata": 5,
    "Altezza massima fuoriterra valutata in gronda": 1,
    "Altezza minima fuoriterra valutata in gronda": 1,
    "Tipologia costruttiva": 5, "Volume degli elementi strutturali": 5,
    "Configurazione planimetrica rapporto \u03b21 = a/l": 3,
    "Configurazione planimetrica rapporto \u03b22 = b/l": 3,
    "Classe di esposizione": 4, "Zona sismica": 2,
}

AREA_MEDIA_FINESTRA = 2.5
AREA_MEDIA_PORTA = 2.0


# ============================================================
# FUNZIONI BASE
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


def extract_project_parameters(model, pset_name):
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


# ============================================================
# QUANTITA E INTERVENTI
# ============================================================

def distribute_quantities(qty, pset, model_name=""):
    qty = qty.copy()
    involucro = pset.get("Superficie involucro esterna")
    if involucro is not None and not pd.isna(involucro):
        qty["superficie_involucro"] = float(involucro)

    vol = pset.get("Volume degli elementi strutturali")
    if vol is not None and not pd.isna(vol):
        qty["volume_strutturale"] = float(vol)

    manual_override = False
    for key, area in MANUALE_ROOF_AREAS.items():
        if key.upper() in model_name.upper():
            qty["area_roofs"] = area
            manual_override = True
            break

    if not manual_override and qty.get("area_roofs", 0) == 0 and involucro:
        has_roof_elements = qty.get("num_roofs", 0) > 0 or qty.get("num_beams", 0) > 0
        is_structural_only = qty.get("num_walls_ext", 0) == 0 and qty.get("num_windows", 0) == 0
        if has_roof_elements and not is_structural_only:
            qty["area_roofs"] = float(involucro) * 0.30

    qty["area_windows"] = qty.get("num_windows", 0) * AREA_MEDIA_FINESTRA
    qty["area_doors"] = qty.get("num_doors", 0) * AREA_MEDIA_PORTA
    return qty


def hypothesize_interventions(params_pset, quantities, target_type="both", interventi_da_escludere=None):
    if interventi_da_escludere is None:
        interventi_da_escludere = set()
    else:
        interventi_da_escludere = set(interventi_da_escludere)
    interventions = {}

    anno = params_pset.get("Anno di costruzione")
    sismica = params_pset.get("Zona sismica")

    involucro = quantities.get("superficie_involucro", 0)
    has_walls = involucro > 100
    has_roofs = quantities.get("area_roofs", 0) > 50
    has_windows = quantities.get("num_windows", 0) > 5
    has_cols = quantities.get("num_columns", 0) > 3
    has_beams = quantities.get("num_beams", 0) > 3

    vecchio = anno and isinstance(anno, (int, float)) and anno < 2000
    molto_vecchio = anno and isinstance(anno, (int, float)) and anno < 1970
    zona_sismica = sismica and isinstance(sismica, (int, float)) and sismica >= 2

    if target_type in ["energetico", "both"]:
        if vecchio and has_walls and "isolamento_pareti_esterne" not in interventi_da_escludere:
            interventions["isolamento_pareti_esterne"] = involucro
        if vecchio and has_roofs and "isolamento_tetto" not in interventi_da_escludere:
            interventions["isolamento_tetto"] = quantities["area_roofs"]
        if has_windows and "sostituzione_infissi" not in interventi_da_escludere:
            interventions["sostituzione_infissi"] = quantities["num_windows"]

    if target_type in ["strutturale", "both"]:
        if zona_sismica and has_cols and "adeguamento_sismico_colonne" not in interventi_da_escludere:
            interventions["adeguamento_sismico_colonne"] = quantities["num_columns"]
        if molto_vecchio and has_beams and "adeguamento_sismico_travi" not in interventi_da_escludere:
            interventions["adeguamento_sismico_travi"] = quantities["num_beams"]

    return interventions


def estimate_costs(interventions, quantities):
    results = []
    for codice, quantita in interventions.items():
        stima = stima_costo(codice, quantita)
        if stima:
            results.append(stima)
    return results


# ============================================================
# ANALISI CAMPIONE
# ============================================================

def _get_interventi_esclusi(model_name, gia_fatti_map=None):
    if gia_fatti_map is None:
        gia_fatti_map = {}
    for key, interventi in gia_fatti_map.items():
        if key.upper() in model_name.upper():
            return interventi
    return []


def build_sample_analysis(df_sim_energ, df_sim_strut, target_substring,
                          all_pset_data, all_quantities, all_costs,
                          gia_fatti_map=None):
    if gia_fatti_map is None:
        gia_fatti_map = {}

    target_name = next(
        (idx for idx in df_sim_energ.index if target_substring.lower() in idx.lower()),
        None
    )
    if target_name is None:
        return None

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

    interv_vicino = all_costs.get(vicino_name, [])
    gia_fatti = set(_get_interventi_esclusi(target_name, gia_fatti_map))
    interv_da_proporre = [i for i in interv_vicino if i["codice"] not in gia_fatti]

    pset_campione = all_pset_data.get(target_name, {})
    qty_campione = distribute_quantities(all_quantities.get(target_name, {}), pset_campione, target_name)

    interv_campione = []
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

    for interv in interv_da_proporre:
        codice = interv["codice"]
        if codice in INTERVENTI:
            interv_def = INTERVENTI[codice]
            entita = interv_def["entita_ifc"]
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
        "sim_energ": float(sim_energ[vicino_name]),
        "sim_strut": float(sim_strut[vicino_name]),
        "sim_media": float(sim_media[vicino_name]),
        "qty_campione": qty_campione,
        "interventi_vicino": interv_vicino,
        "interventi_campione": interv_campione,
        "gia_fatti": sorted(gia_fatti),
        "totale_energetico": sum(c["costo_totale"] for c in interv_campione if c["tipo"] == "energetico"),
        "totale_strutturale": sum(c["costo_totale"] for c in interv_campione if c["tipo"] == "strutturale"),
        "totale_complessivo": sum(c["costo_totale"] for c in interv_campione),
    }


# ============================================================
# FUNZIONE PRINCIPALE
# ============================================================

def list_models(ifc_folder):
    """Restituisce la lista dei modelli IFC disponibili."""
    models = []
    for root, _dirs, files in os.walk(ifc_folder):
        for f in files:
            if f.lower().endswith(".ifc"):
                path = os.path.join(root, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                if size_mb <= MAX_FILE_MB:
                    models.append({"name": f, "path": path, "size_mb": round(size_mb, 1)})
    models.sort(key=lambda x: x["size_mb"])
    return models


def run_analysis(ifc_folder, target, gia_fatti=None, target_type="both",
                 timeout=300, progress_callback=None):
    """
    Esegue l'analisi completa di stima economica.

    Args:
        ifc_folder: cartella con i file IFC
        target: nome modello campione (substring match)
        gia_fatti: lista di codici interventi già realizzati sul campione
        target_type: "energetico", "strutturale", o "both"
        timeout: timeout per file IFC in secondi
        progress_callback: funzione opzionale per reportare progresso

    Returns:
        dict con tutti i risultati dell'analisi
    """
    if gia_fatti is None:
        gia_fatti = []
    gia_fatti_map = {target.upper(): gia_fatti} if gia_fatti else {}

    def _log(msg):
        if progress_callback:
            progress_callback(msg)

    # 1. Trova file IFC
    _log("Ricerca file IFC...")
    ifc_files = []
    for root, _dirs, files in os.walk(ifc_folder):
        for f in files:
            if f.lower().endswith(".ifc"):
                path = os.path.join(root, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                if size_mb <= MAX_FILE_MB:
                    ifc_files.append((size_mb, f, path))
    ifc_files.sort(key=lambda x: x[0])

    if not ifc_files:
        return {"error": "Nessun file IFC trovato nella cartella."}

    _log(f"Trovati {len(ifc_files)} file IFC")

    # 2. Estrai parametri + quantita
    all_pset_data = {}
    all_quantities = {}
    skipped = []
    global MAX_FILE_SECONDS
    MAX_FILE_SECONDS = timeout

    for i, (size_mb, name, path) in enumerate(ifc_files, 1):
        _log(f"[{i}/{len(ifc_files)}] {name[:50]} ({size_mb:.0f}MB)...")
        t0 = time.time()
        try:
            model = ifcopenshell.open(path)
        except Exception as e:
            _log(f"  ERRORE apertura: {e}")
            skipped.append(name)
            continue

        t_open = time.time() - t0
        if timeout > 0 and t_open > timeout:
            _log(f"  SALTATO (apertura {t_open:.0f}s > {timeout}s)")
            skipped.append(name)
            continue

        pset = extract_project_parameters(model, DEFAULT_PSET)
        qty = extract_quantities(model)

        model_name = Path(path).name
        if pset:
            all_pset_data[model_name] = pset
        all_quantities[model_name] = qty

    if not all_pset_data:
        return {"error": "Nessun dato Pset estratto dai file IFC."}

    _log(f"Parametri estratti da {len(all_pset_data)} modelli")

    # 3. Matrici di somiglianza
    _log("Calcolo matrici di somiglianza...")
    df_pset = pd.DataFrame.from_dict(all_pset_data, orient="index")
    df_sim_energ = build_similarity_matrix(df_pset, PESI_ENERGETICI).round(4)
    df_sim_strut = build_similarity_matrix(df_pset, PESI_STRUTTURALI).round(4)

    # 4. Censimento interventi e costi
    _log("Stima interventi e costi...")
    all_costs = {}
    censimento_interventi = set()

    for model_name, pset in all_pset_data.items():
        qty = distribute_quantities(all_quantities.get(model_name, {}), pset, model_name)
        all_quantities[model_name] = qty
        interventions = hypothesize_interventions(pset, qty, target_type=target_type)
        if interventions:
            censimento_interventi.update(interventions.keys())
            costs = estimate_costs(interventions, qty)
            all_costs[model_name] = costs

    # Aggiungi cappotto a Caravaggio se presente
    vicino_candidato = next((n for n in all_costs if "caravaggio" in n.lower()), None)
    if vicino_candidato:
        gia_liquidi = {c["codice"] for c in all_costs.get(vicino_candidato, [])}
        if "isolamento_pareti_esterne" not in gia_liquidi:
            qty_v = all_quantities.get(vicino_candidato, {})
            stima = stima_costo("isolamento_pareti_esterne", qty_v.get("superficie_involucro", 0))
            if stima:
                all_costs.setdefault(vicino_candidato, []).append(stima)
                censimento_interventi.add("isolamento_pareti_esterne")

    # 5. Analisi campione
    _log("Analisi modello campione...")
    sample = build_sample_analysis(
        df_sim_energ, df_sim_strut, target,
        all_pset_data, all_quantities, all_costs,
        gia_fatti_map=gia_fatti_map
    )

    # 6. Riepilogo per modello
    riepilogo = {}
    for model_name, costs in all_costs.items():
        tot_energ = sum(c["costo_totale"] for c in costs if c["tipo"] == "energetico")
        tot_strut = sum(c["costo_totale"] for c in costs if c["tipo"] == "strutturale")
        riepilogo[model_name] = {
            "totale": tot_energ + tot_strut,
            "energetico": tot_energ,
            "strutturale": tot_strut,
            "n_interventi": len(costs),
        }

    return {
        "n_modelli": len(all_pset_data),
        "all_pset_data": all_pset_data,
        "modelli_skipped": skipped,
        "censimento_tipi": sorted(censimento_interventi),
        "riepilogo": riepilogo,
        "sample": sample,
        "df_sim_energ": df_sim_energ,
        "df_sim_strut": df_sim_strut,
    }


if __name__ == "__main__":
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\pietr\Desktop\Scuole ifc parametri"
    tgt = sys.argv[2] if len(sys.argv) > 2 else "de nicola"

    def log(msg):
        print(msg)

    result = run_analysis(folder, tgt, progress_callback=log)

    if "error" in result:
        print(f"ERRORE: {result['error']}")
    else:
        print(f"\nModelli processati: {result['n_modelli']}")
        print(f"Tipi intervento censiti: {len(result['censimento_tipi'])}")
        if result["sample"]:
            s = result["sample"]
            print(f"\nCampione: {s['target_name']}")
            print(f"Vicino: {s['vicino_name']} (sim={s['sim_media']*100:.1f}%)")
            print(f"Interventi proposti: {len(s['interventi_campione'])}")
            print(f"Costo stimato: EUR {s['totale_complessivo']:,.2f}")
            if s["gia_fatti"]:
                print(f"Gia fatti (esclusi): {', '.join(s['gia_fatti'])}")
