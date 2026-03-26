# DICOM 运维工具

面向医疗影像运维人员的桌面工具，支持 DICOM 文件的收发、转发、编辑、匿名化及 Worklist 管理。无需互联网，适用于 Windows 10/11 x64 离线环境。

## 功能概览

| 功能页 | 主要能力 |
|--------|----------|
| 📤 发送 | 多节点管理、批量发送、C-ECHO 连通测试 |
| 📥 接收 | DICOM SCP 服务、条件自动转发、转发队列管理 |
| 📋 Worklist | 内置 Worklist SCP/SCU，手动添加数据，支持日期范围查询 |
| ✏️ 编辑器 | 标签查看/编辑、图像显示、匿名化、UID 修改、年龄计算 |
| 📁 文件浏览 | 扫描文件夹、批量操作（可中断）、导出 Excel |

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动

```bash
python src/main_complete.py
```

或双击 `启动工具.bat`

## 各功能详细说明

### 📤 发送页

- 右侧填写节点信息后点"添加节点"，支持配置多个目标节点
- 双击节点列表中的行可将参数填入右侧编辑区
- 点击第一列（✓）勾选目标节点，支持全选/全不选
- "测试选中"对勾选节点发送 C-ECHO，失败时显示具体原因
- 添加文件/文件夹后点"发送到选中节点"，同时发送到多个节点

### 📥 接收页

- 配置本地 AE Title、端口、存储路径后点"▶ 启动"
- 配置会自动保存，下次启动无需重新填写
- **条件转发规则**：可按模态（CR/DR/CT 等）和来源 AE 过滤，匹配则自动转发到指定节点；不配置规则时转发到发送页勾选的节点
- 转发队列面板实时显示任务状态，支持手动重试失败任务、清除已完成任务
- 日志带时间戳，方便排查问题

### 📋 Worklist 页

**SCP 服务（响应设备查询）**
- 配置 AE Title 和端口后启动，设备可向本工具发送 C-FIND 查询
- 支持手动添加患者信息，或点"生成测试数据"生成随机数据
- 数据持久化到 `config/worklist_data.json`

**SCU 查询（向服务器查询）**
- 配置服务器地址后发送 C-FIND 查询
- 支持按患者ID、姓名、模态过滤
- 检查日期支持范围查询：
  - `20260101` — 精确匹配
  - `20260101-` — 2026年1月1日及之后
  - `-20260131` — 2026年1月31日及之前
  - `20260101-20260131` — 日期范围

### ✏️ 编辑器页

- 打开单个 DCM 文件，左侧显示图像，右侧显示全部标签
- **窗宽窗位**：首次打开自动调整，可手动拖动滑块或点预设按钮（肺窗/纵隔/骨窗/软组织）
- **计算年龄**：仅当文件中无年龄字段时显示，根据出生日期自动计算
- **匿名化**：保留病历号后4位，其余字段清空
- **修改UID**：重新生成 StudyInstanceUID、SeriesInstanceUID、SOPInstanceUID、AccessionNumber，并在 PatientID 后追加日期后缀，确保上传 PACS 不重复
- **应用标签修改**：直接在文本框中编辑标签值后点击应用，支持字符串、整数（US/SS/UL/SL）、浮点（FL/FD）类型

### 📁 文件浏览页

- 选择文件夹后自动扫描所有 .dcm 文件，显示患者信息和三个 UID
- 点击列标题可排序
- **批量操作**（均输出到源文件夹同级的 `_updated` 目录，原文件不变）：
  - 批量匿名化
  - 批量计算年龄（仅处理无年龄的文件）
  - 批量修改UID（保持Study关联）— 同一检查的多张图共享新 StudyUID
  - 批量修改UID（每文件独立Study）— 每个文件独立生成新 StudyUID，适用于多患者混合文件夹或原始 UID 已损坏的情况
- 所有批量操作支持**中断**（点"✕ 取消"按钮）
- 导出 Excel：包含路径、患者信息、三个 UID 字段

## UID 修改说明

修改 UID 时会同步处理以下字段，确保上传 DCM4CHEE 等 PACS 不报 409 冲突：

| 字段 | 处理方式 |
|------|----------|
| StudyInstanceUID | 重新生成（同一检查共享） |
| SeriesInstanceUID | 重新生成（同一序列共享） |
| SOPInstanceUID | 每个文件独立生成 |
| file_meta.MediaStorageSOPInstanceUID | 与 SOPInstanceUID 同步 |
| AccessionNumber | 重新生成（同一检查共享） |
| PatientID | 原ID后追加日期后缀（如 `105_03261550`） |

## 中文乱码说明

内置编码自动检测，支持 GB18030/GBK/GB2312/UTF-8 自动识别和修复。修复后将 SpecificCharacterSet 更新为 UTF-8，保存后不再出现乱码。

## 配置文件

`config/app_config.json` 首次运行自动创建，包含：

```json
{
  "remote_nodes": [...],          // 远程节点列表
  "local_scp": {...},             // 本地SCP配置（自动保存）
  "forward_rules": [...],         // 条件转发规则
  "worklist_scp": {...},          // Worklist SCP配置
  "ui_settings": {...},           // 窗宽窗位预设等
  "anonymize": {...},             // 匿名化规则
  "uid_strategy": {...}           // UID修改策略
}
```

## 打包为 EXE

```bash
build_exe.bat
```

输出在 `dist/` 目录。

## 项目结构

```
src/
├── main_complete.py      # 主程序入口
├── dicom/                # DICOM 收发、编辑、图像处理
│   ├── scu.py            # 发送客户端
│   ├── scp.py            # 接收服务
│   ├── editor.py         # 标签编辑
│   ├── anonymizer.py     # 匿名化
│   ├── echo.py           # C-ECHO 测试
│   ├── image_viewer.py   # 图像处理
│   ├── worklist.py       # Worklist SCU
│   └── worklist_scp.py   # Worklist SCP
├── core/                 # 基础服务
│   ├── config_manager.py # 配置管理
│   ├── logger.py         # 日志
│   └── forward_queue.py  # 转发队列
├── gui/                  # 界面
│   ├── tab_send.py
│   ├── tab_receive.py
│   ├── tab_worklist.py
│   ├── tab_editor.py
│   └── tab_browser.py
└── utils/                # 工具函数
    ├── uid_generator.py  # UID 生成/修改
    ├── age_calculator.py # 年龄计算
    ├── excel_exporter.py # Excel 导出
    └── charset_helper.py # 中文编码修复
config/
├── app_config.json       # 运行时配置（自动生成）
└── worklist_data.json    # Worklist 数据
logs/                     # 运行日志（按日期分文件）
storage/                  # 接收到的 DICOM 文件
```

## 注意事项

- `storage/` 目录存储接收到的 DICOM 文件，可能含患者信息，已加入 `.gitignore`
- 生产环境使用前请确认匿名化规则符合当地法规要求
- 批量修改 UID 前建议先用原始文件，不要对已处理过的 `_updated` 文件夹再次处理
