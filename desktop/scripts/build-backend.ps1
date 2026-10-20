$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Create the repository Python environment first; the supported build Python is Python 3.14 x64."
}
& $python -m pip install --disable-pip-version-check --requirement (Join-Path $PSScriptRoot "..\requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not prepare the pinned Python packaging tool." }
$configuredRoot = $env:ERSELMETZ_BUILD_OUTPUT_ROOT
$buildRoot = if ([string]::IsNullOrWhiteSpace($configuredRoot)) {
    Join-Path $repo "desktop\build"
} elseif ([IO.Path]::IsPathRooted($configuredRoot)) {
    [IO.Path]::GetFullPath($configuredRoot)
} else {
    [IO.Path]::GetFullPath((Join-Path $repo $configuredRoot))
}
$build = Join-Path $buildRoot "pyinstaller"
$dist = Join-Path $buildRoot "backend"
$rootPrefix = $repo.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($target in @($buildRoot, $build, $dist)) {
    $absoluteTarget = [IO.Path]::GetFullPath($target)
    if (-not $absoluteTarget.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a build path outside the repository."
    }
}
if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
if (Test-Path -LiteralPath $dist) { Remove-Item -LiteralPath $dist -Recurse -Force }
& $python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $build (Join-Path $repo "desktop\erselmetz-backend.spec")
if ($LASTEXITCODE -ne 0) { throw "The Python backend package could not be built." }
$package = Get-Content -LiteralPath (Join-Path $repo "desktop\package.json") -Raw | ConvertFrom-Json
$commit = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-fA-F]{40}$') { throw "Could not identify the backend source commit." }
$stamp = @{ version = $package.version; commit = $commit.ToLowerInvariant() } | ConvertTo-Json -Compress
$stampPath = Join-Path $dist "erselmetz-backend\build-stamp.json"
[IO.File]::WriteAllText($stampPath, $stamp, [Text.UTF8Encoding]::new($false))
