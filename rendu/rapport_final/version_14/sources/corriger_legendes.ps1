# Rapport v14 : complète les légendes tronquées (figures 11, 12, 13, 17, 18, 20) et corrige la taille de la salle (13 × 10 m) et deux phrases coupées (sections 4.3 et 5.3).
$ErrorActionPreference = "Stop"
$d = Split-Path -Parent $PSScriptRoot
$R = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\corrections_legendes.json" | ConvertFrom-Json
if ($R.Count -lt 9) { throw "corrections introuvables" }
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v14.docx")
  foreach ($c in $R) {
    $n = 0
    while ($true) {
      $r = $doc.Content; $f = $r.Find; $f.ClearFormatting(); $f.MatchCase = $true; $f.Forward = $true; $f.Wrap = 0
      if (-not $f.Execute($c[0])) { break }
      $r.Text = $c[1]; $n++
      if ($c[1].Contains($c[0])) { break }   # le nouveau texte contient l'ancien : une seule occurrence
      if ($n -gt 5) { throw "boucle sur $($c[0])" }
    }
    if ($n -eq 0) { throw "texte introuvable : $($c[0])" }
    "$n x : $($c[0])"
  }
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v14.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
