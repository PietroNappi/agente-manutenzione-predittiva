#!/usr/bin/env python3
"""
Dizionario interventi di recupero energetico e strutturale per edifici scolastici.
Prezzi dal Prezzario Regione Campania 2026 (CAM26).

Ogni intervento definisce:
  - nome, tipo (energetico/strutturale)
  - entità IFC sorgente per l'estrazione della quantità
  - filtro opzionale sulle proprietà IFC
  - unità di misura
  - prezzario reale (codice, descrizione, prezzo unitario IVA esclusa)
"""

from collections import OrderedDict


# ============================================================
# ELENCO INTERVENTI CON PREZZI REALI CAMPANIA 2026
# ============================================================

INTERVENTI = OrderedDict({

    # ==================== ENERGETICI ====================

    "isolamento_pareti_esterne": {
        "nome": "Isolamento termico pareti esterne (cappotto)",
        "tipo": "energetico",
        "descrizione": "Cappotto termico o isolamento a casseria sulle pareti opache perimetrali",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A06.020.180.A",
            "descrizione_prezzo": "Consolidamento + isolamento termico strutturale pareti (tinteggiatura termica)",
            "prezzo_unitario": 247.43,
            "note": "Voce approximata - cappotto integrato; nel prezzario non esiste cappotto puro, usare voce consolidamento+isolamento",
            "valuta": "EUR"
        }
    },

    "isolamento_tetto": {
        "nome": "Isolamento termico copertura",
        "tipo": "energetico",
        "descrizione": "Isolamento termico del tetto/lastra di copertura",
        "entita_ifc": ["IfcRoof", "IfcSlab"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_E12.030.095.E",
            "descrizione_prezzo": "Manto impermeabile TPO bianco Solar Reflectance Index 100% (sp.1,8mm) - isolamento integrato",
            "prezzo_unitario": 33.86,
            "note": "Manto SRI; per isolamento completo sommare voce isolante aggiuntiva",
            "valuta": "EUR"
        }
    },

    "isolamento_pavimento": {
        "nome": "Isolamento termico pavimento a terra",
        "tipo": "energetico",
        "descrizione": "Isolamento termico del solaio a contatto con il terreno",
        "entita_ifc": ["IfcSlab"],
        "attributo_quantita": "surface_area",
        "filtro": {"PredefinedType": "FLOOR"},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_E07.010.010.A",
            "descrizione_prezzo": "Massetto cementizio sp>=3cm per pavimentazioni (base isolamento)",
            "prezzo_unitario": 17.68,
            "note": "Massetto; aggiungere costo isolante XPS separatamente",
            "valuta": "EUR"
        }
    },

    "sostituzione_infissi": {
        "nome": "Sostituzione infissi (finestre e porte)",
        "tipo": "energetico",
        "descrizione": "Sostituzione serramenti con infissi a taglio termico ad alta efficienza",
        "entita_ifc": ["IfcWindow", "IfcDoor"],
        "attributo_quantita": "count",
        "filtro": {"IsExternal": True},
        "unita_misura": "nr",
        "prezzario": {
            "codice": "CAM26_E18.079.011.B",
            "descrizione_prezzo": "Infisso alluminio/legno zona A-B (1 anta battente, Uw=2,60)",
            "prezzo_unitario": 840.55,
            "valuta": "EUR"
        }
    },

    "sostituzione_infissi_area": {
        "nome": "Sostituzione infissi - superficie",
        "tipo": "energetico",
        "descrizione": "Superficie totale degli infissi esterni sostituiti",
        "entita_ifc": ["IfcWindow", "IfcDoor"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_E18.079.011.A",
            "descrizione_prezzo": "Infisso alluminio/legno telaio fisso (Uw=2,60) - prezzo al m²",
            "prezzo_unitario": 600.55,
            "valuta": "EUR"
        }
    },

    "impianto_fotovoltaico": {
        "nome": "Impianto fotovoltaico",
        "tipo": "energetico",
        "descrizione": "Installazione impianto fotovoltaico su copertura",
        "entita_ifc": ["IfcRoof"],
        "attributo_quantita": "surface_area",
        "filtro": {},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_L20.010.011.A",
            "descrizione_prezzo": "Pannello fotovoltaico monocristallino 230 Wp (garanzia 25 anni) - circa 1 pannello ogni 1.7m²",
            "prezzo_unitario": 486.38,
            "prezzo_per_wp": 2.11,
            "note": "Prezzo per pannello singolo; 1 pannello ~ 1.7 m². Moltiplicare superficie m² per 0.59 (pannelli/m²)",
            "valuta": "EUR"
        }
    },

    "pompa_di_calore": {
        "nome": "Pompa di calore",
        "tipo": "energetico",
        "descrizione": "Sostituzione impianto di riscaldamento con pompa di calore",
        "entita_ifc": ["IfcBuilding"],
        "attributo_quantita": "volume",
        "filtro": {},
        "unita_misura": "m³",
        "prezzario": {
            "codice": "CAM26_C04.015.010.A",
            "descrizione_prezzo": "Elettropompa circolazione con inverter - stima sistemi pompa di calore (prezzo indicativo /m³)",
            "prezzo_unitario": 12.00,
            "note": "PREZZO INDICATIVO - da validare con preventivazione specifica",
            "valuta": "EUR"
        }
    },

    "BMS": {
        "nome": "Building Management System",
        "tipo": "energetico",
        "descrizione": "Installazione sistema di gestione automatizzata dell'edificio",
        "entita_ifc": ["IfcBuilding"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "edificio",
        "prezzario": {
            "codice": "N/A",
            "descrizione_prezzo": "Sistema BMS base per edificio scolastico - PREZZO DA DEFINIRE",
            "prezzo_unitario": 15000.00,
            "note": "Prezzo stimato - non presente nel prezzario regionale. Da acquisire da preventivazione.",
            "valuta": "EUR"
        }
    },

    "illuminazione_LED": {
        "nome": "Illuminazione LED ad alta efficienza",
        "tipo": "energetico",
        "descrizione": "Sostituzione impianto di illuminazione con punti luce LED",
        "entita_ifc": ["IfcBuildingStorey"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "piano",
        "prezzario": {
            "codice": "N/A",
            "descrizione_prezzo": "Sostituzione illuminazione LED per piano scolastico - PREZZO DA DEFINIRE",
            "prezzo_unitario": 5000.00,
            "note": "Prezzo stimato - non presente nel prezzario regionale. Da acquisire da preventivazione.",
            "valuta": "EUR"
        }
    },

    "impianto_termico": {
        "nome": "Sostituzione impianto termico",
        "tipo": "energetico",
        "descrizione": "Sostituzione caldaia e radiatori con sistema ad alta efficienza",
        "entita_ifc": ["IfcBuilding"],
        "attributo_quantita": "volume",
        "filtro": {},
        "unita_misura": "m³",
        "prezzario": {
            "codice": "CAM26_C08.010.010.C",
            "descrizione_prezzo": "Bollitore ACS acciaio zincato 200l con scambiatore - indicatore impianto",
            "prezzo_unitario": 511.66,
            "note": "Prezzo bollitore; impianto completo da moltiplicare per volumetria",
            "valuta": "EUR"
        }
    },

    "rivestimento_acustico": {
        "nome": "Rivestimento fonoassorbente aule",
        "tipo": "energetico",
        "descrizione": "Posa pannelli fonoassorbenti su pareti e soffitti aule",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": False},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_E13.070.060.A",
            "descrizione_prezzo": "Pavimento vinilico fonoassorbente sp.2,8mm (scuole/ospedali) - prezzo orientativo m²",
            "prezzo_unitario": 55.56,
            "note": "Voce per pavimento fonoassorbente; per pareti usare prezzo simile",
            "valuta": "EUR"
        }
    },

    "tinteggiatura_esterna": {
        "nome": "Tinteggiatura esterna con pittura termica",
        "tipo": "energetico",
        "descrizione": "Tinteggiatura delle facciate esterne con pittura isolante",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A06.020.180.A",
            "descrizione_prezzo": "Tinteggiatura pittura termica bi-componente (consolidamento + isolamento leggero)",
            "prezzo_unitario": 247.43,
            "valuta": "EUR"
        }
    },

    "impermeabilizzazione_copertura": {
        "nome": "Impermeabilizzazione copertura",
        "tipo": "energetico",
        "descrizione": "Rifacimento guaina bituminosa e manto di copertura",
        "entita_ifc": ["IfcRoof"],
        "attributo_quantita": "surface_area",
        "filtro": {},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_E12.020.030.A",
            "descrizione_prezzo": "Manto impermeabile doppio strato per supporto fotovoltaico (4+4mm)",
            "prezzo_unitario": 50.42,
            "valuta": "EUR"
        }
    },

    # ==================== STRUTTURALI ====================

    "consolidamento_muratura_pareti": {
        "nome": "Consolidamento muratura pareti",
        "tipo": "strutturale",
        "descrizione": "Intervento di consolidamento delle pareti in muratura (cuci, scuci, irrobustimento)",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A07.010.010.A",
            "descrizione_prezzo": "Consolidamento strutturale pareti murarie (cuci/scuci + barre acciaio)",
            "prezzo_unitario": 513.41,
            "valuta": "EUR"
        }
    },

    "consolidamento_muratura_vol": {
        "nome": "Consolidamento muratura - volume",
        "tipo": "strutturale",
        "descrizione": "Volume di muratura consolidata",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "volume",
        "filtro": {},
        "unita_misura": "m³",
        "prezzario": {
            "codice": "CAM26_A07.010.020.A",
            "descrizione_prezzo": "Ricucitura lesioni muratura tufo - scuci e cuci con blocchi tufo (al mc)",
            "prezzo_unitario": 988.35,
            "valuta": "EUR"
        }
    },

    "iniezioni_muratura": {
        "nome": "Iniezioni di malta in muratura",
        "tipo": "strutturale",
        "descrizione": "Iniezioni a bassa pressione di malta microfusa negli interstizi",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": True},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A07.010.001.A",
            "descrizione_prezzo": "Risanamento strutturale murature - iniezioni malta lungo lesioni",
            "prezzo_unitario": 466.47,
            "note": "Prezzo al ql (quintale lineare); adattare in base a densità lesioni",
            "valuta": "EUR"
        }
    },

    "consolidamento_solai": {
        "nome": "Consolidamento e adeguamento solai",
        "tipo": "strutturale",
        "descrizione": "Rinforzo strutturale dei solai esistenti (cappa c.a. armata)",
        "entita_ifc": ["IfcSlab"],
        "attributo_quantita": "surface_area",
        "filtro": {"PredefinedType": "FLOOR"},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A05.010.030.A",
            "descrizione_prezzo": "Esecuzione soletta c.a. armata nei solai (piano intermedio)",
            "prezzo_unitario": 164.70,
            "valuta": "EUR"
        }
    },

    "consolidamento_solai_vol": {
        "nome": "Consolidamento solai - volta tufo",
        "tipo": "strutturale",
        "descrizione": "Consolidamento volte in tufo con cappa c.a. armata",
        "entita_ifc": ["IfcSlab"],
        "attributo_quantita": "surface_area",
        "filtro": {},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A05.020.110.B",
            "descrizione_prezzo": "Consolidamento volte tufo con cappa c.a. armata + rete e.s.",
            "prezzo_unitario": 232.89,
            "valuta": "EUR"
        }
    },

    "adeguamento_sismico_colonne": {
        "nome": "Adeguamento sismico colonne",
        "tipo": "strutturale",
        "descrizione": "Confinamento e rinforzo delle colonne in calcestruzzo armato",
        "entita_ifc": ["IfcColumn"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "nr",
        "prezzario": {
            "codice": "CAM26_A05.020.120.B",
            "descrizione_prezzo": "Placcaggio fibra di carbonio per rinforzo strutturale (per colonna singola)",
            "prezzo_unitario": 272.28,
            "note": "Prezzo al mq di placcaggio; stimare mq per colonna (circa 3-5 mq/colonna)",
            "valuta": "EUR"
        }
    },

    "adeguamento_sismico_travi": {
        "nome": "Adeguamento sismico travi",
        "tipo": "strutturale",
        "descrizione": "Rinforzo delle travi in calcestruzzo armato con tessuti fibra",
        "entita_ifc": ["IfcBeam"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "nr",
        "prezzario": {
            "codice": "CAM26_A05.020.120.B",
            "descrizione_prezzo": "Placcaggio fibra di carbonio per rinforzo strutturale (per trave)",
            "prezzo_unitario": 272.28,
            "note": "Prezzo al mq; stimare 4-8 mq per trave (perimetro × lunghezza)",
            "valuta": "EUR"
        }
    },

    "adeguamento_sismico_travi_vol": {
        "nome": "Adeguamento sismico travi - volume",
        "tipo": "strutturale",
        "descrizione": "Volume di travi rinforzate",
        "entita_ifc": ["IfcBeam"],
        "attributo_quantita": "volume",
        "filtro": {},
        "unita_misura": "m³",
        "prezzario": {
            "codice": "CAM26_A05.020.120.B",
            "descrizione_prezzo": "Rinforzo travi per volume",
            "prezzo_unitario": 272.28,
            "note": "Stima: prezzo al mq × superficie trave / volume",
            "valuta": "EUR"
        }
    },

    "rinforzo_fondazioni": {
        "nome": "Rinforzo fondazioni",
        "tipo": "strutturale",
        "descrizione": "Intervento di rinforzo delle fondazioni esistenti",
        "entita_ifc": ["IfcFooting"],
        "attributo_quantita": "volume",
        "filtro": {},
        "unita_misura": "m³",
        "prezzario": {
            "codice": "CAM26_E02.030.010.C",
            "descrizione_prezzo": "Palo trivellato dia.600mm in c.a. (rinforzo fondazioni)",
            "prezzo_unitario": 103.33,
            "valuta": "EUR"
        }
    },

    "scuci_e_rifai": {
        "nome": "Scuci e rifai muratura",
        "tipo": "strutturale",
        "descrizione": "Demolizione e ricostruzione di porzioni di muratura danneggiata",
        "entita_ifc": ["IfcWall", "IfcWallStandardCase"],
        "attributo_quantita": "surface_area",
        "filtro": {"IsExternal": False},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A07.010.020.A",
            "descrizione_prezzo": "Ricucitura lesioni muratura tufo - scuci e cuci con blocchi tufo (al mc)",
            "prezzo_unitario": 988.35,
            "valuta": "EUR"
        }
    },

    "tiranti_strutturali": {
        "nome": "Tiranti strutturali",
        "tipo": "strutturale",
        "descrizione": "Posa tiranti in acciaio per contrastare spinte laterali",
        "entita_ifc": ["IfcBeam"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "nr",
        "prezzario": {
            "codice": "CAM26_A07.010.210.A",
            "descrizione_prezzo": "Capochiave per catene in tondo acciaio mm30",
            "prezzo_unitario": 291.51,
            "note": "Prezzo capochiave; aggiungere costo barra acciaio e posa in opera",
            "valuta": "EUR"
        }
    },

    "rifacimento_copertura_str": {
        "nome": "Rifacimento struttura di copertura",
        "tipo": "strutturale",
        "descrizione": "Sostituzione o rinforzo della struttura portante di copertura",
        "entita_ifc": ["IfcRoof", "IfcBeam"],
        "attributo_quantita": "surface_area",
        "filtro": {},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A08.010.200.A",
            "descrizione_prezzo": "Copertura tetto spiovente con travi lamellare + tegole argilla",
            "prezzo_unitario": 608.54,
            "valuta": "EUR"
        }
    },

    "rifacimento_solai_completo": {
        "nome": "Demolizione e ricostruzione solai",
        "tipo": "strutturale",
        "descrizione": "Demolizione solai esistenti e ricostruzione con strutture nuove",
        "entita_ifc": ["IfcSlab"],
        "attributo_quantita": "surface_area",
        "filtro": {"PredefinedType": "FLOOR"},
        "unita_misura": "m²",
        "prezzario": {
            "codice": "CAM26_A05.010.030.B",
            "descrizione_prezzo": "Esecuzione soletta c.a. armata nei solai (sottotetto)",
            "prezzo_unitario": 201.62,
            "valuta": "EUR"
        }
    },

    "scale_interne": {
        "nome": "Ricostruzione scale interne",
        "tipo": "strutturale",
        "descrizione": "Demolizione e ricostruzione scale in calcestruzzo armato",
        "entita_ifc": ["IfcStair", "IfcStairFlight"],
        "attributo_quantita": "count",
        "filtro": {},
        "unita_misura": "nr",
        "prezzario": {
            "codice": "CAM26_A05.010.030.A",
            "descrizione_prezzo": "Esecuzione soletta c.a. armata (prezzo per scala - stima 4mq/media scala)",
            "prezzo_unitario": 164.70,
            "note": "Stima: 4 mq × prezzo unitario = 658.80 €/scala. Da validare con dimensionamento.",
            "valuta": "EUR"
        }
    },
})


