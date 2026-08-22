
import os
from pathlib import Path

import ifcopenshell
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURAZIONE
# ============================================================

IFC_FOLDER = r"C:\Users\pietr\Desktop\Scuole ifc parametri"
OUTPUT_FOLDER = os.path.join(IFC_FOLDER, "output")
TARGET_PSET = "Pset_InformazioniProgetto"

OUTPUT_CSV_FEATURES = os.path.join(OUTPUT_FOLDER, "parametri_estratti_dump.csv")
OUTPUT_CSV_MATRIX = os.path.join(OUTPUT_FOLDER, "matrice_somiglianza_modelli.csv")

# Questo sarà il tuo file finale
OUTPUT_XLSX = os.path.join(OUTPUT_FOLDER, "Algoritmo_di_somiglianza_output.xlsx")


# ============================================================
# SCANSIONE FILE IFC
# ============================================================

def scan_all_ifc_files(folder_path):
    files = []
    for root, _, filenames in os.walk(folder_path):
        for f in filenames:
            if f.lower().endswith(".ifc"):
                files.append(os.path.join(root, f))
    return sorted(files)


# ============================================================
# ESTRAZIONE PARAMETRI
# ============================================================

def extract_project_parameters(model):
    parametri_map = {
        "altezza_massima": "Altezza massima fuoriterra valutata in gronda",
        "altezza_minima": "Altezza minima fuoriterra valutata in gronda",
        "anno": "Anno di costruzione",
        "esposizione": "Classe di esposizione",
        "mare": "Distanza dal mare",
        "carbonatazione": "Profondità di carbonatazione stimata",
        "porosita": "Rapporto di porosità teorica",
        "involucro": "Superficie involucro esterna",
        "tipologia": "Tipologia costruttiva",
        "volume": "Volume degli elementi strutturali",
        "climatica": "Zona climatica",
        "sismica": "Zona sismica",
        "beta1": "Configurazione planimetrica rapporto β1 = a/l",
        "beta2": "Configurazione planimetrica rapporto β2 = b/l",
    }

    pset_data = {nome_umano: None for nome_umano in parametri_map.values()}
    pset_found = False

    for entity_type in ["IfcProject", "IfcBuilding"]:
        for entity in model.by_type(entity_type):
            if not hasattr(entity, "IsDefinedBy") or not entity.IsDefinedBy:
                continue

            for rel in entity.IsDefinedBy:
                if not rel.is_a("IfcRelDefinesByProperties"):
                    continue

                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet") and pdef.Name == TARGET_PSET:
                    pset_found = True

                    for prop in pdef.HasProperties or []:
                        if not prop.is_a("IfcPropertySingleValue"):
                            continue

                        ifc_prop_name = str(prop.Name).strip().lower()

                        for chiave_pulita, nome_umano in parametri_map.items():
                            if chiave_pulita in ifc_prop_name:
                                if prop.NominalValue is not None:
                                    try:
                                        pset_data[nome_umano] = prop.NominalValue.wrappedValue
                                    except Exception:
                                        pset_data[nome_umano] = str(prop.NominalValue)
                                break

    if not pset_found:
        return None

    return pset_data


# ============================================================
# CALCOLO SOMIGLIANZA
# ============================================================

def is_number(value):
    return isinstance(value, (int, float, np.integer, np.floating))


def calculate_mixed_similarity(row1, row2):
    matches = 0
    total_features = len(row1)

    for col in row1.index:
        v1 = row1[col]
        v2 = row2[col]

        if pd.isna(v1) and pd.isna(v2):
            matches += 1
        elif pd.isna(v1) or pd.isna(v2):
            continue
        else:
            if is_number(v1) and is_number(v2):
                max_abs = max(abs(v1), abs(v2))
                if max_abs == 0:
                    matches += 1
                else:
                    matches += 1 - (abs(v1 - v2) / max_abs)
            else:
                if str(v1).strip().lower() == str(v2).strip().lower():
                    matches += 1

    return (matches / total_features) * 100


# ============================================================
# COSTRUZIONE DATAFRAME
# ============================================================

def build_similarity_dataframe(df_features):
    model_names = df_features.index.tolist()
    num_models = len(model_names)
    similarity_matrix = np.zeros((num_models, num_models))

    for i in range(num_models):
        for j in range(num_models):
            similarity_matrix[i, j] = calculate_mixed_similarity(
                df_features.iloc[i],
                df_features.iloc[j]
            )

    return pd.DataFrame(similarity_matrix, index=model_names, columns=model_names)


