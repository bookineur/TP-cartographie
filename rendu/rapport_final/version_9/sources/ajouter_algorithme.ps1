# Ajoute la section « 5.4 L'algorithme et le code » après la vidéo du bonus, met à jour le sommaire, exporte le PDF.
$d = Split-Path -Parent $PSScriptRoot
$ErrorActionPreference = "Stop"
$T = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\textes_algorithme.json" | ConvertFrom-Json
if (-not $T.titre) { throw "textes de la section introuvables" }
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v9.docx")
  $lien = $null
  foreach ($p in $doc.Paragraphs) { if ($p.Range.Text.StartsWith("Vidéo : video/exploration_automatique_demo.mp4")) { $lien = $p } }
  if ($lien -eq $null) { throw "paragraphe du lien vers la vidéo du bonus introuvable" }
  $prev = $lien.Next()   # paragraphe de la vidéo intégrée
  function Nouveau($p0) { $p0.Range.InsertParagraphAfter(); $n = $p0.Next(); $n.Style = -1; $n.Format.PageBreakBefore = 0; $n.Range.Font.Reset(); $n.Range.ParagraphFormat.Shading.BackgroundPatternColor = -16777216; return $n }
  function Texte($par, $txt) { $r = $par.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Text = $txt; return $r }
  function Para($p0, $gras, $txt) { $n = Nouveau $p0; Texte $n ($gras + $txt) | Out-Null; $n.Alignment = 3; $n.SpaceAfter = 6; if ($gras) { $doc.Range($n.Range.Start, $n.Range.Start + $gras.Length).Bold = 1 }; return $n }
  function Code($p0, $lignes) {
    $c = $p0
    foreach ($l in $lignes) {
      $c = Nouveau $c; $r = Texte $c $l; $r.Font.Name = "Consolas"; $r.Font.Size = 8.5; $c.Alignment = 0
      $c.SpaceAfter = 0; $c.SpaceBefore = 0; $c.LineSpacingRule = 0; $c.LeftIndent = 14; $c.RightIndent = 14
      $c.Shading.BackgroundPatternColor = 0xF6F4F3
    }
    $c.SpaceAfter = 8; return $c
  }
  $h = Nouveau $prev; Texte $h $T.titre | Out-Null; $h.Style = -3
  $p = Para $h $T.methode_gras $T.methode
  $p = Para $p $T.algo_gras ""
  $p = Code $p $T.algo
  $p = Para $p $T.code1_gras $T.code1_txt
  $p = Code $p $T.code1
  $p = Para $p $T.code2_gras $T.code2_txt
  $p = Code $p $T.code2
  $p = Para $p "" $T.fin
  "section ajoutée"
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v9.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