# ============================================================
# FUNZIONI DI UTILITÀ
# ============================================================

def get_interventi_per_tipo(tipo):
    """Ritorna tutti gli interventi di un tipo ('energetico' o 'strutturale')."""
    return {k: v for k, v in INTERVENTI.items() if v["tipo"] == tipo}


def get_entita_ifc_uniche():
    """Ritorna l'insieme di tutte le entità IFC referenziate dagli interventi."""
    entita = set()
    for interv in INTERVENTI.values():
        entita.update(interv["entita_ifc"])
    return sorted(entita)


def get_interventi_per_entita(nome_entita):
    """Ritorna tutti gli interventi che usano un dato tipo di entità IFC."""
    return {k: v for k, v in INTERVENTI.items() if nome_entita in v["entita_ifc"]}


def get_prezzario_completo():
    """Ritorna una lista di dict con tutte le voci di prezzario."""
    voci = []
    for chiave, interv in INTERVENTI.items():
        pz = interv["prezzario"]
        voci.append({
            "codice_intervento": chiave,
            "nome_intervento": interv["nome"],
            "tipo": interv["tipo"],
            "codice_prezzario": pz["codice"],
            "descrizione": pz["descrizione_prezzo"],
            "unita_misura": interv["unita_misura"],
            "prezzo_unitario": pz["prezzo_unitario"],
            "valuta": pz["valuta"]
        })
    return voci


