$movies = Get-Content -Raw 'films.json' | ConvertFrom-Json
$movies | ForEach-Object {
    $_.watched = ($_.status -eq '已看')
}
@($movies) | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 'films.json'
Write-Host "已修正 $(@($movies).Count) 部电影的已看标记"
