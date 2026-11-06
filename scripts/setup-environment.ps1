param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$script:ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$script:Mirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'
# Python 3.12 的最后一个官方 Windows 完整安装包；不使用缺少 venv/pip 的嵌入版。
# https://www.python.org/downloads/release/python-31210/
$script:PythonVersion = '3.12.10'

function ConvertTo-ProcessArgument([string]$Value) {
    # Windows 原生命令行：引号前的反斜杠和末尾反斜杠需要加倍。
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Invoke-ProcessCapture([string]$Executable, [string[]]$Arguments, [int]$TimeoutSeconds = 15) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.Arguments = ($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join ' '
    $info.WorkingDirectory = $script:ProjectRoot
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [Text.Encoding]::UTF8
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            throw '检查 Python 超时，已停止本次检查。'
        }
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdout.GetAwaiter().GetResult()
            Stderr = $stderr.GetAwaiter().GetResult()
        }
    } finally {
        $process.Dispose()
    }
}

function Get-PythonInfo([string]$Executable) {
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    # 跳过会打开商店的执行别名，不在探测过程中触发安装。
    if ($Executable -match '\\Microsoft\\WindowsApps\\') { return $null }
    $probe = @'
import sys, struct, json, platform
assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8
assert platform.machine().lower() in ('amd64', 'x86_64')
import venv, ensurepip, ssl, sqlite3, ctypes
print(json.dumps({'executable':sys.executable,'version':platform.python_version(),'is_venv':sys.prefix != sys.base_prefix,'base_executable':getattr(sys,'_base_executable',sys.executable)}))
'@
    try {
        $result = Invoke-ProcessCapture $Executable @('-I', '-B', '-c', $probe)
        if ($result.ExitCode -eq 0) { return ($result.Stdout | ConvertFrom-Json) }
    } catch {
        # 一个候选不可运行时继续查找；不会启动它的安装器或改动配置。
    }
    return $null
}

