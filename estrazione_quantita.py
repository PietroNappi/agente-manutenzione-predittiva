#!/usr/bin/env python3
"""
Estrazione quantità geometriche da modelli IFC.
Calcola superfici, volumi e conteggi di elementi strutturali e architettonici.
"""

import numpy as np
import pandas as pd

try:
    import ifcopenshell
    import ifcopenshell.util.element as ifc_util
    import ifcopenshell.util.unit as ifc_unit
except ImportError:
    raise ImportError("ifcopenshell non installato. pip install ifcopenshell")


def _get_conversion_factor(model):
    """Fattore di conversione da unità IFC (mm) a metri."""
    try:
        unit = ifc_unit.get_units(model)
        length = unit[0]
        if length.Prefix == "MILLI":
            return 0.001
        return 1.0
    except Exception:
        return 0.001


def _get_surface_area(entity):
    """
    Calcola la superficie dell'entità IFC.
    Usa le proprietà Quantity TakeOff se disponibili, altrimenti stima.
    """
    # Prova da Pset_QuantityTakeOff
    if hasattr(entity, "IsDefinedBy") and entity.IsDefinedBy:
        for rel in entity.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcPropertySet"):
                continue
            for prop in (pdef.HasProperties or []):
                if prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                    name = str(prop.Name).lower()
                    if any(kw in name for kw in ["area", "surface", "superficie"]):
                        try:
                            return float(prop.NominalValue.wrappedValue)
                        except (ValueError, TypeError):
                            pass

    # Prova da IfcElementQuantity
    if hasattr(entity, "IsDefinedBy") and entity.IsDefinedBy:
        for rel in entity.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for q in (pdef.Quantities or []):
                if q.is_a("IfcAreaQuantity"):
                    try:
                        return float(q.AreaValue)
                    except (ValueError, TypeError):
                        pass

    return None


def _get_volume(entity):
    """Calcola il volume dell'entità IFC."""
    if hasattr(entity, "IsDefinedBy") and entity.IsDefinedBy:
        for rel in entity.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for q in (pdef.Quantities or []):
                if q.is_a("IfcVolumeQuantity"):
                    try:
                        return float(q.VolumeValue)
                    except (ValueError, TypeError):
                        pass
    return None


def _get_gross_surface(entity):
    """Calcola la superficie lorda (gross area) dell'entità IFC."""
    if hasattr(entity, "IsDefinedBy") and entity.IsDefinedBy:
        for rel in entity.IsDefinedBy:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue
            for q in (pdef.Quantities or []):
                if q.is_a("IfcAreaQuantity") and "gross" in str(q.Name).lower():
                    try:
                        return float(q.AreaValue)
                    except (ValueError, TypeError):
                        pass
    return None


def _is_external(entity):
    """Verifica se un'entità è esterna (IsExternal = True)."""
    if not hasattr(entity, "IsDefinedBy") or not entity.IsDefinedBy:
        return False
    for rel in entity.IsDefinedBy:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if not pdef.is_a("IfcPropertySet"):
            continue
        for prop in (pdef.HasProperties or []):
            if prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                name = str(prop.Name).lower()
                if "isexternal" in name.replace(" ", ""):
                    try:
                        return bool(prop.NominalValue.wrappedValue)
                    except (ValueError, TypeError):
                        pass
    return False


def _get_predefined_type(entity):
    """Ottiene il PredefinedType dell'entità."""
    if hasattr(entity, "PredefinedType"):
        return str(entity.PredefinedType)
    return None


def _count_entities_by_storey(model, entity_type):
    """Conta le entità per piano."""
    storeys = model.by_type("IfcBuildingStorey")
    counts = {}
    for storey in storeys:
        name = storey.Name or "Sconosciuto"
        elements = ifc_util.get_direct_elements(storey)
        type_count = sum(1 for e in elements if e.is_a(entity_type))
        counts[name] = type_count
    return counts


