# Intègre la vidéo dans le Word (objet à double-cliquer) à la place du marqueur [[VIDEO]], met à jour le sommaire et exporte le PDF.
$d = Split-Path -Parent $PSScriptRoot; $m = [Type]::Missing
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v7.docx")
  $r = $doc.Content
  if ($r.Find.Execute("[[VIDEO]]")) {
    $r.Text = ""
    $s = $doc.InlineShapes.AddOLEObject($m, "$((Resolve-Path "$d\..\..\..\resultats\demo_localisation\version_2\demo_localisation_scan_v2.mp4").Path)", $false, $true, $m, $m, "Lancer la vidéo", $r)
    "objet inséré : $($s.OLEFormat.ProgID)"
  } else { "marqueur introuvable" }
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v7.pdf", 17)
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
