"""
folder_picker.py - Selettore cartella IFC.
Seleziona una cartella e carica tutti gli IFC (anche sotto cartelle).
"""
import streamlit.components.v1 as components
import streamlit as st
import os
import tempfile

_FOLDER_PICKER_HTML = """
<div id="fp">
<input type="file" id="fi" webkitdirectory multiple style="display:none" onchange="go(this.files)">
<div class="uz" onclick="document.getElementById('fi').click()" id="zone">
  <div class="il">&#128193; Seleziona cartella IFC</div>
  <div class="sl">Tutti i file IFC delle sotto cartelle vengono caricati</div>
</div>
<div class="st" id="st"></div>
<div class="fl" id="fl"></div>
</div>
<style>
#fp { font-family: 'JetBrains Mono', monospace; }
.uz { border:2px dashed #58a6ff; border-radius:8px; padding:14px; text-align:center;
      cursor:pointer; transition:all 0.2s; background:rgba(88,166,255,0.05); }
.uz:hover { background:rgba(88,166,255,0.12); border-color:#79c0ff; }
.il { color:#58a6ff; font-size:0.85rem; font-weight:600; }
.sl { color:#8b949e; font-size:0.7rem; margin-top:3px; }
.st { margin-top:6px; font-size:0.75rem; color:#8b949e; }
.st.ok { color:#3fb950; }
.st.err { color:#f85149; }
.fl { margin-top:4px; max-height:100px; overflow-y:auto; font-size:0.65rem; color:#8b949e; }
.fl div { padding:1px 0; }
</style>
<script>
function go(files) {
  var ifc = [];
  for (var i=0; i<files.length; i++) {
    if (files[i].name.toLowerCase().endsWith('.ifc'))
      ifc.push({name:files[i].name, path:files[i].webkitRelativePath, size:files[i].size});
  }
  var s = document.getElementById('st');
  var l = document.getElementById('fl');
  if (ifc.length===0) {
    s.className='st err'; s.innerHTML='Nessun file IFC trovato'; l.innerHTML=''; return;
  }
  s.className='st ok'; s.innerHTML=ifc.length+' file IFC trovati';
  var h='';
  for (var j=0;j<ifc.length;j++)
    h+='<div>'+ifc[j].path+' ('+(ifc[j].size/1048576).toFixed(1)+' MB)</div>';
  l.innerHTML=h;
}
</script>
"""

def folder_picker():
    components.html(_FOLDER_PICKER_HTML, height=160)
