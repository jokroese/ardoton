param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "restore", "status")]
    [string]$Command = "status"
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Latin1 = [Text.Encoding]::GetEncoding(28591)

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $InstallerDir
$ProfileDir = Join-Path $RepoDir "profile"
$ConfigDir = if ($env:ARDOURTON_CONFIG_DIR) {
    $env:ARDOURTON_CONFIG_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Ardour9"
}
$StateDir = Join-Path $ConfigDir "ardourton"
$ReceiptFile = Join-Path $StateDir "receipt"
$BackupRoot = Join-Path $StateDir "backups"

$ScriptNames = @(
    "ardourton_add_audio_track.lua",
    "ardourton_add_midi_track.lua",
    "ardourton_add_return.lua",
    "ardourton_set_loop.lua",
    "ardourton_duplicate_tracks.lua",
    "ardourton_beat_production.lua"
)

$Targets = @(
    "ardour.keys",
    "ui_config",
    "ui_scripts",
    "themes/ardourton-ardour.colors"
) + ($ScriptNames | ForEach-Object { "scripts/$_" })

function Stop-WithError([string]$Message) {
    throw "Ardourton: $Message"
}

function Assert-ArdourClosed {
    if ($env:ARDOURTON_SKIP_PROCESS_CHECK -eq "1") {
        return
    }
    if (Get-Process -Name "Ardour9" -ErrorAction SilentlyContinue) {
        Stop-WithError "Quit Ardour before continuing."
    }
}

function Assert-SupportedVersion {
    if ($env:ARDOURTON_SKIP_VERSION_CHECK -eq "1") {
        return
    }

    $Candidates = @(
        (Join-Path $env:ProgramFiles "Ardour9\bin\Ardour9.exe"),
        (Join-Path $env:ProgramFiles "Ardour9\Ardour9.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Ardour9\bin\Ardour9.exe")
    )
    $Executable = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Executable) {
        Stop-WithError "Ardour 9 was not found."
    }

    $VersionOutput = (& $Executable --version 2>&1 | Out-String)
    if ($VersionOutput -notmatch "Ardour9\.7\.") {
        Stop-WithError "This profile supports Ardour 9.7. Detected: $VersionOutput"
    }
}

function New-ProfileBackup {
    $BackupId = "$([DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ"))-$PID"
    $BackupDir = Join-Path $BackupRoot $BackupId
    $FilesDir = Join-Path $BackupDir "files"
    $Manifest = Join-Path $BackupDir "manifest.tsv"
    New-Item -ItemType Directory -Force -Path $FilesDir | Out-Null

    $Rows = foreach ($Target in $Targets) {
        $Source = Join-Path $ConfigDir $Target
        $Destination = Join-Path $FilesDir $Target
        if (Test-Path $Source) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
            Copy-Item -LiteralPath $Source -Destination $Destination
            "existing`t$Target"
        } else {
            "absent`t$Target"
        }
    }
    [IO.File]::WriteAllLines($Manifest, [string[]]$Rows, $Utf8NoBom)
    return $BackupDir
}

function Install-UiOptions {
    $UiConfig = Join-Path $ConfigDir "ui_config"
    if (Test-Path $UiConfig) {
        [xml]$Xml = Get-Content -LiteralPath $UiConfig -Raw
    } else {
        [xml]$Xml = '<?xml version="1.0" encoding="UTF-8"?><Ardour><UI/><Canvas/></Ardour>'
    }

    $UiNode = $Xml.SelectSingleNode("/Ardour/UI")
    if (-not $UiNode) {
        Stop-WithError "Could not find the UI section in ui_config."
    }

    $OptionsPath = Join-Path $ProfileDir "preferences\ui-options.tsv"
    foreach ($Line in Get-Content -LiteralPath $OptionsPath) {
        if (-not $Line.Trim()) {
            continue
        }
        $Name, $Value = $Line -split "`t", 2
        $Option = $UiNode.SelectSingleNode("Option[@name='$Name']")
        if (-not $Option) {
            $Option = $Xml.CreateElement("Option")
            $Option.SetAttribute("name", $Name)
            [void]$UiNode.AppendChild($Option)
        }
        $Option.SetAttribute("value", $Value)
    }

    $Xml.Save($UiConfig)
}

