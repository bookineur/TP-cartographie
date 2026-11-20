# Rapport v17 (allégé pour l'envoi) : même contenu que la v16, vidéos intégrées remplacées par leurs versions 720p
# (dossier video_allegee), puis images recompressées par compresser_images.py ; le PDF est exporté ensuite.
param([switch]$pdf)
$ErrorActionPreference = "Stop"
$d = Split-Path -Parent $PSScriptRoot; $m = [Type]::Missing
$f = "$d\rapport_final_TP_cartographie_v17_allege.docx"
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open($f)
  if ($pdf) {
    $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v17_allege.pdf", 17, $false, 0)
    "PDF exporté"
  } else {
    $videos = @{ "Lancer la vidéo" = "demo_localisation_scan.mp4"; "Lancer la vidéo du bonus" = "exploration_automatique_demo.mp4" }
    foreach ($lab in $videos.Keys) {
      $cible = $null
      foreach ($s in $doc.InlineShapes) { if ($s.OLEFormat -ne $null -and $s.OLEFormat.IconLabel -eq $lab) { $cible = $s } }
      if ($cible -eq $null) { throw "vidéo introuvable : $lab" }
      $r = $cible.Range; $cible.Delete()
      $n = $doc.InlineShapes.AddOLEObject($m, "$d\video_allegee\$($videos[$lab])", $false, $true, $m, $m, $lab, $r)
      "remplacée : $lab"
    }
    $doc.Save()
  }
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
