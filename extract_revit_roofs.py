"""
Estrattore aree copertura da file Revit (.rte/.rvt) via Revit API.
Confronta con risultati IFC.
"""
import sys, os, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BIM_FOLDER = r'C:\Users\pietr\Desktop\BIM PARAMETRI'
IFC_FOLDER = r'C:\Users\pietr\Desktop\Scuole ifc parametri'

# Mappa nomi IFC -> nomi cartelle BIM
IFC_TO_BIM = {
    "ScuolaCaracciolo": "BIM CARACCIOLO PROCIDA",
    "CARAVAGGIO": "BIM CARAVAGGIO SAN GENNARO",
    "COLOMBO": "BIM COLOMBO MARIGLIANO",
    "DeCillis": "BIM DE CILLIS NAPOLI",
    "DE NICOLA": "BIM DE NICOLA NAPOLI",
    "ELENA": "BIM ELENA DI SAVOIA",
    "FALCONE": "BIM FALCONE LICOLA",
    "FERRARIS": "BIM FERRARIS MARIGLIANO",
    "MERCALLI": "BIM MERCALLI-PAGANO NAPOLI",
    "Pagano": "BIM PAGANO-BERNINI NAPOLI",
    "ROSSI DORIA": "BIM ROSSI DORIA MARIGLIANO",
    "SIANI": "BIM SIANI CASALNUOVO",
    "TILGHER": "BIM TILGHER ECOLANO",
    "TORRENTE": "BIM TORRENTE CASORIA",
    "TORRICELLI": "BIM TORRICELLI SOMMA VESUVIANA",
    "Bixio": "BIM BIXIO SORRENTO",
    "MEL_COORDINAMENTO": "BIM KANT MELITO",
    "2024.06": "BIM SIANI CASALNUOVO",
    "ISCHIA": "BIM ISCHIA",
    "CASANOVA": "BIM CASANOVA",
}

# Trova file .rte/.rvt corrispondenti agli IFC
def find_rte_files():
    """Trova i file Revit che corrispondono agli IFC delle scuole."""
    rte_files = {}
    
    for root, _, files in os.walk(BIM_FOLDER):
        for f in files:
            if f.lower().endswith(('.rte', '.rvt')):
                path = os.path.join(root, f)
                # Identifica la scuola dal percorso
                for ifc_key, bim_folder in IFC_TO_BIM.items():
                    if bim_folder.upper() in root.upper():
                        rte_files[ifc_key] = path
                        break
    
    return rte_files

def extract_roof_areas_revit():
    """Estrae aree copertura usando la struttura XML del file Revit."""
    import zipfile
    import xml.etree.ElementTree as ET
    
    rte_files = find_rte_files()
    results = {}
    
    for school, rte_path in rte_files.items():
        print(f"\n=== {school} ===")
        print(f"  File: {os.path.basename(rte_path)}")
        
        try:
            # I file .rte/.rvt sono OLE2 o ZIP
            # Proviamo come ZIP (formato moderno)
            with zipfile.ZipFile(rte_path, 'r') as z:
                # Cerca il file di progetto
                project_files = [n for n in z.namelist() if 'ProjectInformation' in n or 'BasicFileInfo' in n]
                print(f"  File nel ZIP: {len(z.namelist())}")
                for pf in project_files[:5]:
                    print(f"    {pf}")
                    
        except zipfile.BadZipFile:
            # File OLE2
            try:
                import olefile
                ole = olefile.OleFileIO(rte_path)
                streams = ole.listdir()
                print(f"  Stream OLE2: {len(streams)}")
                for s in streams[:10]:
                    print(f"    {'/'.join(s)}")
                ole.close()
            except ImportError:
                print("  Nessun formato riconosciuto (serve olefile)")
            except Exception as e:
                print(f"  Errore OLE2: {e}")
    
    return rte_files

if __name__ == "__main__":
    print("=== Ricerca file Revit ===")
    rte_files = find_rte_files()
    for school, path in sorted(rte_files.items()):
        print(f"  {school}: {os.path.basename(path)}")
    
    print(f"\n=== Analisi formati ===")
    results = extract_roof_areas_revit()