function Install-UiScripts {
    $UiScripts = Join-Path $ConfigDir "ui_scripts"
    if (Test-Path $UiScripts) {
        [xml]$Xml = Get-Content -LiteralPath $UiScripts -Raw
    } else {
        [xml]$Xml = '<?xml version="1.0" encoding="UTF-8"?><UIScripts><ActionScript lua="Lua 5.3"></ActionScript><ActionHooks/></UIScripts>'
    }

    $ActionNode = $Xml.SelectSingleNode("/UIScripts/ActionScript")
    if (-not $ActionNode) {
        Stop-WithError "Could not find ActionScript in ui_scripts."
    }

    $State = if ($ActionNode.InnerText) {
        $Latin1.GetString([Convert]::FromBase64String($ActionNode.InnerText))
    } else {
        "scripts = {}"
    }

    if ($State -notmatch "Ardourton: Add Stereo Audio Track") {
        $FragmentPath = Join-Path $ProfileDir "ui-scripts\ardourton-actions.lua-state"
        $Fragment = $Latin1.GetString([IO.File]::ReadAllBytes($FragmentPath))
        $State = $State + "`n" + $Fragment
    }

    $ActionNode.InnerText = [Convert]::ToBase64String($Latin1.GetBytes($State))
    $Xml.Save($UiScripts)
}

function Install-Profile {
    Assert-ArdourClosed
    Assert-SupportedVersion
    if (Test-Path $ReceiptFile) {
        Stop-WithError "Ardourton is already installed. Restore it first."
    }

    New-Item -ItemType Directory -Force -Path $ConfigDir, $StateDir, $BackupRoot | Out-Null
    $BackupDir = New-ProfileBackup

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $ConfigDir "themes"), `
        (Join-Path $ConfigDir "scripts") | Out-Null

    Copy-Item `
        (Join-Path $ProfileDir "keybindings\windows\ardour.keys") `
        (Join-Path $ConfigDir "ardour.keys")
    Copy-Item `
        (Join-Path $ProfileDir "theme\ardourton-ardour.colors") `
        (Join-Path $ConfigDir "themes\ardourton-ardour.colors")

    foreach ($ScriptName in $ScriptNames) {
        Copy-Item `
            (Join-Path $ProfileDir "scripts\$ScriptName") `
            (Join-Path $ConfigDir "scripts\$ScriptName")
    }

    Install-UiOptions
    Install-UiScripts

    $Receipt = @(
        "version=0.2.1",
        "backup=$BackupDir"
    )
    [IO.File]::WriteAllLines($ReceiptFile, [string[]]$Receipt, $Utf8NoBom)

    Write-Host "Ardourton installed."
    Write-Host "Backup: $BackupDir"
    Write-Host "Restart Ardour to load the profile."
}

function Restore-Profile {
    Assert-ArdourClosed
    if (-not (Test-Path $ReceiptFile)) {
        Stop-WithError "No Ardourton installation receipt was found."
    }

    $BackupDir = (Get-Content -LiteralPath $ReceiptFile |
        Where-Object { $_ -like "backup=*" }) -replace "^backup=", ""
    $Manifest = Join-Path $BackupDir "manifest.tsv"
    if (-not (Test-Path $Manifest)) {
        Stop-WithError "The recorded backup is missing."
    }

    foreach ($Line in Get-Content -LiteralPath $Manifest) {
        $State, $Target = $Line -split "`t", 2
        $Destination = Join-Path $ConfigDir $Target
        Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        if ($State -eq "existing") {
            $Source = Join-Path (Join-Path $BackupDir "files") $Target
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
            Copy-Item -LiteralPath $Source -Destination $Destination
        }
    }

    Remove-Item -LiteralPath $ReceiptFile -Force
    Write-Host "Ardourton restored the pre-install configuration."
    Write-Host "Backup retained at: $BackupDir"
}

function Show-Status {
    if (Test-Path $ReceiptFile) {
        Write-Host "Ardourton is installed in $ConfigDir."
    } else {
        Write-Host "Ardourton is not installed in $ConfigDir."
    }
}

switch ($Command) {
    "install" { Install-Profile }
    "restore" { Restore-Profile }
    "status" { Show-Status }
}
