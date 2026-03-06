# 第五人格录像解析器

一个用于解析和管理《第五人格》游戏录像文件的工具，提供图形界面（GUI）和命令行界面（CLI）两种方式。核心解析逻辑封装在独立模块中，便于维护和扩展。

---

## 文件结构

- `idv_replay_core.py`：核心模块，包含常量、数据模型、解析器类以及通用辅助函数（如 `update_vmap`），供 GUI 和 CLI 共享。
- `IdentityV_Replay_Parser_GUI.py`：图形界面主程序，基于 Tkinter 实现。
- `IdentityV_Replay_Parser_CLI.py`：命令行界面主程序，支持批量处理与过滤。
- `README.md`：本文档。

---

## 功能特性

### 核心模块 (idv_replay_core.py)
- 定义地图、模式名称映射及逃生判定常量。
- `ReplayParser` 类：解析单个录像文件夹的 `game_info.txt`，提取日期、时间、结果、地图、逃生人数等信息。
- `parse_all_replays()`：批量解析指定目录下的所有录像。
- `update_vmap()`：更新游戏索引文件 `vmap.txt`，确保导入的录像在游戏中可见。

### GUI 版本 (IdentityV_Replay_Parser_GUI.py)
- **图形界面**：直观的窗口操作，支持路径记忆、一键解析、结果显示。
- **导出为 ZIP**：选中单个录像后打包为 ZIP 文件，文件名自动生成（包含模式、日期、结果、地图等描述信息）。
- **导出统计数据**：将所有成功解析的录像信息导出为 CSV 文件。
- **导入 ZIP**：将之前导出的 ZIP 文件重新导入到录像根目录，自动解压并更新 `vmap.txt`。
- **路径记忆**：用户设置的“录像根目录”和“导出路径”自动保存到 `config.json` 中，下次启动时自动加载。
- **日志记录**：程序运行日志保存在同目录下的 `replay_parser.log` 文件中。

### CLI 版本 (IdentityV_Replay_Parser_CLI.py)
- **命令行操作**：通过子命令 `parse`、`export`、`import` 实现解析、导出、导入等功能。
- **灵活过滤**：可根据模式、日期、结果、地图、逃生人数等条件过滤录像。
- **批量导出**：支持按条件批量导出多个录像为 ZIP 文件。
- **多种输出格式**：解析结果可导出为 CSV 或 JSON 格式。
- **无配置记忆**：所有路径需通过命令行参数指定，适合脚本集成。

---

## 系统要求

- 操作系统：Windows 7 或更高版本（理论上支持 Linux/macOS，但游戏录像通常位于 Windows 系统）
- Python 3.7 或更高版本（若直接运行源码）
- 依赖库：
  - `pymongo`（提供 `bson` 模块，用于反序列化游戏数据）
  - `tkinter`（Python 标准库，用于 GUI，仅 GUI 版本需要）

---

## 安装与运行

### 方式一：直接运行 Python 源码

1. **克隆或下载本项目**，确保以下文件在同一目录：
   - `idv_replay_core.py`
   - `IdentityV_Replay_Parser_GUI.py`
   - `IdentityV_Replay_Parser_CLI.py`

2. **安装依赖**（建议使用虚拟环境）：
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate    # Linux/macOS
   pip install pymongo
   ```

3. **运行 GUI 版本**：
   ```bash
   python IdentityV_Replay_Parser_GUI.py
   ```

4. **运行 CLI 版本**（查看帮助）：
   ```bash
   python IdentityV_Replay_Parser_CLI.py --help
   ```

### 方式二：打包为独立可执行文件（无需 Python 环境）

#### GUI 版本打包
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "第五人格录像解析器" \
  --hidden-import bson --hidden-import bson.objectid --hidden-import pymongo \
  IdentityV_Replay_Parser_GUI.py
```
生成的可执行文件位于 `dist` 文件夹中。

#### CLI 版本打包
```bash
pyinstaller --onefile --name "IdentityV_Replay_Parser_CLI" \
  --hidden-import bson --hidden-import bson.objectid --hidden-import pymongo \
  IdentityV_Replay_Parser_CLI.py
```

**注意**：打包时需确保 `idv_replay_core.py` 与主程序在同一目录，或使用 `--add-data` 将其包含。

---

## 使用方法

### GUI 版本

#### 主界面说明
- **录像根目录**：存放所有哈希命名的录像文件夹的父目录（例如游戏安装目录下的 `Documents\video`）。
- **导出路径**：ZIP 文件默认保存目录（留空则每次导出时弹出对话框）。
- **解析录像**：扫描当前录像根目录，提取信息并显示在下方列表中。
- **导出为 ZIP**：在列表中选中一个录像后，将其打包为 ZIP 文件。
- **导出统计数据**：将所有成功解析的录像信息导出为 CSV 文件。
- **导入 ZIP**：选择之前导出的 ZIP 文件，自动解压并更新索引。

