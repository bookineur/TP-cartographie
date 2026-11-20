# Ajoute la vidéo du bonus au rapport v9 (copie de la v8 relue) : texte, planche, lien, vidéo intégrée, annexe ; exporte le PDF.
$d = Split-Path -Parent $PSScriptRoot; $m = [Type]::Missing
$T = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\textes_video_bonus.json" | ConvertFrom-Json
$video = (Resolve-Path "$d\..\..\..\resultats\video_exploration\version_2\exploration_automatique_demo.mp4").Path
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $w.DefaultWebOptions().UpdateLinksOnSave = $false
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v9.docx")
  $cap = $null
  foreach ($p in $doc.Paragraphs) { if ($p.Range.Text.StartsWith("Figure 26 ")) { $cap = $p } }
  if ($cap -eq $null) { throw "légende de la figure 26 introuvable" }
  function Nouveau($prev) { $prev.Range.InsertParagraphAfter(); $n = $prev.Next(); $n.Style = -1; $n.Format.PageBreakBefore = 0; $n.Range.Font.Reset(); return $n }
  function Texte($par, $txt) { $r = $par.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Text = $txt; return $r }
  # 1. présentation
  $p1 = Nouveau $cap; Texte $p1 ($T.intro_gras + $T.intro) | Out-Null; $p1.Alignment = 3; $p1.SpaceAfter = 6
  $doc.Range($p1.Range.Start, $p1.Range.Start + $T.intro_gras.Length).Bold = 1
  # 2. planche
  $p2 = Nouveau $p1; $p2.Alignment = 1; $p2.KeepWithNext = -1
  $r2 = $p2.Range; $r2.MoveEnd(1, -1) | Out-Null
  $pic = $doc.InlineShapes.AddPicture("$d\figures\planche_video_exploration.png", $false, $true, $r2)
  $pic.LockAspectRatio = -1; $pic.Width = 440
  # 3. légende
  $p3 = Nouveau $p2; $r3 = Texte $p3 $T.legende; $p3.Alignment = 1; $r3.Italic = 1; $r3.Font.Size = 9; $r3.Font.Color = 0x555555; $p3.SpaceAfter = 10
  # 4. lien
  $p4 = Nouveau $p3; Texte $p4 ($T.lien_avant + $T.lien + $T.lien_apres) | Out-Null; $p4.Alignment = 0
  $s = $p4.Range.Start
  $doc.Range($s, $s + $T.lien_avant.Length).Bold = 1
  $rl = $doc.Range($s + $T.lien_avant.Length, $s + $T.lien_avant.Length + $T.lien.Length)
  $doc.Hyperlinks.Add($rl, $T.lien) | Out-Null
  # 5. vidéo intégrée
  $p5 = Nouveau $p4; $p5.Alignment = 1
  $r5 = $p5.Range; $r5.MoveEnd(1, -1) | Out-Null
  $o = $doc.InlineShapes.AddOLEObject($m, $video, $false, $true, $m, $m, $T.icone, $r5)
  "vidéo intégrée : $($o.OLEFormat.ProgID)"
  # synthèse : figures du bonus
  $rr = $doc.Content; "synthèse : " + $rr.Find.Execute("Figures 25, 26", $true, $false, $false, $false, $false, $true, 0, $false, "Figures 25 à 27", 2)
  # annexe : ligne pour la vidéo du bonus, après celle de la démo de localisation
  $ok = $false
  foreach ($t in $doc.Tables) {
    for ($i = 1; $i -le $t.Rows.Count -and -not $ok; $i++) {
      if ($t.Cell($i, 1).Range.Text -like "video/demo_localisation_scan.mp4*") {
        if ($i -lt $t.Rows.Count) { $t.Rows.Add($t.Rows.Item($i + 1)) | Out-Null } else { $t.Rows.Add() | Out-Null }
        $t.Cell($i + 1, 1).Range.Text = $T.annexe_c1; $t.Cell($i + 1, 2).Range.Text = $T.annexe_c2; $ok = $true
      }
    }
    if ($ok) { break }
  }
  "annexe : $ok"
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v9.pdf", 17)
  "PDF exporté"
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