function Find-BasePython {
    $candidates = New-Object 'Collections.Generic.List[string]'
    $candidates.Add((Join-Path $script:ProjectRoot '.runtime\python312\python.exe'))
    $venvConfig = Join-Path $script:ProjectRoot 'backend\.venv\pyvenv.cfg'
    if (Test-Path -LiteralPath $venvConfig -PathType Leaf) {
        $config = Get-Content -LiteralPath $venvConfig -Raw
        if ($config -match '(?m)^executable\s*=\s*(.+?)\s*$') { $candidates.Add($Matches[1]) }
    }
    foreach ($name in @('python.exe', 'python3.exe', 'python3.12.exe')) {
        foreach ($command in @(Get-Command $name -All -CommandType Application -ErrorAction SilentlyContinue)) {
            $candidates.Add($command.Source)
        }
    }
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($launcher -and $launcher.Source -notmatch '\\Microsoft\\WindowsApps\\') {
        try {
            $listed = Invoke-ProcessCapture $launcher.Source @('-0p')
            foreach ($line in ($listed.Stdout -split '\r?\n')) {
                if ($line -match '([A-Za-z]:\\.+?python\.exe)\s*$') { $candidates.Add($Matches[1]) }
            }
        } catch { }
    }
    foreach ($registryRoot in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        foreach ($versionKey in @(Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue)) {
            $installPath = Get-Item -LiteralPath ($versionKey.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
            if ($installPath) {
                $registeredExe = $installPath.GetValue('ExecutablePath')
                if ($registeredExe) { $candidates.Add([string]$registeredExe) }
                $directory = $installPath.GetValue('')
                if ($directory) { $candidates.Add((Join-Path $directory 'python.exe')) }
            }
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $info = Get-PythonInfo $candidate
        if ($info -and $info.is_venv) { $info = Get-PythonInfo $info.base_executable }
        if ($info -and -not $info.is_venv) { return $info }
    }
    return $null
}

function Test-PythonInstaller([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    return ($signature.Status -eq 'Valid' -and
        $signature.SignerCertificate.Subject -match 'O=Python Software Foundation(?:,|$)')
}

function Install-ProjectPython {
    $runtime = Join-Path $script:ProjectRoot '.runtime'
    $target = Join-Path $runtime 'python312'
    $downloads = Join-Path $runtime 'downloads'
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    $installer = Join-Path $downloads "python-$script:PythonVersion-amd64.exe"
    $url = "https://www.python.org/ftp/python/$script:PythonVersion/python-$script:PythonVersion-amd64.exe"
    if (-not (Test-PythonInstaller $installer)) {
        Write-Host "未找到合适的 Python，正在从 Python 官网下载 $script:PythonVersion（64 位）……"
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $partial = $installer + '.part'
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                $oldProgress = $ProgressPreference
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $partial -TimeoutSec 120
                if (-not (Test-PythonInstaller $partial)) { throw '下载文件的 Python 官方数字签名校验未通过。' }
                Move-Item -LiteralPath $partial -Destination $installer -Force
                break
            } catch {
                if ($attempt -eq 3) { throw "Python 下载失败：$($_.Exception.Message) 请检查能否访问 www.python.org 后重试。" }
                Write-Host "下载未完成，正在重试（$attempt/3）……" -ForegroundColor Yellow
            } finally {
                $ProgressPreference = $oldProgress
                if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
            }
        }
    }
    Write-Host "正在把 Python 安装到：$target"
    $log = Join-Path $runtime 'python-install.log'
    $arguments = @('/quiet', '/norestart', '/log', $log, 'InstallAllUsers=0', "TargetDir=$target",
        'PrependPath=0', 'AppendPath=0', 'Include_launcher=0', 'InstallLauncherAllUsers=0',
        'AssociateFiles=0', 'Shortcuts=0', 'Include_pip=1', 'Include_test=0', 'Include_doc=0',
        'Include_tcltk=0', 'Include_tools=0')
    $argumentLine = ($arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join ' '
    $installed = Start-Process -FilePath $installer -ArgumentList $argumentLine -Wait -PassThru -WindowStyle Hidden
    if ($installed.ExitCode -notin @(0, 3010)) { throw "Python 安装失败（代码 $($installed.ExitCode)），详情见 $log" }
    $info = Get-PythonInfo (Join-Path $target 'python.exe')
    if (-not $info) { throw "Python 安装后检查未通过。请查看 $log；如果安装器要求重启，请重启电脑后再运行本脚本。" }
    return $info
}

function Invoke-PythonCommand([string]$Python, [string[]]$Arguments) {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python 命令未成功（退出代码 $LASTEXITCODE），请查看上方错误。" }
}

function Initialize-ProjectVenv([string]$BasePython) {
    $venv = Join-Path $script:ProjectRoot 'backend\.venv'
    $backup = $null
    if (Test-Path -LiteralPath $venv) {
        $backup = $venv + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
        # 只移动本项目中这个确切目录；保留原环境和 pip.ini，不自动删除。
        if ((Split-Path -Parent ([IO.Path]::GetFullPath($venv))) -ne (Join-Path $script:ProjectRoot 'backend') -or
            (Split-Path -Parent ([IO.Path]::GetFullPath($backup))) -ne (Join-Path $script:ProjectRoot 'backend') -or
            ((Get-Item -LiteralPath $venv).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '虚拟环境备份路径检查失败。'
        }
        Move-Item -LiteralPath $venv -Destination $backup
        Write-Host "原环境不可用，已保留备份：$backup" -ForegroundColor Yellow
    }
    try {
        Invoke-PythonCommand $BasePython @('-m', 'venv', $venv)
        $python = Join-Path $venv 'Scripts\python.exe'
        $info = Get-PythonInfo $python
        if (-not $info -or -not $info.is_venv) { throw '新虚拟环境检查未通过。' }
        if ($backup -and (Test-Path -LiteralPath (Join-Path $backup 'pip.ini'))) {
            Copy-Item -LiteralPath (Join-Path $backup 'pip.ini') -Destination (Join-Path $venv 'pip.ini')
        }
        return $backup
    } catch {
        if ($backup) {
            if (Test-Path -LiteralPath $venv) {
                $failed = $venv + '.failed-' + [guid]::NewGuid().ToString('N')
                if ((Split-Path -Parent ([IO.Path]::GetFullPath($failed))) -ne (Join-Path $script:ProjectRoot 'backend')) {
                    throw '虚拟环境恢复路径检查失败。'
                }
                Move-Item -LiteralPath $venv -Destination $failed
            }
            Move-Item -LiteralPath $backup -Destination $venv
            Write-Host '创建失败，原虚拟环境已经放回原位置。' -ForegroundColor Yellow
        }
        throw
    }
}

function Invoke-EnvironmentSetup([switch]$InspectOnly) {
    Write-Host '灵栖环境配置：请保持联网。首次安装需要下载 Python（如有必要）和依赖。' -ForegroundColor Cyan
    if (-not [Environment]::Is64BitOperatingSystem) { throw '本项目需要 64 位 Windows 和 64 位 Python 3.12。' }
    $requirements = Join-Path $script:ProjectRoot 'backend\requirements.txt'
    if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) { throw '找不到 backend\requirements.txt，请先完整解压项目，再运行此脚本。' }
    $python = Join-Path $script:ProjectRoot 'backend\.venv\Scripts\python.exe'
    Write-Host '[1/4] 检查 64 位 Python 3.12 和现有虚拟环境……'
    $venvInfo = Get-PythonInfo $python
    if ($venvInfo -and -not $venvInfo.is_venv) { $venvInfo = $null }
    $baseInfo = $null
    if (-not $venvInfo) { $baseInfo = Find-BasePython }
    if ($InspectOnly) {
        if ($venvInfo) { Write-Host "可复用虚拟环境：$($venvInfo.executable)，Python $($venvInfo.version)（64 位）。" }
        elseif ($baseInfo) { Write-Host "可用基础 Python：$($baseInfo.executable)，版本 $($baseInfo.version)（64 位）。" }
        else { Write-Host "没有合适的 Python，正式配置时将下载官方 $script:PythonVersion（64 位）。" }
        Write-Host '仅检查结束，未下载、安装或修改文件。'
        return
    }
    $cache = Join-Path $script:ProjectRoot 'backend\.pipcache'
    $temp = Join-Path $script:ProjectRoot 'backend\.setup\tmp'
    New-Item -ItemType Directory -Force -Path $cache, $temp | Out-Null
    # 只作用于本次脚本及子进程；现有 pip.ini 和全局 pip 配置保持原样。
    $env:TEMP = $temp
    $env:TMP = $temp
    $env:PIP_CACHE_DIR = $cache
    $env:PIP_INDEX_URL = $script:Mirror
    $env:PIP_EXTRA_INDEX_URL = ''
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:PIP_NO_INPUT = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    $downloaded = $false
    $backup = $null
    if (-not $venvInfo) {
        if (-not $baseInfo) {
            $baseInfo = Install-ProjectPython
            $downloaded = $true
        }
        Write-Host "[2/4] 使用 Python $($baseInfo.version) 创建项目虚拟环境……"
        $backup = Initialize-ProjectVenv $baseInfo.executable
    } else {
        Write-Host "[2/4] 复用现有虚拟环境（Python $($venvInfo.version)），无需重建。"
    }
    $pipIni = Join-Path $script:ProjectRoot 'backend\.venv\pip.ini'
    if (-not (Test-Path -LiteralPath $pipIni)) {
        $config = "[global]`r`ncache-dir = $cache`r`nindex-url = $script:Mirror`r`ntimeout = 60`r`n"
        [IO.File]::WriteAllText($pipIni, $config, (New-Object Text.UTF8Encoding($false)))
    }
    $env:PIP_CONFIG_FILE = $pipIni
    $pip = Invoke-ProcessCapture $python @('-m', 'pip', '--version')
    if ($pip.ExitCode -ne 0) { Invoke-PythonCommand $python @('-m', 'ensurepip', '--upgrade') }
    Write-Host '[3/4] 使用清华大学镜像源安装 backend\requirements.txt 中的依赖……'
    Write-Host "镜像源：$script:Mirror"
    Invoke-PythonCommand $python @('-m', 'pip', '--disable-pip-version-check', 'install',
        '--index-url', $script:Mirror, '--cache-dir', $cache, '--timeout', '60', '--retries', '2', '-r', $requirements)
    Write-Host '[4/4] 检查依赖是否完整……'
    Invoke-PythonCommand $python @('-m', 'pip', '--disable-pip-version-check', 'check')
    Write-Host ''
    Write-Host '配置完成！刚刚完成了以下操作：' -ForegroundColor Green
    if ($downloaded) { Write-Host '- 使用经 Python 官方数字签名校验的安装包，将 Python 安装到项目的 .runtime\python312。' }
    elseif ($venvInfo) { Write-Host '- 检查并复用了现有的 64 位 Python 3.12 虚拟环境。' }
    else { Write-Host "- 检查并复用了电脑已有的 Python $($baseInfo.version)：$($baseInfo.executable)" }
    if (-not $venvInfo) { Write-Host '- 创建了项目独立的虚拟环境 backend\.venv。' }
    Write-Host '- 使用清华大学镜像源安装或确认了项目依赖，并通过依赖完整性检查。'
    Write-Host '- pip 下载缓存与安装临时目录设置在项目内；已有 pip.ini 保留原内容。'
    if ($backup) { Write-Host "- 原虚拟环境备份保留在：$backup" }
    Write-Host ''
    Write-Host '现在可以关闭这个窗口，然后双击 start.bat 启动灵栖。' -ForegroundColor Green
    Write-Host '对话模型服务（如 Ollama）和 API Key 仍需在使用时自行准备。'
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-EnvironmentSetup -InspectOnly:$CheckOnly
        exit 0
    } catch {
        Write-Host ''
        Write-Host "配置失败：$($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}
