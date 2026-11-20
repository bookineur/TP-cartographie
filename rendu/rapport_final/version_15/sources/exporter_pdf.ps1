# Rapport v15 (version finale fournie) : export PDF sans modifier le .docx.
$ErrorActionPreference = "Stop"
$d = Split-Path -Parent $PSScriptRoot
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v15.docx", $false, $true)
  "sommaires : " + $doc.TablesOfContents.Count
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v15.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
