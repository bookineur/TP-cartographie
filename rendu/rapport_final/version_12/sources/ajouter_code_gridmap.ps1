# Rapport v12 : ajoute « L'algorithme et le code de la grid map » dans la section 2.3, après la figure 9 ;
# met à jour le sommaire et exporte le PDF.
$ErrorActionPreference = "Stop"
$d = Split-Path -Parent $PSScriptRoot
$T = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\textes_code_gridmap.json" | ConvertFrom-Json
if (-not $T.titre) { throw "textes de la section introuvables" }
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v12.docx")
  $ancre = $null
  foreach ($p in $doc.Paragraphs) { if ($p.Range.Text.StartsWith($T.ancre)) { $ancre = $p } }
  if ($ancre -eq $null) { throw "légende de la figure 9 introuvable" }
  function Nouveau($p0) { $p0.Range.InsertParagraphAfter(); $n = $p0.Next(); $n.Style = -1; $n.Format.PageBreakBefore = 0; $n.Range.Font.Reset(); return $n }
  function Texte($par, $txt) { $r = $par.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Text = $txt; return $r }
  function Para($p0, $gras, $txt) { $n = Nouveau $p0; Texte $n ($gras + $txt) | Out-Null; $n.Alignment = 3; $n.SpaceAfter = 6; if ($gras) { $doc.Range($n.Range.Start, $n.Range.Start + $gras.Length).Bold = 1 }; return $n }
  function Code($p0, $lignes) {
    $c = $p0
    foreach ($l in $lignes) {
      $c = Nouveau $c; $r = Texte $c $l; $r.Font.Name = "Consolas"; $r.Font.Size = 8; $c.Alignment = 0
      $c.SpaceAfter = 0; $c.SpaceBefore = 0; $c.LineSpacingRule = 0; $c.LeftIndent = 14; $c.RightIndent = 14
      $c.Shading.BackgroundPatternColor = 0xF6F4F3
    }
    $c.SpaceAfter = 8; return $c
  }
  $h = Nouveau $ancre; Texte $h $T.titre | Out-Null; $h.Style = -4
  $p = Para $h $T.methode_gras $T.methode
  $p = Para $p $T.algo_gras ""
  $p = Code $p $T.algo
  foreach ($c in $T.codes) { $p = Para $p $c[0] $c[1]; $p = Code $p $c[2] }
  $p = Para $p "" $T.fin
  "bloc grid map ajouté"
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v12.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
