# Keep GTX 1080 Ti out of Idle P-state while Ollama/CUDA runs under WDDM.
# Must run in STA. START.bat / GPU_WAKE.bat pass -STA.
param()

$ErrorActionPreference = "Continue"
$logPath = Join-Path $PSScriptRoot "logs\gpu_wake.log"
try {
    New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null
    Add-Content -Path $logPath -Value ("[{0}] start pid={1} apartment={2}" -f (Get-Date -Format o), $PID, [Threading.Thread]::CurrentThread.GetApartmentState())
} catch {}

try {
    if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne "STA") {
        # Re-launch self in STA if somehow started without -STA.
        $self = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-STA", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $self
        ) | Out-Null
        exit 0
    }

    Add-Type -AssemblyName PresentationCore, PresentationFramework, WindowsBase

    $window = New-Object System.Windows.Window
    $window.Title = "GPU Wake - leave open during LLM"
    $window.Width = 460
    $window.Height = 200
    $window.Topmost = $true
    $window.ShowInTaskbar = $true
    $window.WindowStartupLocation = "CenterScreen"
    $window.WindowStyle = "SingleBorderWindow"
    $window.ResizeMode = "CanMinimize"
    $window.Background = [System.Windows.Media.Brushes]::Black

    $text = New-Object System.Windows.Controls.TextBlock
    $text.FontSize = 18
    $text.Foreground = [System.Windows.Media.Brushes]::Lime
    $text.HorizontalAlignment = "Center"
    $text.VerticalAlignment = "Center"
    $text.TextWrapping = "Wrap"
    $text.TextAlignment = "Center"
    $text.Margin = New-Object System.Windows.Thickness(12)
    $text.Text = "GPU wake starting...`r`nLeave this window open while review runs."
    $window.Content = $text

    $script:tick = 0
    $script:allowClose = $false

    $window.Add_Closing({
        param($sender, $e)
        if ($script:allowClose) { return }
        $answer = [System.Windows.MessageBox]::Show(
            "Close GPU Wake? Clocks may drop back to ~700MHz during LLM.",
            "GPU Wake",
            [System.Windows.MessageBoxButton]::YesNo,
            [System.Windows.MessageBoxImage]::Warning
        )
        if ($answer -ne [System.Windows.MessageBoxResult]::Yes) {
            $e.Cancel = $true
        } else {
            $script:allowClose = $true
        }
    })

    $timer = New-Object System.Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromMilliseconds(16)
    $timer.Add_Tick({
        try {
            $script:tick++
            $hue = [byte]($script:tick % 255)
            $text.Text = ("GPU wake #{0}`r`nLeave open while Streamlit/Ollama review runs`r`nClose only when finished" -f $script:tick)
            $brush = New-Object System.Windows.Media.SolidColorBrush
            $brush.Color = [System.Windows.Media.Color]::FromRgb($hue, 220, [byte](255 - $hue))
            $text.Foreground = $brush
        } catch {
            # Never let a tick crash the window.
        }
    })
    $timer.Start()

    Add-Content -Path $logPath -Value ("[{0}] show dialog" -f (Get-Date -Format o)) -ErrorAction SilentlyContinue
    [void]$window.ShowDialog()
    Add-Content -Path $logPath -Value ("[{0}] closed" -f (Get-Date -Format o)) -ErrorAction SilentlyContinue
    exit 0
} catch {
    $msg = $_.Exception.Message
    try { Add-Content -Path $logPath -Value ("[{0}] FATAL {1}" -f (Get-Date -Format o), $msg) } catch {}
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show("GPU Wake failed:`r`n$msg", "GPU Wake") | Out-Null
    } catch {}
    exit 1
}
