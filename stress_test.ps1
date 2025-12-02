# stress_test.ps1 - Spawn 100 RTSP clients
param (
    [string]$HostName = "localhost"
)

$PORT = 8554
$COUNT = 100

Write-Host "Starting stress test against $HostName`:$PORT with $COUNT clients..." -ForegroundColor Cyan

# Ensure ffmpeg is installed
if (-not (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: ffmpeg is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

$jobs = @()

for ($i = 1; $i -le $COUNT; $i++) {
    $URL = "rtsp://$HostName`:$PORT/cam$i"
    Write-Host "Starting client $i on $URL..."

    # Start ffmpeg in background
    # -vcodec copy: No decoding
    # -f null -: Discard output
    # -rtsp_transport tcp: Force TCP
    $jobs += Start-Process -FilePath "ffmpeg" -ArgumentList "-rtsp_transport tcp -i $URL -vcodec copy -f null -" -PassThru -NoNewWindow
}

Write-Host "All $COUNT clients started." -ForegroundColor Green
Write-Host "Press any key to stop all clients..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host "Stopping clients..." -ForegroundColor Yellow
foreach ($job in $jobs) {
    Stop-Process -Id $job.Id -ErrorAction SilentlyContinue
}
Write-Host "Done." -ForegroundColor Green