def parse_prezzario_csv(csv_bytes):
    """
    Parsa un CSV di prezzario e ritorna un dict {codice: prezzo_unitario}.
    Supporta separatore | o ; o ,
    Cerca le colonne: Codice, Prezzo (o Prezzo senza S.G.)
    """
    import csv
    import io

    text = csv_bytes.decode("utf-8", errors="replace")
    # Prova a rilevare il separatore
    first_line = text.split("\n")[0]
    if "|" in first_line:
        sep = "|"
    elif ";" in first_line:
        sep = ";"
    else:
        sep = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=sep)

    prezzi = {}
    for row in reader:
        codice = None
        prezzo = None
        for k, v in row.items():
            if k and "codice" in k.lower():
                codice = v.strip().strip('"') if v else None
            if k and ("prezzo senza" in k.lower() or k.lower().strip() == "prezzo"):
                try:
                    prezzo = float(v.strip().strip('"').replace(",", "."))
                except (ValueError, TypeError):
                    pass
        if codice and prezzo and prezzo > 0:
            prezzi[codice] = prezzo

    return prezzi


def stima_costo(codice_intervento, quantita, prezzario_custom=None):
    """
    Stima il costo di un intervento dato il codice e la quantità.
    Ritorna dict con dettagli del calcolo o None se intervento non trovato.
    """
    if codice_intervento not in INTERVENTI:
        return None
    interv = INTERVENTI[codice_intervento]
    pz = interv["prezzario"]

    # Se c'e un prezzario custom, prova a sovrascrivere il prezzo
    prezzo = pz["prezzo_unitario"]
    if prezzario_custom and pz["codice"] in prezzario_custom:
        prezzo = prezzario_custom[pz["codice"]]

    costo = quantita * prezzo
    return {
        "codice": codice_intervento,
        "nome": interv["nome"],
        "tipo": interv["tipo"],
        "quantita": quantita,
        "unita_misura": interv["unita_misura"],
        "prezzo_unitario": prezzo,
        "costo_totale": round(costo, 2),
        "codice_prezzario": pz["codice"],
        "valuta": pz["valuta"]
    }


if __name__ == "__main__":
    print("=== INTERVENTI DISPONIBILI (Prezzario Campania 2026) ===\n")
    for tipo in ["energetico", "strutturale"]:
        print(f"\n--- {tipo.upper()} ---")
        for chiave, interv in get_interventi_per_tipo(tipo).items():
            pz = interv["prezzario"]
            print(f"  {chiave:45s} | {interv['unita_misura']:3s} | € {pz['prezzo_unitario']:>10.2f} | {pz['codice']}")

    print(f"\n\nTotale: {len(INTERVENTI)} interventi")
    print(f"Entità IFC coinvolte: {get_entita_ifc_uniche()}")
    print(f"\nCosto totale indicativo (se tutti gli interventi applicati 1x):")
    tot = sum(v["prezzario"]["prezzo_unitario"] for v in INTERVENTI.values())
    print(f"  € {tot:,.2f}")