def _get_projected_area_xy(entity):
    """Calcola area proiettata XY di un'entità IFC dalla geometria triangolare."""
    try:
        import ifcopenshell.geom
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, entity)
        if shape is None:
            return 0
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        if not verts or not faces:
            return 0

        points = []
        for i in range(0, len(verts), 3):
            points.append((verts[i], verts[i+1], verts[i+2]))

        # Raggruppa triangoli per livello Z, prendi il livello più alto (faccia superiore)
        z_groups = {}
        for i in range(0, len(faces), 3):
            i0, i1, i2 = faces[i], faces[i+1], faces[i+2]
            x0, y0, z0 = points[i0]
            x1, y1, z1 = points[i1]
            x2, y2, z2 = points[i2]
            z_avg = (z0 + z1 + z2) / 3
            area = abs((x1-x0)*(y2-y0) - (x2-x0)*(y1-y0)) / 2
            z_key = round(z_avg, 1)
            if z_key not in z_groups:
                z_groups[z_key] = 0
            z_groups[z_key] += area

        if z_groups:
            return max(z_groups.values())
    except Exception:
        pass
    return 0


def extract_quantities(model):
    """
    Estrae quantità geometriche da un modello IFC.
    Conteggi entità + area coperture calcolata geometricamente.
    """
    quantities = {
        "num_storeys": 0,
        "num_walls_ext": 0,
        "num_windows": 0,
        "num_doors": 0,
        "num_columns": 0,
        "num_beams": 0,
        "num_slabs": 0,
        "num_roofs": 0,
        "num_stairs": 0,
        "area_roofs": 0.0,
    }

    quantities["num_storeys"] = len(model.by_type("IfcBuildingStorey"))
    quantities["num_walls_ext"] = len(model.by_type("IfcWall")) + len(model.by_type("IfcWallStandardCase"))
    quantities["num_windows"] = len(model.by_type("IfcWindow"))
    quantities["num_doors"] = len(model.by_type("IfcDoor"))
    quantities["num_columns"] = len(model.by_type("IfcColumn")) + len(model.by_type("IfcPile"))
    quantities["num_beams"] = len(model.by_type("IfcBeam")) + len(model.by_type("IfcMember"))
    quantities["num_slabs"] = len(model.by_type("IfcSlab")) + len(model.by_type("IfcPlate"))
    quantities["num_roofs"] = len(model.by_type("IfcRoof"))
    quantities["num_stairs"] = (
        len(model.by_type("IfcStair"))
        + len(model.by_type("IfcStairFlight"))
        + len(model.by_type("IfcRamp"))
        + len(model.by_type("IfcRampFlight"))
    )

    # Area copertura: raccoglie TUTTI gli IfcSlab che sono coperture
    # Usa un set per evitare doppio conteggio
    roof_slab_ids = set()

    # 1. IfcSlab con "copertura"/"tetto"/"involucro" o PredefinedType=ROOF
    for slab in model.by_type("IfcSlab"):
        name = getattr(slab, "Name", "") or ""
        pt = getattr(slab, "PredefinedType", "") or ""
        is_roof = pt == "ROOF" or "copertura" in name.lower() or "cop" in name.lower() or "tetto" in name.lower() or "involucro" in name.lower()
        if is_roof:
            roof_slab_ids.add(slab.id())

    # 2. IfcSlab in piani "copertura"/"colmo" (anche se il nome non lo dice)
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        storey = rel.RelatingStructure
        if not storey or not storey.is_a("IfcBuildingStorey"):
            continue
        sname = getattr(storey, "Name", "") or ""
        if "copertura" in sname.lower() or "colmo" in sname.lower():
            for elem in (rel.RelatedElements or []):
                if elem.is_a("IfcSlab"):
                    roof_slab_ids.add(elem.id())

    # 3. IfcSlab nel piano più alto (Elevation massima) — solo se non già trovati
    #    e solo se il modello ha muri (non è solo struttura)
    has_walls = len(model.by_type("IfcWall")) + len(model.by_type("IfcWallStandardCase")) > 0
    if len(roof_slab_ids) < 3 and has_walls:
        storeys = model.by_type("IfcBuildingStorey")
        if storeys:
            max_elev = max(getattr(s, "Elevation", 0) or 0 for s in storeys)
            top_storeys = [s for s in storeys if (getattr(s, "Elevation", 0) or 0) >= max_elev - 0.5]
            for rel in model.by_type("IfcRelContainedInSpatialStructure"):
                if rel.RelatingStructure in top_storeys:
                    for elem in (rel.RelatedElements or []):
                        if elem.is_a("IfcSlab") and elem.id() not in roof_slab_ids:
                            roof_slab_ids.add(elem.id())

    # 4. Calcola area di TUTTI gli slabs raccolti
    for slab_id in roof_slab_ids:
        slab = model.by_id(slab_id)
        quantities["area_roofs"] += _get_projected_area_xy(slab)

    # 4. IfcRoof TotalArea — somma solo se il nome non corrisponde a un IfcSlab
    #    (se IfcRoof e IfcSlab hanno lo stesso nome = stesso tetto, evita doppio)
    quantities["area_roofs"] = sum(_get_projected_area_xy(model.by_id(sid)) for sid in roof_slab_ids)

    slab_names = set()
    for sid in roof_slab_ids:
        slab = model.by_id(sid)
        sname = (getattr(slab, "Name", "") or "").split(":")[0].strip().lower()
        slab_names.add(sname)

    for roof in model.by_type("IfcRoof"):
        roof_area = 0
        for rel in getattr(roof, "IsDefinedBy", []):
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcPropertySet"):
                continue
            if pdef.Name != "Pset_RoofCommon":
                continue
            for prop in (pdef.HasProperties or []):
                if prop.is_a("IfcPropertySingleValue") and prop.NominalValue:
                    if prop.Name == "TotalArea":
                        try:
                            roof_area = float(prop.NominalValue.wrappedValue)
                        except (ValueError, TypeError):
                            pass
        if roof_area > 0:
            rname = (getattr(roof, "Name", "") or "").split(":")[0].strip().lower()
            already_covered = any(rname in sn or sn in rname for sn in slab_names if sn)
            if not already_covered:
                quantities["area_roofs"] += roof_area

    # 5. Se ancora 0, fallback IfcRoof geometrico (solo modelli piccoli)
    if quantities["area_roofs"] == 0 and len(model.by_type("IfcSlab")) < 50:
        for roof in model.by_type("IfcRoof"):
            quantities["area_roofs"] += _get_projected_area_xy(roof)

    return quantities


