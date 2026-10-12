$ErrorActionPreference = "Stop"
$previousAutoDiscovery = $env:CSC_IDENTITY_AUTO_DISCOVERY
$previousCertLink = $env:CSC_LINK
$previousWindowsCertLink = $env:WIN_CSC_LINK
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
Remove-Item Env:CSC_LINK -ErrorAction SilentlyContinue
Remove-Item Env:WIN_CSC_LINK -ErrorAction SilentlyContinue
try {
    & (Join-Path $PSScriptRoot "..\node_modules\.bin\electron-builder.cmd") --win nsis --x64
    if ($LASTEXITCODE -ne 0) { throw "The unsigned local Windows installer could not be built." }
} finally {
    if ($null -eq $previousAutoDiscovery) { Remove-Item Env:CSC_IDENTITY_AUTO_DISCOVERY -ErrorAction SilentlyContinue }
    else { $env:CSC_IDENTITY_AUTO_DISCOVERY = $previousAutoDiscovery }
    if ($null -eq $previousCertLink) { Remove-Item Env:CSC_LINK -ErrorAction SilentlyContinue }
    else { $env:CSC_LINK = $previousCertLink }
    if ($null -eq $previousWindowsCertLink) { Remove-Item Env:WIN_CSC_LINK -ErrorAction SilentlyContinue }
    else { $env:WIN_CSC_LINK = $previousWindowsCertLink }
}
