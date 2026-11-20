# Rapport v10 : remplace la vidéo de localisation intégrée par la version 3 (avec l'algorithme et le code) et met à jour
# la phrase qui la présente ; exporte le PDF. La vidéo du bonus n'est pas touchée.
$ErrorActionPreference = "Stop"
$d = Split-Path -Parent $PSScriptRoot; $m = [Type]::Missing
$video = (Resolve-Path "$d\..\..\..\resultats\demo_localisation\version_3\demo_localisation_scan_v3.mp4").Path
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v10.docx")
  $cible = $null
  foreach ($s in $doc.InlineShapes) { if ($s.OLEFormat -ne $null -and $s.OLEFormat.IconLabel -eq "Lancer la vidéo") { $cible = $s } }
  if ($cible -eq $null) { throw "vidéo de localisation intégrée introuvable" }
  $r = $cible.Range; $cible.Delete()
  $n = $doc.InlineShapes.AddOLEObject($m, $video, $false, $true, $m, $m, "Lancer la vidéo", $r)
  "vidéo remplacée : $($n.OLEFormat.ProgID)"
  $rr = $doc.Content
  "phrase : " + $rr.Find.Execute("(76 s) montre trois tirages à la suite", $true, $false, $false, $false, $false, $true, 0, $false, "(1 min 52) présente d'abord l'algorithme et le code de la localisation, puis trois tirages à la suite", 2)
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v10.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
