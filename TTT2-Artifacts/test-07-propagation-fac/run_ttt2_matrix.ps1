[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$VerificationRoot = Join-Path $RepoRoot 'results\test-07-propagation-fac-tests\verification'
$RunRoot = Join-Path $VerificationRoot 'ttt2'
$MirrorRoot = $PSScriptRoot
$MirrorRunRoot = Join-Path $MirrorRoot 'runs'
$MirrorCpfRoot = Join-Path $MirrorRoot 'cpf'
$MirrorTrsRoot = Join-Path $MirrorRoot 'trs'
$Endpoint = 'http://138.232.18.220/tool/ttt2'
$TimeoutSeconds = 60
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

foreach ($directory in @($RunRoot, $MirrorRunRoot, $MirrorCpfRoot, $MirrorTrsRoot)) {
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
}

$systems = [ordered]@{
    S1_fac = Join-Path $VerificationRoot 'S1_fac.trs'
    S2_nofac = Join-Path $VerificationRoot 'S2_nofac.trs'
    S3_ag316 = Join-Path $VerificationRoot 'S3_ag316.trs'
    S4_schema = Join-Path $VerificationRoot 'S4_schema.trs'
}

foreach ($entry in $systems.GetEnumerator()) {
    Copy-Item -LiteralPath $entry.Value -Destination (Join-Path $MirrorTrsRoot (Split-Path $entry.Value -Leaf)) -Force
}

$strategySpecs = [ordered]@{
    auto = @{
        strategy = 'WyItdCJd'
        description = 'FAST/default automatic strategy'
    }
    lpo = @{
        strategy = 'WyItdCIsIi1zIiwiJSUlUExBQ0VIT0xERVJfVkFMVUVfTFBPJSUlIl0='
        lpoStrategy = 'lpo'
        lpoPrecedence = ''
        description = 'LPO only'
    }
    kbo = @{
        strategy = 'WyItdCIsIi1zIiwiJSUlUExBQ0VIT0xERVJfVkFMVUVfS0JPJSUlIl0='
        kboStrategy = 'kbo'
        kboPrecendence = ''
        kboWeights = ''
        kboW0 = ''
        description = 'KBO only'
    }
    poly = @{
        strategy = 'WyItdCIsIi1zIiwiJSUlUExBQ0VIT0xERVJfVkFMVUVfUE9MWSUlJSJd'
        polyStrategy = 'poly -direct -ib 5 -ob 6'
        polyInterpretations = ''
        description = 'direct linear polynomial only'
    }
    dp = @{
        strategy = 'WyItdCIsIi1zIl0='
        strategyExpert = 'dp;(tdg | sccs | sc)*;(edg -gtcap -nl[2] | sccs | sc | sc -rec -defs[1] | sc -mulex -defs[1] | sct | {ur?;lpo -dp -af[2]}restore | {ur?;matrix -dp -dim 2 -ib 2 -ob 2 -ur[2]}restore | uncurryx?;uncurryx -top )[10]*'
        description = 'dependency-pair branch with graph, subterm, LPO reduction-pair, and matrix reduction-pair processors'
    }
}

$runMatrix = [ordered]@{
    S1_fac = @('auto', 'lpo', 'kbo', 'poly', 'dp')
    S2_nofac = @('auto', 'lpo', 'kbo', 'poly', 'dp')
    S3_ag316 = @('auto', 'lpo', 'kbo', 'poly', 'dp')
    S4_schema = @('lpo', 'kbo', 'poly', 'dp')
}

$results = [System.Collections.Generic.List[object]]::new()

foreach ($systemName in $runMatrix.Keys) {
    $trsPath = $systems[$systemName]
    $trsText = [System.IO.File]::ReadAllText($trsPath)

    foreach ($strategyName in $runMatrix[$systemName]) {
        $spec = $strategySpecs[$strategyName]
        $body = @{
            'bit-tool-input' = $trsText
            strategy = $spec.strategy
            cetaEnabled = '1'
        }
        foreach ($key in $spec.Keys) {
            if ($key -notin @('strategy', 'description')) {
                $body[$key] = $spec[$key]
            }
        }

        $baseName = "${systemName}_${strategyName}"
        $rawHtmlPath = Join-Path $RunRoot "${baseName}.html"
        $outputPath = Join-Path $RunRoot "${baseName}.txt"
        $cpfPath = Join-Path $RunRoot "${baseName}.cpf"

        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $transportExit = 0
        $transportError = ''
        try {
            $response = Invoke-WebRequest -Uri $Endpoint -Method Post -Body $body -TimeoutSec $TimeoutSeconds
            $html = $response.Content
        } catch {
            $transportExit = 1
            $transportError = $_.Exception.Message
            $html = ''
        }
        $stopwatch.Stop()

        [System.IO.File]::WriteAllText($rawHtmlPath, $html, $Utf8NoBom)

        $commandMatch = [regex]::Match(
            $html,
            '<strong>Command:</strong><br>\s*<pre>(.*?)</pre>',
            [System.Text.RegularExpressions.RegexOptions]::Singleline)
        $resultMatch = [regex]::Match(
            $html,
            '<strong>Result:</strong><br>\s*<pre>(.*?)</pre>',
            [System.Text.RegularExpressions.RegexOptions]::Singleline)
        $errorMatch = [regex]::Match(
            $html,
            '<strong>Errors:</strong><br>\s*<pre>(.*?)</pre>',
            [System.Text.RegularExpressions.RegexOptions]::Singleline)

        $remoteCommand = if ($commandMatch.Success) {
            [System.Net.WebUtility]::HtmlDecode($commandMatch.Groups[1].Value).Trim()
        } else {
            'NOT_RETURNED'
        }
        $decodedResult = if ($resultMatch.Success) {
            [System.Net.WebUtility]::HtmlDecode($resultMatch.Groups[1].Value).Trim()
        } elseif ($errorMatch.Success) {
            'REMOTE ERROR:' + [Environment]::NewLine +
                [System.Net.WebUtility]::HtmlDecode($errorMatch.Groups[1].Value).Trim()
        } else {
            'NO RESULT BLOCK RETURNED'
        }

        $cpfMatch = [regex]::Match(
            $decodedResult,
            '<\?xml version="1\.0"\?>.*?</certificationProblem>',
            [System.Text.RegularExpressions.RegexOptions]::Singleline)
        if ($cpfMatch.Success) {
            [System.IO.File]::WriteAllText($cpfPath, $cpfMatch.Value, $Utf8NoBom)
            Copy-Item -LiteralPath $cpfPath -Destination (Join-Path $MirrorCpfRoot "${baseName}.cpf") -Force
        }

        $cetaMatch = [regex]::Match($decodedResult, 'CeTA Result:\s*([^\r\n]+)')
        $cetaVerdict = if ($cetaMatch.Success) { $cetaMatch.Groups[1].Value.Trim() } else { 'NOT_RUN_OR_NOT_RETURNED' }

        $originalOutput = $decodedResult
        $marker = 'Original tool output:'
        $markerIndex = $decodedResult.IndexOf($marker, [System.StringComparison]::Ordinal)
        if ($markerIndex -ge 0) {
            $originalOutput = $decodedResult.Substring($markerIndex + $marker.Length).Trim()
            $xmlIndex = $originalOutput.IndexOf('<?xml', [System.StringComparison]::Ordinal)
            if ($xmlIndex -ge 0) {
                $originalOutput = $originalOutput.Substring(0, $xmlIndex).Trim()
            }
        }

        $resultTokenMatch = [regex]::Match($originalOutput, '^(YES|NO|MAYBE)', [System.Text.RegularExpressions.RegexOptions]::Multiline)
        $resultToken = if ($resultTokenMatch.Success) { $resultTokenMatch.Groups[1].Value } else { 'ERROR' }
        $toolTimeMatch = [regex]::Match($originalOutput, 'Time:\s*([0-9.]+)')
        $toolTime = if ($toolTimeMatch.Success) { $toolTimeMatch.Groups[1].Value } else { '' }

        $wrapperCommand = "Invoke-WebRequest -Uri '$Endpoint' -Method Post -TimeoutSec $TimeoutSeconds (form strategy: $strategyName)"
        $record = @(
            "tool: TTT2 1.19 [hg: unknown] via the University of Innsbruck integrated TTT2/CeTA host"
            "endpoint: $Endpoint"
            "system: $systemName"
            "input: $trsPath"
            "input_sha256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $trsPath).Hash)"
            "strategy_label: $strategyName"
            "strategy_description: $($spec.description)"
            "timeout_seconds: $TimeoutSeconds (HTTP wrapper wall-clock limit; the host's printed TTT2 command has no explicit numeric timeout)"
            "wrapper_command: $wrapperCommand"
            "remote_command: $remoteCommand"
            "transport_exit_status: $transportExit"
            "wall_time_seconds: $([Math]::Round($stopwatch.Elapsed.TotalSeconds, 3))"
            "ttt2_result: $resultToken"
            "ttt2_reported_time_seconds: $toolTime"
            "ceta_verdict: $cetaVerdict"
            "cpf_saved: $($cpfMatch.Success)"
            "transport_error: $transportError"
            ''
            '--- FULL DECODED RESULT BLOCK ---'
            $decodedResult
            ''
            '--- ORIGINAL TTT2 OUTPUT ---'
            $originalOutput
        ) -join [Environment]::NewLine
        [System.IO.File]::WriteAllText($outputPath, $record, $Utf8NoBom)
        Copy-Item -LiteralPath $outputPath -Destination (Join-Path $MirrorRunRoot "${baseName}.txt") -Force
        Copy-Item -LiteralPath $rawHtmlPath -Destination (Join-Path $MirrorRunRoot "${baseName}.html") -Force

        $results.Add([pscustomobject]@{
            system = $systemName
            strategy = $strategyName
            result = $resultToken
            tool_time_seconds = $toolTime
            wall_time_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
            exit_status = $transportExit
            ceta_verdict = $cetaVerdict
            cpf_saved = if ($cpfMatch.Success) { 'yes' } else { 'no' }
            source = "verification/ttt2/${baseName}.txt"
            remote_command = $remoteCommand
            timeout_note = '60-second HTTP wrapper wall-clock limit; remote command exposes no numeric timeout'
        })
    }
}

$jsonPath = Join-Path $MirrorRoot 'matrix_results.json'
[System.IO.File]::WriteAllText(
    $jsonPath,
    ($results | ConvertTo-Json -Depth 4),
    $Utf8NoBom)

Write-Output "Completed $($results.Count) TTT2 runs."
Write-Output "Run outputs: $RunRoot"
Write-Output "Mirror: $MirrorRoot"
