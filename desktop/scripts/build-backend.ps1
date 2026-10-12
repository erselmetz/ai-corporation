$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Create the repository Python environment first; the supported build Python is Python 3.14 x64."
}
& $python -m pip install --disable-pip-version-check --requirement (Join-Path $PSScriptRoot "..\requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not prepare the pinned Python packaging tool." }
$build = Join-Path $repo "desktop\build\pyinstaller"
$dist = Join-Path $repo "desktop\build\backend"
$rootPrefix = $repo.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($target in @($build, $dist)) {
    $absoluteTarget = [IO.Path]::GetFullPath($target)
    if (-not $absoluteTarget.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a build path outside the repository."
    }
}
if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
if (Test-Path -LiteralPath $dist) { Remove-Item -LiteralPath $dist -Recurse -Force }
& $python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $build (Join-Path $repo "desktop\erselmetz-backend.spec")
if ($LASTEXITCODE -ne 0) { throw "The Python backend package could not be built." }
