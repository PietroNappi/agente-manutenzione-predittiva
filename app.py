"""
app.py - Chatbot Streamlit per stima economica basata su somiglianza IFC.
Avvio: py -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
"""

import sys
import os
import io
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from agent_core import run_analysis, list_models

# ============================================================
# TRADUZIONI
# ============================================================

T = {
    "it": {
        "page_title": "Agente Manutenzione Predittiva",
        "header_main": "Agente AI Algoritmico",
        "header_sub": "Stima economica degli interventi per la manutenzione predittiva",
        "header_caption": "Analisi basata su somiglianza modelli IFC",
        "powered_by": "Powered by Pietro Nappi",
        "sidebar_config": "Configurazione",
        "source_title": "Sorgente modelli IFC",
        "source_local": "Cartella locale",
        "source_upload": "Carica singoli file",
        "folder_placeholder": "Incolla percorso cartella...",
        "models_found": "{} modelli trovati",
        "show_models": "Mostra modelli",
        "folder_not_found": "Cartella non trovata",
        "upload_label": "Carica file IFC (puoi selezionarli tutti insieme)",
        "files_uploaded": "{} file caricati",
        "target_title": "Modello campione",
        "target_placeholder": "Nome modello da stimare...",
        "target_select": "(inserisci nella chat)",
        "done_title": "Interventi gia realizzati",
        "done_placeholder": "Codici interventi, uno per riga...",
        "timeout_label": "Timeout per file (sec)",
        "welcome": "Seleziona un modello dalla sidebar o scrivi il nome nella chat. Poi lancio l'analisi.",
        "chat_placeholder": "Scrivi qui...",
        "no_target": "Non ho capito quale modello analizzare. Selezionalo dalla sidebar o scrivi il nome nella chat.",
        "analyzing": "Analisi di {} in corso...",
        "analysis_done": "Analisi completata",
        "field_model": "Modello",
        "field_neighbor": "Vicino",
        "field_similarity": "Somiglianza",
        "field_energy": "Energetica",
        "field_structural": "Strutturale",
        "field_done": "Gia realizzati",
        "field_excluded": "esclusi dalla proposta",
        "table_intervention": "Intervento",
        "table_type": "Tipo",
        "table_quantity": "Quantita",
        "table_cost": "Costo",
        "total_label": "Totale",
        "not_found": "Modello '{}' non trovato tra i {} modelli.",
        "download_excel": "Scarica report Excel",
        "footer": "Stima Economica | v1.0",
    },
    "en": {
        "page_title": "Predictive Maintenance Agent",
        "header_main": "AI Algorithmic Agent",
        "header_sub": "Intervention cost estimation for predictive maintenance",
        "header_caption": "Analysis based on IFC model similarity",
        "powered_by": "Powered by Pietro Nappi",
        "sidebar_config": "Configuration",
        "source_title": "IFC model source",
        "source_local": "Local folder",
        "source_upload": "Upload individual files",
        "folder_placeholder": "Paste folder path...",
        "models_found": "{} models found",
        "show_models": "Show models",
        "folder_not_found": "Folder not found",
        "upload_label": "Upload IFC files (select all at once)",
        "files_uploaded": "{} files uploaded",
        "target_title": "Sample building",
        "target_placeholder": "Model name to estimate...",
        "target_select": "(type in chat)",
        "done_title": "Already completed interventions",
        "done_placeholder": "Intervention codes, one per line...",
        "timeout_label": "File timeout (sec)",
        "welcome": "Select a model from the sidebar or type its name in the chat. Then I will run the analysis.",
        "chat_placeholder": "Type here...",
        "no_target": "I did not understand which model to analyze. Select from the sidebar or type the name in chat.",
        "analyzing": "Analyzing {}...",
        "analysis_done": "Analysis complete",
        "field_model": "Model",
        "field_neighbor": "Most similar",
        "field_similarity": "Similarity",
        "field_energy": "Energy",
        "field_structural": "Structural",
        "field_done": "Already done",
        "field_excluded": "excluded from proposal",
        "table_intervention": "Intervention",
        "table_type": "Type",
        "table_quantity": "Quantity",
        "table_cost": "Cost",
        "total_label": "Total",
        "not_found": "Model '{}' not found among {} models.",
        "download_excel": "Download Excel report",
        "footer": "Cost Estimation | v1.0",
    }
}