def build_pair_ranking(df_similarity_numeric):
    pairs = []
    model_names = df_similarity_numeric.index.tolist()

    for i in range(len(model_names)):
        for j in range(i + 1, len(model_names)):
            pairs.append({
                "Posizione": 0,
                "Primo Modello IFC": model_names[i],
                "Secondo Modello IFC": model_names[j],
                "Grado di Somiglianza": round(float(df_similarity_numeric.iloc[i, j]) / 100.0, 4)
            })

    df_pairs = pd.DataFrame(pairs)

    if not df_pairs.empty:
        df_pairs = df_pairs.sort_values(
            by="Grado di Somiglianza",
            ascending=False
        ).reset_index(drop=True)
        df_pairs["Posizione"] = np.arange(1, len(df_pairs) + 1)

    return df_pairs


def build_ferraris_sheet(df_similarity_numeric):
    target_name = next(
        (idx for idx in df_similarity_numeric.index if "ferraris" in idx.lower()),
        None
    )

    if target_name is None:
        return pd.DataFrame(columns=[
            "Posizione",
            "Primo Modello IFC",
            "Secondo Modello IFC",
            "Grado di Somiglianza"
        ])

    series_ferraris = (
        df_similarity_numeric.loc[target_name]
        .drop(labels=[target_name], errors="ignore")
        .sort_values(ascending=False)
    )

    rows = []
    for i, (name, value) in enumerate(series_ferraris.items(), start=1):
        rows.append({
            "Posizione": i,
            "Primo Modello IFC": target_name,
            "Secondo Modello IFC": name,
            "Grado di Somiglianza": round(float(value) / 100.0, 4)
        })

    return pd.DataFrame(rows)


# ============================================================
# FORMATTAZIONE EXCEL E FOGLI AGGIUNTIVI
# ============================================================

def build_formats(workbook):
    orange_title = "#F4B183"
    orange_header = "#ED7D31"
    orange_light = "#FCE4D6"
    blue_name = "#D9EAF7"

    return {
        "title": workbook.add_format({
            "bold": True,
            "font_size": 14,
            "align": "center",
            "valign": "vcenter",
            "bg_color": orange_title,
            "border": 1,
        }),
        "header": workbook.add_format({
            "bold": True,
            "text_wrap": True,
            "align": "center",
            "valign": "vcenter",
            "font_color": "#FFFFFF",
            "bg_color": orange_header,
            "border": 1,
        }),
        "row_name": workbook.add_format({
            "bold": True,
            "align": "left",
            "valign": "vcenter",
            "bg_color": blue_name,
            "border": 1,
        }),
        "text": workbook.add_format({
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        }),
        "index": workbook.add_format({
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        }),
        "percent": workbook.add_format({
            "num_format": "0.0%",
            "align": "center",
            "valign": "vcenter",
            "bg_color": orange_light,
            "border": 1,
        }),
        "percent_bold": workbook.add_format({
            "num_format": "0.0%",
            "align": "center",
            "valign": "vcenter",
            "bg_color": orange_light,
            "bold": True,
            "border": 1,
        }),
    }


