# Insère la conclusion (sources/conclusion.json) sous le titre « Conclusion personnelle », met à jour le sommaire, exporte le PDF.
$d = Split-Path -Parent $PSScriptRoot
$items = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\conclusion.json" | ConvertFrom-Json
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v8.docx")
  $h = $null
  foreach ($p in $doc.Paragraphs) { if ($p.OutlineLevel -eq 1 -and $p.Range.Text.Trim() -eq "Conclusion personnelle") { $h = $p } }
  if ($h -eq $null) { throw "titre « Conclusion personnelle » introuvable" }
  $next = $h.Next(); "paragraphe suivant le titre : niveau $($next.OutlineLevel), « $($next.Range.Text.Trim().Substring(0, [Math]::Min(40, $next.Range.Text.Trim().Length))) »"
  $prev = $h
  foreach ($it in $items) {
    $prev.Range.InsertParagraphAfter()
    $np = $prev.Next()
    $np.Style = -1
    $np.Format.PageBreakBefore = 0
    $r = $np.Range; $r.MoveEnd(1, -1) | Out-Null
    $r.Text = [string]$it[0] + [string]$it[1]
    $np.Alignment = 3
    $np.SpaceAfter = 6
    if ([string]$it[0]) { $b = $doc.Range($np.Range.Start, $np.Range.Start + ([string]$it[0]).Length); $b.Bold = 1 }
    $prev = $np
  }
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v8.pdf", 17)
  $doc.Close(0)
  "conclusion insérée : $($items.Count) paragraphes"
} catch { "erreur : $_" } finally { $w.Quit() }
