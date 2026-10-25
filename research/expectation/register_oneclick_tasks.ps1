<#
.SYNOPSIS
  Register PT one-click scheduled tasks (run once as Administrator).

.DESCRIPTION
  Creates two weekly tasks (Mon-Fri):
    PT-OneClick-AfterClose 16:30 -> task_after_close.cmd (fallback, --skip-if-done)
    PT-OneClick-Premarket  09:00 -> task_premarket.cmd  (verify/rerun + pre-upload hard check)

  Both run as the current logged-on user (Interactive: PTrade client must be logged in
  for position sync), StartWhenAvailable = catch up after sleep/shutdown.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File register_oneclick_tasks.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File register_oneclick_tasks.ps1
#>
param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$me).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin -and -not $DryRun) {
    Write-Host "[FAIL] Administrator required: open PowerShell as Administrator and re-run this script." -ForegroundColor Red
    Write-Host "       Use -DryRun to preview without registering (works as normal user)."
    exit 1
}

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # ...\PROJ\PT
$defs = @(
    [pscustomobject]@{
        Name = 'PT-OneClick-AfterClose'
        Cmd  = Join-Path $root 'research\expectation\task_after_close.cmd'
        At   = '16:30'
        Desc = 'PT after-close one-click fallback (--skip-if-done; review chain runs it first)'
    },
    [pscustomobject]@{
        Name = 'PT-OneClick-Premarket'
        Cmd  = Join-Path $root 'research\expectation\task_premarket.cmd'
        At   = '09:00'
        Desc = 'PT premarket one-click: verify/rerun + pre-upload hard check (upload before 09:15)'
    }
)

$user = "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

foreach ($d in $defs) {
    if (-not (Test-Path -LiteralPath $d.Cmd)) {
        Write-Host ("[FAIL] missing entry script: " + $d.Cmd) -ForegroundColor Red
        exit 2
    }
    if ($DryRun) {
        Write-Host ("[dry-run] " + $d.Name + " | Mon-Fri " + $d.At + " | cmd /c `"" + $d.Cmd + "`" | user=" + $user)
        continue
    }
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "' + $d.Cmd + '"')
    $trigger = New-ScheduledTaskTrigger -Weekly `
        -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $d.At
    Register-ScheduledTask -TaskName $d.Name -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description $d.Desc -Force | Out-Null
    $task = Get-ScheduledTask -TaskName $d.Name
    $info = $task | Get-ScheduledTaskInfo
    Write-Host ("[OK] " + $d.Name + " | State=" + $task.State + " | Next=" + $info.NextRunTime)
}

if ($DryRun) {
    Write-Host "[dry-run] nothing registered; drop -DryRun and run as Administrator to register."
} else {
    Write-Host ""
    Write-Host "[done] check: Get-ScheduledTask -TaskName 'PT-OneClick-*' | Get-ScheduledTaskInfo"
    Write-Host ("       logs : " + $root + "\Logs\oneclick_after_close.log / oneclick_premarket.log")
}