def build_quantities_dataframe(models_data):
    """
    Costruisce un DataFrame con le quantità estratte per ogni modello.
    models_data: dict {nome_file: {quantità}}
    """
    return pd.DataFrame.from_dict(models_data, orient="index")


def print_quantities_summary(df_quantities):
    """Stampa un riepilogo delle quantità estratte."""
    print("\n=== RIEPILOGO QUANTITÀ ESTRAITTE ===\n")
    for col in df_quantities.columns:
        val = df_quantities[col].sum()
        if isinstance(val, float):
            print(f"  {col:35s}: {val:>15.2f}")
        else:
            print(f"  {col:35s}: {val:>15}")


if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    IFC_FOLDER = r"C:\Users\pietr\Desktop\Scuole ifc parametri"

    files = []
    for root, _, filenames in os.walk(IFC_FOLDER):
        for f in filenames:
            if f.lower().endswith(".ifc"):
                files.append(os.path.join(root, f))
    files = sorted(files)

    if not files:
        print("Nessun file IFC trovato.")
        sys.exit(1)

    print(f"Trovati {len(files)} file IFC\n")

    all_data = {}
    for path in files[:3]:  # Test primi 3 file
        name = Path(path).name
        print(f"[FILE] {name}")
        try:
            model = ifcopenshell.open(path)
            qty = extract_quantities(model)
            all_data[name] = qty
            n_ext = qty["num_walls_ext"]
            n_win = qty["num_windows"]
            print(f"  Pareti: {n_ext}")
            print(f"  Finestre: {n_win}, Porte: {qty['num_doors']}")
            print(f"  Colonne: {qty['num_columns']}, Travi: {qty['num_beams']}")
            print(f"  Solai: {qty['num_slabs']}, Scale: {qty['num_stairs']}")
            print(f"  Coperture: {qty['num_roofs']}, Area copertura: {qty['area_roofs']:.0f} m²")
            print()
        except Exception as e:
            print(f"  [ERR] {e}\n")

    if all_data:
        df = build_quantities_dataframe(all_data)
        print_quantities_summary(df)
