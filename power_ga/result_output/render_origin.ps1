# 结果输出模块的后台Origin原生渲染器：只负责画图、数据回读与工程交付。
param([Parameter(Mandatory=$true)][string]$SpecPath)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$spec=Get-Content -LiteralPath $SpecPath -Raw -Encoding UTF8 | ConvertFrom-Json
$folder=$spec.folder
$commands=[Collections.Generic.List[string]]::new()
$before=@(Get-Process Origin64 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$owned=@(); $app=$null; $gl=$null
$qa=@{renderer='Origin native'; visual_review='PENDING'; source='本次输入与绘图源数据'}

function LT([string]$command) {
    $commands.Add($command)
    if(-not $app.Execute($command)){throw "Origin拒绝命令: $command"}
}
function NumberText($value) { return ([double]$value).ToString('G17',[Globalization.CultureInfo]::InvariantCulture) }
# 刻度数字按人可读的十进制写入Origin；G17会把259.6展开成259.60000000000002。
function TickText($value) { return ([double]$value).ToString('0.##########',[Globalization.CultureInfo]::InvariantCulture) }
function RGB([string]$hex) {
    $r=[Convert]::ToInt32($hex.Substring(1,2),16)
    $g=[Convert]::ToInt32($hex.Substring(3,2),16)
    $b=[Convert]::ToInt32($hex.Substring(5,2),16)
    return "color($r,$g,$b)"
}

try {
    # Application创建独立COM实例；不连接用户现有Origin工程。
    $app=New-Object -ComObject Origin.Application
    $app.Visible=0
    $owned=@(Get-Process Origin64 -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $before } | Select-Object Id,StartTime)
    if($owned.Count -ne 1){throw '无法确认本任务独立Origin实例的归属'}
    $qa.origin_version=[string]$app.LTVar('@V')
    $qa.owned_pid=$owned[0].Id
    $book=$app.CreatePage(2,'FigureData','Origin')
    LT ('win -a {0};wks.ncols={1};wks.col1.type=4;' -f $book,$spec.columns.Count)
    $rows=@(Import-Csv -LiteralPath $spec.data -Encoding UTF8)
    $arrays=@()
    for($c=0;$c -lt $spec.columns.Count;$c++) {
        $column=$spec.columns[$c]
        [double[]]$values=@($rows | Where-Object { $_.$column -ne '' } | ForEach-Object { [double]::Parse($_.$column,[Globalization.CultureInfo]::InvariantCulture) })
        $arrays+=,$values
        if(-not $app.PutWorksheet("[$book]Sheet1",$values,0,$c)){throw "工作表写入失败: $column"}
    }
    # 回读原生工作表逐值比较，避免仅以导出成功作为数据正确的证据。
    $readback=$app.GetWorksheet("[$book]Sheet1")
    $qa.readback_shape=@($readback.GetLength(0),$readback.GetLength(1))
    $qa.readback_lower_bounds=@($readback.GetLowerBound(0),$readback.GetLowerBound(1))
    for($c=0;$c -lt $arrays.Count;$c++) {
        for($r=0;$r -lt $arrays[$c].Count;$r++) {
            $actual=[double]$readback.GetValue($r+$readback.GetLowerBound(0),$c+$readback.GetLowerBound(1))
            $expected=[double]$arrays[$c][$r]
            if([Math]::Abs($actual - $expected) -gt 1e-8){throw "工作表回读不匹配: $r,$c"}
        }
    }
    $qa.worksheet_readback='EXACT_MATCH'
    $graph=$app.CreatePage(3,'Figure','Origin')
    for($i=0;$i -lt $spec.plots.Count;$i++) {
        $plot=$spec.plots[$i]
        $range='[{0}]Sheet1!(1,{1})' -f $book,$plot.column
        if($plot.end_row){$range+='[1:{0}]' -f $plot.end_row}
        LT ('plotxy iy:={0} plot:=200 ogl:=[{1}]Layer1;' -f $range,$graph)
    }
    LT ('win -a {0};page.cntrl=16;page.kar=0;page.width=18/2.54*page.resx;page.height=11/2.54*page.resy;' -f $graph)
    LT 'layer.fixed=1;layer.unit=1;layer.left=13;layer.top=28;layer.width=83;layer.height=58;layer.clip=0;layer -b f 0;'
    $xmin=NumberText $spec.x_min; $xmax=NumberText $spec.x_max
    $ymin=NumberText $spec.y_min; $ymax=NumberText $spec.y_max
    LT "layer.x.from=$xmin;layer.x.to=$xmax;layer.y.from=$ymin;layer.y.to=$ymax;layer.x.rescale=1;layer.y.rescale=1;"
    foreach($axis in @('x','y')) {
        $tickValues=$spec."${axis}_ticks"
        if($axis -eq 'y' -and $spec.zero_once){$tickValues=@($tickValues | Where-Object { $_ -ne 0 })}
        $ticks=($tickValues | ForEach-Object { TickText $_ }) -join ' '
        # 每根轴的实际显示端点都包含在刻度列表；全部刻度仅向内。
        LT "layer.$axis.ticksbydata$=`"$ticks`";layer.$axis.ticks=1;layer.$axis.ticklength=4;layer.$axis.minorTicks=0;layer.$axis.opposite=0;layer.$axis.showopposite=0;layer.$axis.showaxes=1;layer.$axis.showlabels=1;layer.$axis.thickness=0.7;layer.$axis.label.pt=10;layer.$axis.label.font=font(Times New Roman);"
    }
    # 原点保留两轴刻度，只隐藏纵轴第一个0标签。
    if($spec.zero_once){LT 'layer.y.mticksbydata$="0";layer.y.ticks=5;layer.y.mticklength=4;'}
    LT 'layer.y.grid.show=1;'
    LT ('label -r legend;label -xb {0};xb.fsize=10;xb.font=font(SimSun);label -yl {1};yl.fsize=10;yl.font=font(SimSun);yl.rotate=90;' -f $spec.x_label,$spec.y_label)
    $gl=$app.FindGraphLayer("[$graph]Layer1")
    for($i=0;$i -lt $spec.plots.Count;$i++) {
        $plot=$spec.plots[$i]; $name=$gl.DataPlots.Item($i).Name
        $color=RGB $plot.color; $width=[double]$plot.width*500
        LT "set $name -l 1;set $name -k 0;set $name -w $width;"
        if($plot.fill) {
            # 边界线与填充同色；全年8760个阶梯边界不会形成密集黑刺。
            LT "set $name -c $color;set $name -pf 1;set $name -pfv 2;set $name -pfb $color;set $name -pfc 1;set $name -pfp $($plot.pattern);set $name -pfw 0.3;"
        } else { LT "set $name -pf 0;set $name -c $color;" }
    }
    # 每个条目用实际DataPlot样本，3列排在数据区外；显式归零文字旋转角度。
    for($i=0;$i -lt $spec.plots.Count;$i++) {
        $entry='LegendEntry'+($i+1)
        $text='\l({0}) \f:SimSun({1})' -f ($i+1),$spec.plots[$i].label
        $x=$spec.x_min+($spec.x_max-$spec.x_min)*(0.16+0.34*($i%3))
        $y=$spec.y_max+($spec.y_max-$spec.y_min)*(0.28-0.085*[Math]::Floor($i/3))
        LT ('label -p 50 10 -j 1 -n {0} {1};{0}.font=font(SimSun);{0}.fsize=9;{0}.rotate=0;{0}.x={2};{0}.y={3};' -f $entry,$text,(NumberText $x),(NumberText $y))
    }
    # 图题使用与已校验横排图例相同的label锚点10；锚点2会继承模板旋转。
    $titleText='\f:SimSun({0})' -f $spec.title
    LT ('label -p 50 10 -j 1 -n LegendEntryTitle {0};LegendEntryTitle.font=font(SimSun);LegendEntryTitle.fsize=12;LegendEntryTitle.rotate=0;LegendEntryTitle.x={1};LegendEntryTitle.y={2};' -f $titleText,(NumberText (($spec.x_min+$spec.x_max)/2)),(NumberText ($spec.y_max+($spec.y_max-$spec.y_min)*0.42)))
    # 较长的算法说明仅留在同图figure_spec.json，不在图内压缩显示。
    $qa.native_plot_count=$gl.DataPlots.Count
    $qa.axis_ranges=@{x=@($spec.x_min,$spec.x_max);y=@($spec.y_min,$spec.y_max)}
    foreach($ext in @('png','pdf')) {
        $extra=if($ext -eq 'png'){'tr2.png.dotsperinch:=600'}else{''}
        try {
            LT ('expGraph type:={0} path:="{1}" filename:="{2}" export:=specified pages:="{3}" sysopts:=0 tr.Margin:=2 tr1.unit:=1 tr1.width:=18 {4} overwrite:=replace;' -f $ext,(Join-Path $folder 'images'),$spec.name,$graph,$extra)
            if($ext -eq 'pdf'){$qa.pdf_export='Origin native'}
        } catch {
            if($ext -ne 'pdf'){throw}
            # 全年阶梯点+密集点阵有时使Origin的矢量PDF导出失败；
            # 仅PDF改用已核实的600dpi Origin PNG封装，OPJU与PNG仍是Origin原生结果。
            $png=Join-Path $folder ('images\'+$spec.name+'.png')
            $pdf=Join-Path $folder ('images\'+$spec.name+'.pdf')
            $helper=Join-Path $folder 'scripts\pdf_fallback.py'
            if($spec.frozen_executable){
                # 单文件EXE的sys.executable不是Python解释器；调用其内置PDF子命令，
                # 等进程退出后再验文件，避免GUI程序异步返回造成假成功。
                $arguments='--pdf-fallback "'+$png+'" "'+$pdf+'"'
                $fallback=Start-Process -FilePath $spec.python_executable -ArgumentList $arguments -PassThru -Wait -WindowStyle Hidden
                if($fallback.ExitCode -ne 0){throw '单文件应用PNG封装PDF失败'}
            } else {
                & $spec.python_executable $helper $png $pdf
                if($LASTEXITCODE -ne 0){throw 'Origin PDF失败，PNG封装PDF也失败'}
            }
            $qa.pdf_export='600dpi Origin PNG wrapped as raster PDF'
        }
        $file=Join-Path $folder ('images\'+$spec.name+'.'+$ext)
        if(-not (Test-Path -LiteralPath $file) -or (Get-Item -LiteralPath $file).Length -lt 1000){throw "导出失败: $file"}
    }
    $project=Join-Path $folder ($spec.name+'.opju')
    if(-not $app.Save($project)){throw 'Origin工程保存失败'}
    # 保存后重开同一独立工程，确认DataPlots仍可编辑且没有丢失。
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($gl);$gl=$null
    if(-not $app.Load($project)){throw 'Origin工程重开失败'}
    $gl=$app.FindGraphLayer("[$graph]Layer1")
    if($gl.DataPlots.Count -ne $spec.plots.Count){throw '重开工程后的曲线数量错误'}
    $qa.project_reopen='PASS';$qa.export_check='PASS';$qa.data_check='PASS'
    Write-Output ('已导出Origin图: '+$folder)
} finally {
    $commands | Set-Content -LiteralPath (Join-Path $folder 'scripts\commands.ogs') -Encoding UTF8
    $qa | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $folder 'qa\origin_report.json') -Encoding UTF8
    if($null -ne $gl){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($gl);$gl=$null}
    if($null -ne $app){
        if($owned.Count -eq 1){$app.IsModified=$false;[void]$app.Exit()}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app);$app=$null
    }
    [GC]::Collect();[GC]::WaitForPendingFinalizers()
    # 仅处理PID和创建时间均确认属于本任务的残留后台实例。
    foreach($item in $owned){
        $process=Get-Process -Id $item.Id -ErrorAction SilentlyContinue
        if($process -and $process.StartTime -eq $item.StartTime){
            try{Wait-Process -Id $item.Id -Timeout 3 -ErrorAction Stop}catch{
                $process=Get-Process -Id $item.Id -ErrorAction SilentlyContinue
                if($process -and $process.StartTime -eq $item.StartTime){$process.Kill()}
            }
        }
    }
}
