"""
folder_uploader.py - Componente Streamlit per selezione cartella IFC.
Usa webkitdirectory per permettere la selezione di un'intera cartella dal browser.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile
import base64

_FOLDER_PICKER_HTML = """
<div id="folder-picker">
    <style>
        .folder-btn {
            width: 100%%;
            padding: 10px 16px;
            border: 2px dashed #58a6ff;
            border-radius: 8px;
            background: transparent;
            color: #58a6ff;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }
        .folder-btn:hover {
            background: rgba(88,166,255,0.1);
            border-color: #79c0ff;
        }
        .folder-status {
            margin-top: 8px;
            font-size: 0.78rem;
            color: #8b949e;
            font-family: 'JetBrains Mono', monospace;
        }
        .folder-status.ok { color: #3fb950; }
        .folder-status.err { color: #f85149; }
        .file-list {
            margin-top: 6px;
            max-height: 120px;
            overflow-y: auto;
            font-size: 0.7rem;
            color: #8b949e;
            font-family: 'JetBrains Mono', monospace;
        }
        .file-list div { padding: 1px 0; }
    </style>
    <input type="file" id="folder-input" webkitdirectory multiple style="display:none"
           onchange="handleFolder(this.files)">
    <button class="folder-btn" onclick="document.getElementById('folder-input').click()">
        &#128193; Seleziona cartella IFC
    </button>
    <div id="folder-status" class="folder-status"></div>
    <div id="file-list" class="file-list"></div>
</div>

<script>
function handleFolder(files) {
    var ifcFiles = [];
    for (var i = 0; i < files.length; i++) {
        var name = files[i].name;
        if (name.toLowerCase().endsWith('.ifc')) {
            ifcFiles.push({
                name: name,
                path: files[i].webkitRelativePath || name,
                size: files[i].size
            });
        }
    }

    var status = document.getElementById('folder-status');
    var list = document.getElementById('file-list');

    if (ifcFiles.length === 0) {
        status.className = 'folder-status err';
        status.innerHTML = 'Nessun file IFC trovato nella cartella';
        list.innerHTML = '';
        return;
    }

    status.className = 'folder-status ok';
    status.innerHTML = ifcFiles.length + ' file IFC trovati';

    var html = '';
    for (var j = 0; j < ifcFiles.length; j++) {
        html += '<div>' + ifcFiles[j].name + ' (' + (ifcFiles[j].size / 1048576).toFixed(1) + ' MB)</div>';
    }
    list.innerHTML = html;

    // Invia la lista al parent (Streamlit)
    window.parent.postMessage({type: 'streamlit:folderSelected', files: ifcFiles}, '*');
}
</script>
"""


def folder_uploader(key="folder_upload"):
    """
    Mostra un componente per selezionare una cartella IFC.
    Ritorna la lista di nomi file IFC selezionati.
    """
    components.html(_FOLDER_PICKER_HTML, height=180)
