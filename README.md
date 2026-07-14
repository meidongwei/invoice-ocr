# 发票识别 (Invoice OCR)

基于 PaddleOCR 的发票识别桌面应用，支持电子发票（普票/专票/铁路电子客票）的 PDF 和图片识别，自动提取关键信息并导出为 CSV。

## ✨ 功能特性

- 支持 **PDF**（文本层直读 + 扫描件 OCR）和 **图片** 识别
- 自动识别发票类型：电子发票（普通发票）、电子发票（增值税专用发票）、电子发票（铁路电子客票）
- 提取字段：销售方名称、发票号码、合计税额
- 批量处理，结果导出为 CSV
- PySide6 图形界面，跨平台（Windows / macOS）

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows 或 macOS

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/invoice-ocr.git
cd invoice-ocr

# 创建虚拟环境并安装依赖
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 运行

**macOS：**
```bash
双击 invoice_recognition_startup.command
```

**Windows：**
```bash
双击 invoice_recognition_startup.bat
```

### 使用步骤

1. 点击「选择文件」，选中 PDF 或图片发票（可多选）
2. 如需更改保存位置，点击「更改目录」（默认桌面）
3. 点击「开始识别」
4. 等待识别完成，结果会显示在下方表格中
5. 点击「打开结果文件夹」查看 CSV 文件

## 📦 打包为 EXE（Windows）

在 Windows 上双击 `BuildToEXE.bat` 即可将应用打包为独立的 `.exe` 文件，用户无需安装 Python。

> ⚠️ 注意：Mac 上无法生成可用的 Windows exe，请把整个项目文件夹拷到 Windows 电脑后再打包。

### 1. 安装 Python（必须）

1. 打开 https://www.python.org/downloads/ 下载并安装 Python 3.10 或更高
2. 安装界面务必勾选 **Add python.exe to PATH**
3. 安装完成后，关掉所有命令窗口，重新打开再打包

若提示 `Python was not found`：
- 设置 → 应用 → 高级应用设置 → 应用执行别名
- 关闭 `python.exe`、`python3.exe` 的开关
- 然后重新安装 Python 并勾选 Add to PATH

### 2. 打包

1. 把整个项目文件夹拷到 Windows 电脑
2. 双击 `BuildToEXE.bat`
3. 等待完成（首次 10~30 分钟，需联网）
4. 自动打开文件夹：`dist\发票识别\`

### 3. 测试

双击 `dist\发票识别\发票识别.exe`，不需要再装 Python。

### 4. 分发给普通用户

把整个文件夹打包成 zip 发给对方：

```
发票识别\
 ├── 发票识别.exe     ← 双击这个
 └── _internal\       ← 必须一起带走
```

不要只发单个 exe，否则会打不开。如果修改过代码或打包配置，请重新双击 `BuildToEXE.bat`，并用新生成的 `dist\发票识别\` 整个文件夹替换旧版本。

### 5. 开发测试（不打包，需要 Python）

双击 `invoice_recognition_startup.bat`。

### 6. 打包失败排查

在文件夹中打开命令提示符，运行 `BuildToEXE.bat`，把黑色窗口里的报错截图发回即可。

常见错误：`Read timed out` / `files.pythonhosted.org`
- 这是下载 Python 依赖超时，不是程序代码错误
- 已在脚本中使用国内镜像并增加重试次数
- 若仍失败，换一个网络或手机热点后重新双击 `BuildToEXE.bat`
- 已经下载成功的依赖会保留在 `.venv` 里，重新运行会继续安装剩余部分

## 📊 输出格式

| 字段 | 说明 |
|------|------|
| 源文件 | 原始文件名 |
| 发票类型 | 自动识别 |
| 销售方名称 | 销售方信息 |
| 发票号码 | 发票编号 |
| 合计税额 | 税额（铁路电子客票为票价） |

输出文件名格式：`YYYYMMDD_001.csv`（同一天自动递增序号）。

## 🏗️ 技术栈

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR 识别引擎
- [PySide6](https://pypi.org/project/PySide6/) - GUI 框架
- [pdfplumber](https://github.com/jsvine/pdfplumber) - PDF 文本提取
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) - PDF 页面渲染

## 📄 开源协议

[MIT License](LICENSE)
