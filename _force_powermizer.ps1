$ErrorActionPreference = "Stop"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $prin = New-Object Security.Principal.WindowsPrincipal($id)
    return $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Output "Elevating to Administrator..."
    $self = $MyInvocation.MyCommand.Path
    Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $self
    )
    exit $LASTEXITCODE
}

$base = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
$edited = $false

Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {
    $path = $_.PSPath
    try {
        $props = Get-ItemProperty -Path $path -ErrorAction Stop
    } catch {
        return
    }
    $desc = [string]$props.DriverDesc
    if ($desc -notmatch "1080\s*Ti") {
        return
    }
    Write-Output "Editing: $desc ($($_.PSChildName))"
    New-ItemProperty -Path $path -Name "PowerMizerEnable" -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $path -Name "PowerMizerLevel" -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $path -Name "PowerMizerLevelAC" -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $path -Name "PerfLevelSrc" -PropertyType DWord -Value 0x2222 -Force | Out-Null
    New-ItemProperty -Path $path -Name "EnableUlps" -PropertyType DWord -Value 0 -Force | Out-Null
    $check = Get-ItemProperty -Path $path
    Write-Output ("PowerMizerEnable=" + $check.PowerMizerEnable)
    Write-Output ("PowerMizerLevel=" + $check.PowerMizerLevel)
    Write-Output ("PowerMizerLevelAC=" + $check.PowerMizerLevelAC)
    Write-Output ("PerfLevelSrc=0x{0:X}" -f [int]$check.PerfLevelSrc)
    Write-Output ("EnableUlps=" + $check.EnableUlps)
    if ([int]$check.PowerMizerEnable -ne 1 -or [int]$check.PerfLevelSrc -ne 0x2222) {
        throw "Registry write did not stick."
    }
    $edited = $true
}

if (-not $edited) {
    Write-Output "ERROR: GTX 1080 Ti registry key not found."
    pause
    exit 2
}

Write-Output ""
Write-Output "OK: PowerMizer written."
Write-Output "Now REBOOT Windows, then run a review and check nvidia-smi clocks."
Write-Output "Target during generation: ~1600MHz, 100W+, pstate P2/P0"
pause
exit 0