def write_excel_output(df_similarity_numeric, output_path):
    df_pairs = build_pair_ranking(df_similarity_numeric)
    df_ferraris = build_ferraris_sheet(df_similarity_numeric)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        fmt = build_formats(workbook)

        # --------------------------------------------------------
        # FOGLIO 1: MATRICE SOVRAPPOSIZIONE TOTALE
        # --------------------------------------------------------
        ws1 = workbook.add_worksheet("Matrice Sovrapposizione Totale")
        title1 = "Matrice Completa di Somiglianza Incrociata e Sovrapposizione Tipologica (Set Integrale)"
        ws1.merge_range(0, 0, 0, len(df_similarity_numeric.columns), title1, fmt["title"])

        for col_idx, col_name in enumerate(df_similarity_numeric.columns, start=1):
            ws1.write(2, col_idx, col_name, fmt["header"])

        for row_idx, row_name in enumerate(df_similarity_numeric.index, start=3):
            ws1.write(row_idx, 0, row_name, fmt["row_name"])

        for r in range(len(df_similarity_numeric.index)):
            for c in range(len(df_similarity_numeric.columns)):
                value = float(df_similarity_numeric.iloc[r, c]) / 100.0
                ws1.write_number(r + 3, c + 1, value, fmt["percent"])

        ws1.set_column(0, 0, 43.17)
        ws1.set_column(1, len(df_similarity_numeric.columns), 15.17)
        ws1.freeze_panes(3, 1)

        if not df_similarity_numeric.empty:
            ws1.conditional_format(
                3, 1, len(df_similarity_numeric.index) + 2, len(df_similarity_numeric.columns),
                {"type": "cell", "criteria": ">", "value": 0.75, "format": fmt["percent_bold"]}
            )

        # --------------------------------------------------------
        # FOGLIO 2: CLASSIFICA COPPIE
        # --------------------------------------------------------
        ws2 = workbook.add_worksheet("Classifica Coppie")
        ws2.merge_range("B6:E6", "Graduatoria Generale delle Coppie di Modelli per Somiglianza", fmt["title"])
        ws2.merge_range("B7:E7", f"Analisi incrociata ({len(df_similarity_numeric.index)} modelli complessivi)", fmt["title"])

        headers2 = ["Posizione", "Primo Modello IFC", "Secondo Modello IFC", "Grado di Somiglianza"]
        for col_offset, header in enumerate(headers2, start=1):
            ws2.write(8, col_offset, header, fmt["header"])

        for i, row in enumerate(df_pairs.itertuples(index=False), start=9):
            ws2.write_number(i, 1, int(row[0]), fmt["index"])
            ws2.write(i, 2, row[1], fmt["text"])
            ws2.write(i, 3, row[2], fmt["text"])
            ws2.write_number(i, 4, float(row[3]), fmt["percent"])

        ws2.set_column("B:B", 12)
        ws2.set_column("C:D", 38)
        ws2.set_column("E:E", 18)
        ws2.freeze_panes(9, 1)

        if not df_pairs.empty:
            ws2.conditional_format(
                9, 4, len(df_pairs) + 8, 4,
                {"type": "cell", "criteria": ">", "value": 0.75, "format": fmt["percent_bold"]}
            )

        # --------------------------------------------------------
        # FOGLIO 3: CAMPIONE FERRARIS
        # --------------------------------------------------------
        ws3 = workbook.add_worksheet("Campione Ferraris")
        ws3.merge_range("B2:E2", "Matrice di Confronto Unidirezionale: ISTITUTO FERRARIS - MODELLO BIM", fmt["title"])

        headers3 = ["Posizione", "Primo Modello IFC", "Secondo Modello IFC", "Grado di Somiglianza"]
        for col_offset, header in enumerate(headers3, start=1):
            ws3.write(4, col_offset, header, fmt["header"])

        for i, row in enumerate(df_ferraris.itertuples(index=False), start=5):
            ws3.write_number(i, 1, int(row[0]), fmt["index"])
            ws3.write(i, 2, row[1], fmt["text"])
            ws3.write(i, 3, row[2], fmt["text"])
            ws3.write_number(i, 4, float(row[3]), fmt["percent"])

        ws3.set_column("B:B", 12)
        ws3.set_column("C:D", 38)
        ws3.set_column("E:E", 18)
        ws3.freeze_panes(5, 1)

        if not df_ferraris.empty:
            ws3.conditional_format(
                5, 4, len(df_ferraris) + 4, 4,
                {"type": "cell", "criteria": ">", "value": 0.75, "format": fmt["percent_bold"]}
            )


# ============================================================
# MAIN
# ============================================================

def main():
    print("STO ESEGUENDO LO SCRIPT COMPLETO CON I 3 FOGLI EXCEL")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    files = scan_all_ifc_files(IFC_FOLDER)
    print(f"Trovati {len(files)} file IFC da analizzare.\n")

    if not files:
        print("[STOP] Nessun file IFC trovato nella cartella indicata.")
        return

    all_models_data = {}

    for path in files:
        file_name = Path(path).name
        try:
            model = ifcopenshell.open(path)
            features = extract_project_parameters(model)

            if features:
                all_models_data[file_name] = features
                print(f"[OK] {file_name} -> Estratti {len(features)} parametri reali.")
            else:
                print(f"[WARN] {file_name} -> {TARGET_PSET} non trovato nel file.")
        except Exception as e:
            print(f"[ERR] {file_name} -> Errore in lettura: {e}")

    if not all_models_data:
        print("\n[STOP] Nessun dato estratto. Verifica le esportazioni IFC.")
        return

    # Salva il dump dei parametri
    df_features = pd.DataFrame.from_dict(all_models_data, orient="index")
    df_features.to_csv(OUTPUT_CSV_FEATURES, sep=";")

    # Calcola somiglianza numerica
    df_similarity_numeric = build_similarity_dataframe(df_features).round(1)

    # Output CSV originale
    df_similarity_csv = df_similarity_numeric.astype(str) + "%"
    df_similarity_csv.to_csv(OUTPUT_CSV_MATRIX, sep=";")

    # Genera l'Excel con i tre fogli e la formattazione
    write_excel_output(df_similarity_numeric, OUTPUT_XLSX)

    print("\n[COMPLETATO] File generati con successo.")
    print(f"File finale pronto: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
