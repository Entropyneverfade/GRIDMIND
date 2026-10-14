# GRIDMIND应用打包入口；本文件只处理窗口与依赖，不修改算法模块。
param([string]$PythonPath = 'python', [switch]$CreateDesktopShortcut)
$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $app
$entry = Join-Path $app 'main.py'
$icon = Join-Path $app 'assets\gridmind.ico'
$costs = Join-Path $project 'input\project_costs.csv'
$syntheticCosts = Join-Path $project 'examples\synthetic_case_costs.csv'
$assetDir = Join-Path $app 'assets'
$renderer = Join-Path $project 'power_ga\result_output\render_origin.ps1'
foreach($path in @($entry, $icon, $costs, $syntheticCosts, $renderer)) {
    if(-not (Test-Path -LiteralPath $path)) { throw "缺少打包输入：$path" }
}
# --onefile交付单个EXE；内置默认成本表只用于首次复制，用户更改保存在EXE旁。
& $PythonPath -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name GRIDMIND --icon $icon `
    --paths $project `
    --add-data "${costs};input" `
    --add-data "${syntheticCosts};examples" `
    --add-data "${assetDir};gridmind_app/assets" `
    --add-data "${renderer};power_ga/result_output" `
    --hidden-import power_ga.result_output.viewer `
    --hidden-import power_ga.result_output.python_plot `
    --hidden-import power_ga.dynamic_planning.solver `
    --hidden-import power_ga.result_output.dynamic_report `
    --hidden-import power_ga.operation_simulation.network_case `
    --hidden-import examples.synthetic_dynamic_case `
    --hidden-import examples.synthetic_network_case `
    --collect-all gurobipy `
    --hidden-import matplotlib.backends.backend_tkagg `
    --hidden-import matplotlib.backends.backend_pdf `
    --distpath (Join-Path $app 'dist') `
    --workpath (Join-Path $app 'build_cache') `
    --specpath $app $entry
if($LASTEXITCODE -ne 0) { throw 'PyInstaller打包失败' }
# 根目录只交付一个正式EXE；打包缓存仍隔离在应用开发文件夹。
$built = Join-Path $app 'dist\GRIDMIND.exe'
$delivery = Join-Path $project 'GRIDMIND.exe'
$shortcutTarget = $delivery
try {
    Copy-Item -LiteralPath $built -Destination $delivery -Force
    Write-Output $delivery
} catch [System.IO.IOException] {
    # 已打开的旧版不得强制终止；此时新版留在应用子目录，避免根目录出现双版本。
    $shortcutTarget = $built
    Write-Warning "根目录EXE仍被占用；新版位于 $built，旧窗口关闭后可重新构建替换"
    Write-Output $built
}
if($CreateDesktopShortcut) {
    # 使用系统桌面路径，快捷方式始终指向本次可运行的新版并继承其原创图标。
    $desktop = [Environment]::GetFolderPath('Desktop')
    $linkPath = Join-Path $desktop 'GRIDMIND.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($linkPath)
    $link.TargetPath = $shortcutTarget
    $link.WorkingDirectory = Split-Path -Parent $shortcutTarget
    $link.IconLocation = "$shortcutTarget,0"
    $link.Description = 'GRIDMIND 电源规划与8760小时运行模拟'
    $link.Save()
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($link) | Out-Null
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) | Out-Null
    Write-Output $linkPath
}
