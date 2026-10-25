$ErrorActionPreference = "Stop"
$previousAutoDiscovery = $env:CSC_IDENTITY_AUTO_DISCOVERY
$previousCertLink = $env:CSC_LINK
$previousWindowsCertLink = $env:WIN_CSC_LINK
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configuredRoot = $env:ERSELMETZ_BUILD_OUTPUT_ROOT
$buildRoot = if ([string]::IsNullOrWhiteSpace($configuredRoot)) {
    Join-Path $repo "desktop\build"
} elseif ([IO.Path]::IsPathRooted($configuredRoot)) {
    [IO.Path]::GetFullPath($configuredRoot)
} else {
    [IO.Path]::GetFullPath((Join-Path $repo $configuredRoot))
}
$releaseRoot = if ([string]::IsNullOrWhiteSpace($env:ERSELMETZ_RELEASE_OUTPUT)) {
    Join-Path $repo "desktop\release"
} elseif ([IO.Path]::IsPathRooted($env:ERSELMETZ_RELEASE_OUTPUT)) {
    [IO.Path]::GetFullPath($env:ERSELMETZ_RELEASE_OUTPUT)
} else {
    [IO.Path]::GetFullPath((Join-Path $repo $env:ERSELMETZ_RELEASE_OUTPUT))
}
$repoPrefix = $repo.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($target in @($buildRoot, $releaseRoot)) {
    if (-not [IO.Path]::GetFullPath($target).StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing an Electron build or release output outside the repository."
    }
}
$package = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\package.json") -Raw | ConvertFrom-Json
$buildConfig = $package.build
$buildConfig.directories.output = $releaseRoot
$buildConfig.extraResources[0].from = Join-Path $buildRoot "backend\erselmetz-backend"
$buildConfig.extraResources[1].from = Join-Path $repo "desktop-ui\out"
$configPath = Join-Path ([IO.Path]::GetTempPath()) "erselmetz-electron-build-$PID.json"
[IO.File]::WriteAllText($configPath, ($buildConfig | ConvertTo-Json -Depth 32), [Text.UTF8Encoding]::new($false))
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
Remove-Item Env:CSC_LINK -ErrorAction SilentlyContinue
Remove-Item Env:WIN_CSC_LINK -ErrorAction SilentlyContinue
try {
    Push-Location (Join-Path $PSScriptRoot "..")
    & (Join-Path $PSScriptRoot "..\node_modules\.bin\electron-builder.cmd") --config $configPath --win nsis --x64
    if ($LASTEXITCODE -ne 0) { throw "The unsigned local Windows installer could not be built." }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $configPath -Force -ErrorAction SilentlyContinue
    if ($null -eq $previousAutoDiscovery) { Remove-Item Env:CSC_IDENTITY_AUTO_DISCOVERY -ErrorAction SilentlyContinue }
    else { $env:CSC_IDENTITY_AUTO_DISCOVERY = $previousAutoDiscovery }
    if ($null -eq $previousCertLink) { Remove-Item Env:CSC_LINK -ErrorAction SilentlyContinue }
    else { $env:CSC_LINK = $previousCertLink }
    if ($null -eq $previousWindowsCertLink) { Remove-Item Env:WIN_CSC_LINK -ErrorAction SilentlyContinue }
    else { $env:WIN_CSC_LINK = $previousWindowsCertLink }
}
