# DICOM 运维工具

一款面向医疗影像运维人员的桌面工具，支持 DICOM 文件的收发、转发、编辑、匿名化及 Worklist 管理。

## 主要功能

- **发送**：多节点管理，批量发送，C-ECHO 连通性测试
- **接收**：DICOM SCP 服务，自动转发到指定节点，转发失败自动重试（5分钟）
- **Worklist**：内置 Worklist SCP 服务，支持手动添加/生成测试数据，SCU 查询
- **编辑器**：标签查看与编辑，图像显示（自动窗宽窗位），匿名化（保留病历号后4位），UID 修改，年龄自动计算
- **文件浏览**：扫描文件夹，批量匿名化/计算年龄/修改UID，导出 Excel
- **中文乱码修复**：自动检测并修复 GB2312/GBK/GB18030 编码的中文标签

## 运行环境

- Windows 10/11 x64
- Python 3.9+
- 无需互联网连接

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动

```bash
python src/main_complete.py
```

或双击 `启动工具.bat`

## 项目结构

```
src/
├── main_complete.py      # 主程序入口
├── dicom/                # DICOM 收发、编辑、图像处理
├── core/                 # 配置管理、日志、转发队列
└── utils/                # UID、年龄计算、Excel导出、编码修复
config/
└── app_config.json       # 运行时自动生成
logs/                     # 运行日志
```

## 配置文件

首次运行自动创建 `config/app_config.json`，包含节点配置、窗宽窗位预设、匿名化规则等。

## 注意事项

- `storage/` 目录存储接收到的 DICOM 文件，可能含患者信息，已加入 `.gitignore`
- 生产环境使用前请确认匿名化规则符合当地法规要求
