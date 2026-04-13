# win-install.ps1 — install comad-world scheduled jobs via Windows Task Scheduler.
#
# Each task invokes bun directly (no .sh shell needed). If claude -p needs
# ANTHROPIC_API_KEY on Windows (DPAPI from a non-interactive task may fail
# to unlock OAuth), set it in the user-level environment variables:
#   [Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY','sk-ant-…','User')
# before running this script. Tasks inherit the User environment.
#
# Usage (elevated PowerShell):
#   pwsh -File brain\scripts\win-install.ps1
#   pwsh -File brain\scripts\win-install.ps1 -Uninstall
#
# Test a single task:
#   Start-ScheduledTask -TaskName "Comad\EarDigest"

[CmdletBinding()]
param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$project = Join-Path $HOME "Programmer\01-comad\comad-world"
$bun = Join-Path $HOME ".bun\bin\bun.exe"
$node = "node"
$log = Join-Path $project "brain\crawl.log"
$digestLog = Join-Path $project "ear\digest.log"

$jobs = @(
    @{ Name="EarIngest";       Time="07:00"; Daily=$true;  Exe=$bun;  Args="run $project\brain\packages\search\src\ear-ingest.ts --since 1"; Log=$log },
    @{ Name="EarDigest";       Time="08:00"; Daily=$true;  Exe=$node; Args="$project\ear\generate-digest.js"; Log=$digestLog },
    @{ Name="CrawlArxiv";      Time="09:00"; Daily=$true;  Exe="zsh"; Args="$project\brain\scripts\crawl-arxiv.sh"; Log=$log },
    @{ Name="IngestGeeknews";  Time="09:30"; Daily=$true;  Exe="zsh"; Args="$project\brain\scripts\ingest-geeknews.sh"; Log=$log },
    @{ Name="CrawlBlogs";      Time="10:00"; Daily=$true;  Exe="zsh"; Args="$project\brain\scripts\crawl-blogs.sh"; Log=$log },
    @{ Name="CrawlGithub";     Time="11:00"; Daily=$false; Exe="zsh"; Args="$project\brain\scripts\crawl-github.sh"; Log=$log },
    @{ Name="MonitorUpstream"; Time="11:30"; Daily=$false; Exe="zsh"; Args="$project\brain\scripts\monitor-upstream.sh"; Log=$log },
    @{ Name="SearchWeekly";    Time="12:00"; Daily=$false; Exe="zsh"; Args="$project\brain\scripts\search-weekly.sh"; Log=$log },
    @{ Name="EvolutionLoop";   Time="12:30"; Daily=$false; Exe="zsh"; Args="$project\brain\scripts\evolution-loop.sh"; Log=$log },
    @{ Name="RunBenchmark";    Time="13:00"; Daily=$false; Exe="zsh"; Args="$project\brain\scripts\run-benchmark.sh"; Log=$log }
)

if ($Uninstall) {
    foreach ($j in $jobs) {
        $task = "Comad\$($j.Name)"
        if (Get-ScheduledTask -TaskName $j.Name -TaskPath "\Comad\" -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $j.Name -TaskPath "\Comad\" -Confirm:$false
            Write-Host "  - removed $task"
        }
    }
    Write-Host "Uninstall complete."
    return
}

foreach ($j in $jobs) {
    # Wrap the command so stdout/stderr go to the log (tasks don't redirect natively)
    $cmdLine = "`"$($j.Exe)`" $($j.Args) *>> `"$($j.Log)`""
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmdLine"

    if ($j.Daily) {
        $trigger = New-ScheduledTaskTrigger -Daily -At $j.Time
    } else {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $j.Time
    }

    # Run only when user is logged on so claude -p can reach the OAuth token.
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

    Register-ScheduledTask -TaskName $j.Name -TaskPath "\Comad\" `
        -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
        -Force | Out-Null

    Write-Host "  ✓ Comad\$($j.Name)  — $($j.Time) $(if($j.Daily){'daily'}else{'Mon'})"
}

Write-Host "`nInstalled $($jobs.Count) scheduled tasks under \Comad\."
Write-Host "View: Get-ScheduledTask -TaskPath '\Comad\*' | Format-Table TaskName,State,Triggers"
Write-Host "Test one: Start-ScheduledTask -TaskName EarDigest -TaskPath '\Comad\'"