def t(key):
    lang = st.session_state.get("lang", "it")
    return T.get(lang, T["it"]).get(key, key)

# ============================================================
# THEME + FONT
# ============================================================

st.set_page_config(page_title="Agente Manutenzione Predittiva", page_icon="x1f3d7", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800;900&display=swap');

/* Font su tutto il contenuto */
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stChatMessageContent"],
[data-testid="stChatInput"] textarea,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] code,
.stTextInput input,
.stTextArea textarea,
.stSelectbox [data-baseweb="select"],
.stRadio label,
.stSlider label,
.stButton button,
.stDownloadButton button,
.stExpander summary,
.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* Titoli piu piccoli */
[data-testid="stMarkdownContainer"] h1 { font-weight: 800 !important; font-size: 1.25rem !important; }
[data-testid="stMarkdownContainer"] h2 { font-weight: 700 !important; font-size: 1rem !important; }
[data-testid="stMarkdownContainer"] h3 { font-weight: 600 !important; font-size: 0.88rem !important; }

/* Input */
.stTextInput input, .stTextArea textarea { font-size: 0.78rem !important; }

/* Sidebar stretta e compatta */
section[data-testid="stSidebar"] { width: 22rem !important; font-size: 0.65rem !important; }
section[data-testid="stSidebar"] > div { width: 22rem !important; max-width: 22rem !important; }
section[data-testid="stSidebar"] * { font-size: 0.65rem !important; }
section[data-testid="stSidebar"] hr { margin: 0.3rem 0 !important; }

