# GRIDMIND应用打包入口；本文件只处理窗口与依赖，不修改算法模块。
param([string]$PythonPath = 'python')
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
    --hidden-import power_ga.dynamic_planning.solver `
    --hidden-import power_ga.result_output.dynamic_report `
    --hidden-import examples.synthetic_dynamic_case `
    --collect-all gurobipy `
    --hidden-import matplotlib.backends.backend_tkagg `
    --distpath (Join-Path $app 'dist') `
    --workpath (Join-Path $app 'build_cache') `
    --specpath $app $entry
if($LASTEXITCODE -ne 0) { throw 'PyInstaller打包失败' }
# 根目录放用户可直接双击的正式EXE；打包缓存仍隔离在应用开发文件夹。
$built = Join-Path $app 'dist\GRIDMIND.exe'
$delivery = Join-Path $project 'GRIDMIND.exe'
try {
    Copy-Item -LiteralPath $built -Destination $delivery -Force
    Write-Output $delivery
} catch [System.IO.IOException] {
    # 用户若正在使用旧EXE，保留其窗口；完整新版已在独立dist目录等待替换。
    Write-Warning "根目录EXE仍在运行，保留旧文件；新版位于 $built"
    Write-Output $built
}