#### 使用流程示例
1. 设置录像根目录为 `D:\Program Files\dwrg2\Documents\video`。
2. 点击“解析录像”，列表显示所有录像及其对战信息。
3. 选中某个录像，点击“导出为 ZIP”进行备份。
4. 如需恢复备份，点击“导入 ZIP”选择对应的 ZIP 文件。

### CLI 版本

#### 全局帮助
```bash
python IdentityV_Replay_Parser_CLI.py --help
```

#### 子命令：parse —— 解析并显示/导出录像信息
```bash
python IdentityV_Replay_Parser_CLI.py parse <root_dir> [--export-csv FILE] [--export-json FILE] [--filter KEY=VALUE] [--show-errors]
```
- `--filter` 支持键：`mode`、`date`、`time`、`result`、`map`、`escape`（逃生人数整数）。

示例：
```bash
# 解析并显示所有录像
python IdentityV_Replay_Parser_CLI.py parse "D:\Program Files\dwrg2\Documents\video"

# 解析并导出为 CSV，只显示结果为“四抓”的录像
python IdentityV_Replay_Parser_CLI.py parse "D:\Program Files\dwrg2\Documents\video" --export-csv stats.csv --filter result=四抓
```

#### 子命令：export —— 导出录像为 ZIP 文件
```bash
python IdentityV_Replay_Parser_CLI.py export <root_dir> --output-dir DIR [--filter KEY=VALUE] [--hash HASH] [--force]
```
示例：
```bash
# 导出所有录像到 ./backup 目录
python IdentityV_Replay_Parser_CLI.py export "D:\Program Files\dwrg2\Documents\video" -o ./backup

# 按条件导出（地图为“军工厂”且结果为“四抓”）
python IdentityV_Replay_Parser_CLI.py export "D:\Program Files\dwrg2\Documents\video" -o ./zips --filter map=军工厂 --filter result=四抓

# 导出单个录像（指定哈希）
python IdentityV_Replay_Parser_CLI.py export "D:\Program Files\dwrg2\Documents\video" --hash 306779587 -o ./single
```

#### 子命令：import —— 导入 ZIP 文件到录像目录
```bash
python IdentityV_Replay_Parser_CLI.py import <root_dir> <zip_file> [--force]
```
示例：
```bash
python IdentityV_Replay_Parser_CLI.py import "D:\Program Files\dwrg2\Documents\video" ./backup/306779587(排位模式-3月5日-20-30-15-四抓-军工厂).zip --force
```

---

## 配置文件说明（仅 GUI）

程序首次运行后会在同目录下生成 `config.json` 文件，内容示例如下：
```json
{
  "root_path": "D:/Program Files/dwrg2/Documents/video",
  "export_path": "D:/Users/YourUsername/Downloads"
}
```
每次通过界面修改路径后，配置文件会自动更新。

---

## 常见问题

### 1. 导入ZIP时出现跨驱动器错误（OSError: [WinError 17]）
- **原因**：临时目录与目标目录不在同一驱动器。
- **解决**：代码已使用 `shutil.move` 替代 `os.rename`，可自动处理跨驱动器移动。若仍遇到，请确保代码为最新版本。

### 2. 打包后的 exe 无法记忆路径（仅 GUI）
- **原因**：exe 所在目录无写入权限，或未正确处理配置文件路径。
- **解决**：将 exe 放在用户文件夹（如桌面）运行，确保能生成 `config.json`。代码已内置 `get_base_dir()` 函数获取正确路径。

### 3. 解析录像时出现 `No module named 'bson'` 错误
- **原因**：缺少 `pymongo` 库。
- **解决**：运行 `pip install pymongo`。打包时需添加 `--hidden-import bson --hidden-import bson.objectid`。

### 4. 导入ZIP后游戏内不显示录像
- **可能原因**：
  - 未重启游戏（`vmap.txt` 可能在游戏启动时加载一次）。
  - `vmap.txt` 更新失败（检查日志）。
  - 导入的 ZIP 不是由本工具导出的，或内部结构损坏。
- **建议**：导入后重启游戏，查看日志确认 `vmap.txt` 已成功更新。

### 5. CLI 版本提示无法导入 `idv_replay_core`
- **原因**：`idv_replay_core.py` 不在同一目录，或文件名不匹配。
- **解决**：确保核心模块与 CLI 脚本在同一目录，且文件名完全一致。

### 6. 如何添加新的地图或模式映射？
- 编辑 `idv_replay_core.py` 中的 `MAP_NAMES` 和 `MODE_NAMES` 字典，按格式添加新 ID 和名称。GUI 和 CLI 会自动生效。

---

## 更新日志

- **v1.0**（当前）：初始版本，包含核心模块、GUI 和 CLI。支持解析、导出 ZIP、导出 CSV、导入 ZIP 并更新 vmap.txt。

---

## 许可证

本项目仅供学习交流使用，未经授权不得用于商业用途。《第五人格》游戏相关内容版权归网易公司所有。

---

如有任何问题或建议，欢迎提交 Issue 或联系作者。