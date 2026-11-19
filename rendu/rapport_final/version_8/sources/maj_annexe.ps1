# Met l'annexe « Contenu du livrable » en accord avec l'organisation du ZIP, puis réexporte le PDF.
$d = Split-Path -Parent $PSScriptRoot
$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Open("$d\rapport_final_TP_cartographie_v8.docx")
  foreach ($pair in @(@("depots/TP-cartographie/", "code/1_outil1_carto_python/"), @("depots/lidar_lab/", "code/2_outil2_lidar_lab/"), @("(dans lidar_lab)", "(dans code/2_outil2_lidar_lab)"))) {
    $r = $doc.Content
    $ok = $r.Find.Execute($pair[0], $true, $false, $false, $false, $false, $true, 0, $false, $pair[1], 2)
    "$($pair[0]) -> $($pair[1]) : $ok"
  }
  $done = $false
  foreach ($t in $doc.Tables) {
    for ($i = 1; $i -le $t.Rows.Count -and -not $done; $i++) {
      if ($t.Cell($i, 1).Range.Text -like "LISEZMOI.txt*") {
        $row = $t.Rows.Add($t.Rows.Item($i))
        $t.Cell($i, 1).Range.Text = "code/3_robot_arduino_V5/"
        $t.Cell($i, 2).Range.Text = "Programme de l'ESP32 retenu (version 5) et son mode d'emploi ; les autres versions sont dans le dépôt de l'outil 1 (dossier arduino/)"
        $done = $true
      }
    }
    if ($done) { break }
  }
  "ligne Arduino ajoutée : $done"
  $doc.TablesOfContents | ForEach-Object { $_.Update() }
  $doc.Save()
  $doc.ExportAsFixedFormat("$d\rapport_final_TP_cartographie_v8.pdf", 17)
  $doc.Close(0)
} catch { "erreur : $_" } finally { $w.Quit() }
