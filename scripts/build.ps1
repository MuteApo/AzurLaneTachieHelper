param(
    [string]$OutputDirectory = '.artifacts/nuitka',
    [ValidateRange(1, 64)]
    [int]$Jobs = 4
)

$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    uv run --locked --no-dev --group build pyside6-lrelease `
        src/ui/translations/zh_CN.ts -qm src/ui/translations/zh_CN.qm
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    uv run --locked --no-dev --group build python -m nuitka src/main.py `
        --mode=standalone `
        --msvc=latest `
        --clang `
        --jobs=$Jobs `
        --lto=no `
        --python-flag=no_docstrings `
        --assume-yes-for-downloads `
        --enable-plugin=pyside6 `
        --noinclude-qt-plugins=platforms,imageformats,iconengines,styles,tls `
        --nofollow-import-to=tkinter `
        --windows-console-mode=disable `
        --windows-icon-from-ico=cheshire.ico `
        --user-package-configuration-file=scripts/nuitka-package.config.yml `
        --output-dir=$OutputDirectory `
        --output-filename=AzurLaneTachieHelper.exe `
        --report=$OutputDirectory/report.xml
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