/* Chat e bottoni */
[data-testid="stChatMessage"] { border-radius: 6px; padding: 0.8rem; margin-bottom: 0.4rem; }
[data-testid="stChatInput"] { font-size: 0.65rem !important; }
[data-testid="stChatInput"] textarea { font-size: 0.65rem !important; }
.stButton button { font-weight: 700; border-radius: 4px; }
.stDownloadButton button { font-weight: 700; border-radius: 4px; }
.stExpander summary { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# INIT SESSION
# ============================================================

if "lang" not in st.session_state:
    st.session_state.lang = "it"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("IT", use_container_width=True,
                      type="primary" if st.session_state.lang == "it" else "secondary",
                      key="btn_it"):
            if st.session_state.lang != "it":
                st.session_state.lang = "it"
                st.rerun()
    with col2:
        if st.button("EN", use_container_width=True,
                      type="primary" if st.session_state.lang == "en" else "secondary",
                      key="btn_en"):
            if st.session_state.lang != "en":
                st.session_state.lang = "en"
                st.rerun()

    st.markdown("---")
    st.markdown("### " + t("sidebar_config"))

    st.markdown("**" + t("source_title") + "**")
    src_local = t("source_local")
    src_upload = t("source_upload")
    src_options = [src_local, src_upload]

    if "src_idx" not in st.session_state:
        st.session_state.src_idx = 0
    sel_idx = st.radio("src", src_options, index=st.session_state.src_idx,
                       label_visibility="collapsed", horizontal=True)
    st.session_state.src_idx = src_options.index(sel_idx)
    sorgente = sel_idx

    ifc_folder = ""
    model_names = []

    if sorgente == src_local:
        ifc_folder = st.text_input("path", value=r"C:\Users\pietr\Desktop\Scuole ifc parametri",
                                    label_visibility="collapsed", placeholder=t("folder_placeholder"))
        if os.path.isdir(ifc_folder):
            models = list_models(ifc_folder)
            model_names = [m["name"] for m in models]
            st.success(t("models_found").format(len(models)))
            with st.expander(t("show_models")):
                for m in models:
                    st.caption(f"{m['name'][:50]} ({m['size_mb']}MB)")
        elif ifc_folder:
            st.error(t("folder_not_found"))
    else:
        st.caption("Apri la cartella, premi Ctrl+A per selezionare tutti gli IFC, e caricali tutti insieme")
        uploaded = st.file_uploader(t("upload_label"), type=["ifc"], accept_multiple_files=True)
        if uploaded:
            tmp = tempfile.mkdtemp(prefix="stima_")
            for f in uploaded:
                with open(os.path.join(tmp, f.name), "wb") as out:
                    out.write(f.read())
            ifc_folder = tmp
            models = list_models(ifc_folder)
            model_names = [m["name"] for m in models]
            st.success(t("files_uploaded").format(len(models)))

    st.markdown("---")
    st.markdown("**" + t("target_title") + "**")
    if model_names:
        opts = [t("target_select")] + model_names
        if "target_idx" not in st.session_state:
            st.session_state.target_idx = 0
        # Assicura che l'indice sia valido
        if st.session_state.target_idx >= len(opts):
            st.session_state.target_idx = 0
        sel_t = st.selectbox("target", opts, index=st.session_state.target_idx, label_visibility="collapsed")
        st.session_state.target_idx = opts.index(sel_t)
        target_from_sidebar = "" if sel_t == t("target_select") else sel_t
    else:
        target_from_sidebar = st.text_input("target", value="", label_visibility="collapsed")

    st.markdown("---")
    timeout = st.slider(t("timeout_label"), 30, 600, 300)

# ============================================================
# HEADER
# ============================================================

st.markdown("# " + t("header_main"))
st.markdown("### " + t("header_sub"))
st.markdown(f"<p style='color:#666;font-size:0.85rem'>{t('header_caption')} · Powered by <span style='font-weight:900'>Pietro Nappi</span></p>",
            unsafe_allow_html=True)

# Applica tema
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

# ============================================================
# MESSAGES
# ============================================================

if not st.session_state.messages:
    st.session_state.messages.append({"role": "assistant", "content": t("welcome")})

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ============================================================
# AUTO-RUN: se un modello e selezionato nella sidebar, parte l'analisi
# ============================================================

if target_from_sidebar and st.session_state.get("last_analyzed") != target_from_sidebar:
    gia_fatti = []
    with st.chat_message("user"):
        st.markdown(target_from_sidebar)
    with st.chat_message("assistant"):
        with st.spinner(t("analyzing").format(target_from_sidebar)):
            result = run_analysis(ifc_folder=ifc_folder, target=target_from_sidebar,
                                  gia_fatti=gia_fatti, timeout=timeout)
        st.session_state.last_result = result
        st.session_state.last_analyzed = target_from_sidebar

        if "error" in result:
            st.error("ERROR: " + result["error"])
            resp = "ERROR: " + result["error"]
        else:
            sample = result["sample"]
            if sample is None:
                resp = t("not_found").format(target_from_sidebar, result["n_modelli"])
                st.warning(resp)
            else:
                li = []
                li.append("### " + t("analysis_done") + "\n")
                li.append("**" + t("field_model") + ":** " + sample["target_name"])
                li.append("**" + t("field_neighbor") + ":** " + sample["vicino_name"])
                li.append("**" + t("field_similarity") + ":** " + str(round(sample["sim_media"]*100, 1)) + "%")
                li.append("  - " + t("field_energy") + ": " + str(round(sample["sim_energ"]*100, 1)) + "%")
                li.append("  - " + t("field_structural") + ": " + str(round(sample["sim_strut"]*100, 1)) + "%\n")
                if sample["gia_fatti"]:
                    li.append("**" + t("field_done") + " (" + t("field_excluded") + "):** " + ", ".join(sample["gia_fatti"]) + "\n")
                li.append("| " + t("table_intervention") + " | " + t("table_type") + " | " + t("table_quantity") + " | " + t("table_cost") + " |")
                li.append("|-----------|------|----------|-------|")
                for c in sample["interventi_campione"]:
                    li.append("| " + c["nome"] + " | " + c["tipo"] + " | " + str(int(c["quantita"])) + " " + c["unita_misura"] + " | " + str(round(c["costo_totale"], 2)) + " |")
                li.append("\n**" + t("total_label") + ":** EUR " + f'{sample["totale_complessivo"]:,.2f}')
                resp = "\n".join(li)
                st.markdown(resp)

                try:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                        pd.DataFrame(result["riepilogo"]).T.to_excel(writer, sheet_name="Riepilogo")
                        pd.DataFrame({t("field_model"): [sample["target_name"]],
                                      t("field_neighbor"): [sample["vicino_name"]],
                                      t("field_similarity"): [sample["sim_media"]]}).to_excel(writer, sheet_name="Campione", index=False)
                        if sample["interventi_campione"]:
                            pd.DataFrame(sample["interventi_campione"]).to_excel(writer, sheet_name="Interventi", index=False)
                    buf.seek(0)
                    st.download_button(label=t("download_excel"), data=buf,
                                       file_name="Stima_" + target_from_sidebar.replace(" ", "_") + ".xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as e:
                    st.caption(str(e))

        st.session_state.messages.append({"role": "user", "content": target_from_sidebar})
        st.session_state.messages.append({"role": "assistant", "content": resp})

# ============================================================
# INPUT
# ============================================================

user_input = st.chat_input(t("chat_placeholder"))

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    target_input = ""
    user_lower = user_input.lower().strip()
    for name in model_names:
        nc = name.lower().replace(".ifc", "").replace("-", " ").replace("_", " ")
        if any(w in nc for w in user_lower.split() if len(w) > 2):
            target_input = name
            break

    if not target_input and target_from_sidebar:
        target_input = target_from_sidebar

    if not target_input:
        resp = t("no_target")
        with st.chat_message("assistant"):
            st.warning(resp)
        st.session_state.messages.append({"role": "assistant", "content": resp})
    else:
        gia_fatti = []

        with st.chat_message("assistant"):
            with st.spinner(t("analyzing").format(target_input)):
                result = run_analysis(ifc_folder=ifc_folder, target=target_input,
                                      gia_fatti=gia_fatti, timeout=timeout)

            st.session_state.last_result = result

            if "error" in result:
                st.error("ERROR: " + result["error"])
                resp = "ERROR: " + result["error"]
            else:
                sample = result["sample"]
                if sample is None:
                    resp = t("not_found").format(target_input, result["n_modelli"])
                    st.warning(resp)
                else:
                    li = []
                    li.append("### " + t("analysis_done") + "\n")
                    li.append("**" + t("field_model") + ":** " + sample["target_name"])
                    li.append("**" + t("field_neighbor") + ":** " + sample["vicino_name"])
                    li.append("**" + t("field_similarity") + ":** " + str(round(sample["sim_media"]*100, 1)) + "%")
                    li.append("  - " + t("field_energy") + ": " + str(round(sample["sim_energ"]*100, 1)) + "%")
                    li.append("  - " + t("field_structural") + ": " + str(round(sample["sim_strut"]*100, 1)) + "%\n")
                    if sample["gia_fatti"]:
                        li.append("**" + t("field_done") + " (" + t("field_excluded") + "):** " + ", ".join(sample["gia_fatti"]) + "\n")
                    li.append("| " + t("table_intervention") + " | " + t("table_type") + " | " + t("table_quantity") + " | " + t("table_cost") + " |")
                    li.append("|-----------|------|----------|-------|")
                    for c in sample["interventi_campione"]:
                        li.append("| " + c["nome"] + " | " + c["tipo"] + " | " + str(int(c["quantita"])) + " " + c["unita_misura"] + " | " + str(round(c["costo_totale"], 2)) + " |")
                    li.append("\n**" + t("total_label") + ":** EUR " + f'{sample["totale_complessivo"]:,.2f}')
                    resp = "\n".join(li)
                    st.markdown(resp)

                    try:
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                            pd.DataFrame(result["riepilogo"]).T.to_excel(writer, sheet_name="Riepilogo")
                            pd.DataFrame({t("field_model"): [sample["target_name"]],
                                          t("field_neighbor"): [sample["vicino_name"]],
                                          t("field_similarity"): [sample["sim_media"]]}).to_excel(writer, sheet_name="Campione", index=False)
                            if sample["interventi_campione"]:
                                pd.DataFrame(sample["interventi_campione"]).to_excel(writer, sheet_name="Interventi", index=False)
                        buf.seek(0)
                        st.download_button(label=t("download_excel"), data=buf,
                                           file_name="Stima_" + target_input.replace(" ", "_") + ".xlsx",
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as e:
                        st.caption(str(e))

            st.session_state.messages.append({"role": "assistant", "content": resp})

st.markdown("---")
st.markdown(f"<div style='text-align:center;color:#484f58;font-size:0.75rem;font-weight:600;letter-spacing:0.05em'>{t('footer')}</div>", unsafe_allow_html=True)
