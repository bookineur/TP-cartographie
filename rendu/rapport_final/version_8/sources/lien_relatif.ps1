# Remet le lien vers la vidéo en chemin relatif (video/demo_localisation_scan.mp4) et réexporte le PDF,
# sans laisser Word transformer les liens en chemins absolus à l'enregistrement.
$d = Split-Path -Parent $PSScriptRoot
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v8.docx")
  foreach ($h in $doc.Hyperlinks) {
    if ($h.Address -like "*demo_localisation_scan.mp4") { "avant : $($h.Address)"; $h.Address = "video/demo_localisation_scan.mp4"; "après : $($h.Address)" }
  }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v8.pdf", 17)
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
