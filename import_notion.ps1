$ErrorActionPreference = 'Stop'

$pageId = '2bb630d2-d8de-80fb-8ef1-d5b9d38274e2'
$collectionViewId = '352630d2-d8de-80f8-9edf-000cdecd6381'
$spaceId = 'e666fc4a-5e38-471d-a165-6baef0036f88'

function Invoke-NotionApi($path, $body) {
    $json = $body | ConvertTo-Json -Depth 10
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        try {
            return Invoke-RestMethod -Uri "https://www.notion.so/api/v3/$path" -Method Post `
                -ContentType 'application/json' -Body $json
        } catch {
            if ($attempt -eq 4) { throw }
            Start-Sleep -Seconds $attempt
        }
    }
}

$page = Invoke-NotionApi 'loadCachedPageChunk' @{
    pageId = $pageId; limit = 100; cursor = @{ stack = @() }; chunkNumber = 0; verticalColumns = $false
}
$ids = $page.recordMap.collection_view.$collectionViewId.value.value.page_sort

$movies = @()
foreach ($batch in @($ids | ForEach-Object -Begin { $bucket = @() } -Process {
    $bucket += $_
    if ($bucket.Count -eq 50) { ,$bucket; $bucket = @() }
} -End { if ($bucket.Count) { ,$bucket } })) {
    $records = Invoke-NotionApi 'syncRecordValues' @{
        requests = @($batch | ForEach-Object {
            @{ pointer = @{ table = 'block'; id = $_; spaceId = $spaceId }; version = -1 }
        })
    }
    foreach ($entry in $records.recordMap.block.PSObject.Properties) {
        $record = $entry.Value.value.value
        if ($record.type -ne 'page' -or -not $record.alive) { continue }
        $props = $record.properties
        $status = if ($props.'X]yd') { $props.'X]yd'[0][0] } else { '未看' }
        $watched = if ($status -eq '已看') { $true } else { $false }
        $movies += [ordered]@{
            id = $record.id
            title = if ($props.title) { $props.title[0][0] } else { '' }
            rating = if ($props.'ly=p') { $props.'ly=p'[0][0] } else { '' }
            watched = $watched
            status = $status
            notes = if ($props.'q<v\') { $props.'q<v\'[0][0] } else { '' }
        }
    }
}

$movies | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 'films.json'
Write-Host "已导出 $($movies.Count) 部电影到 films.json"
