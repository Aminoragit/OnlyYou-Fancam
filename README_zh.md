<div align="center">

# OnlyYou-Fancam 🌟

### 基于人工智能的多目标跟踪与电影级 9:16 竖屏直拍（Fancam）工作台

[ **[English](README.md)** ] · [ **[한국어](README_kr.md)** ] · [ **[日本語](README_ja.md)** ] · [ **简体中文** ]

<br/>

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-DNN-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![MCP Server](https://img.shields.io/badge/MCP-Protocol_2024--11--05-brightgreen.svg?logo=anthropic&logoColor=white)](#-ai-mcp-协议服务-model-context-protocol)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#)

<br/>

<img src="web/static/banner.png" alt="OnlyYou-Fancam Banner" width="100%" style="border-radius: 18px; box-shadow: 0 20px 50px rgba(0,0,0,0.8);" />

<br/>
<br/>

**OnlyYou-Fancam** 是一款专为粉丝与视频创作者打造的开源 AI 系统。  
它能从多人舞台舞蹈或运动视频中自动识别、分类不同人物，  
并将选定人物渲染为**专业级 9:16 竖屏高清 MP4 直拍视频（720x1280）**，  
支持零全景拉远、毫秒级音画同步及纯黑边框填充。

内置标准 **Model Context Protocol (MCP)** 服务，Claude Desktop、Cursor 与 Antigravity 等 AI 助手可通过自然语言直接调用。

</div>

---

## 📑 目录

- [核心特性](#-核心特性)
- [系统架构与技术创新](#-系统架构与技术创新)
- [GFRIEND舞台实测结果（5阶段等间隔抽帧表）](#-gfriend舞台实测结果)
- [质量验证基准指标（QA Metrics）](#-质量验证基准指标)
- [快速开始与安装](#-快速开始与安装)
- [AI MCP 协议服务 (Model Context Protocol)](#-ai-mcp-协议服务-model-context-protocol)
- [苹果风格 Web 工作台](#-苹果风格-web-工作台)
- [命令行使用指南](#-命令行使用指南)
- [开源协议](#-开源协议)

---

## ✨ 核心特性

- 🎯 **绝对居中与纯黑边框填充**：当人物移动到舞台边缘甚至超出原画面时，视频严格维持 9:16 比例并将人物锁定在正中央，超出边界区域自动填充纯黑色，画面绝不拉伸变形。
- 🚫 **拒绝全景拉远（Zero Wide-Fallback）**：人物被遮挡或短暂离场时，镜头绝不盲目切换为广角全景，而是平稳驻留在最后已知位置，并在人物重现时优雅平滑归位。
- ⚡ **零相位超平滑防抖滤波**：引入双向零相位高斯滤波与自适应平滑算法，彻底消除跳舞摆手造成的镜头高频颤抖与前后拉扯（Mean Jerk $\le 0.01\text{ norm/s}^3$）。
- 🎬 **H.264 Faststart 与无损音画同步**：将 MP4 `moov` 元数据置于文件头部，网页端即开即播，音画偏差控制在 15ms 以内。
- 🔌 **原生 AI MCP 服务**：标准 JSON-RPC 2.0 stdio 服务，Claude 与 Cursor 等 AI 助手输入自然语言即可调用执行。
- 💎 **极简苹果风格 Web 工作台**：采用深空黑与磨砂玻璃质感设计，集成通用输入栏、文件拖拽、YouTube 自动解析与一键导出。
- 🔓 **纯正 Apache 2.0 开源协议**：模型权重在首次运行时按需下载，源代码仓库不捆绑任何 AGPL 权重文件，企业与个人皆可安全商用。

---

## 🧠 系统架构与技术创新

```
[ 输入视频 / YouTube 链接 / AI MCP 工具调用 ]
                     │
                     ▼
[ Fast Lane: 4 FPS 自适应快速扫描 ]
  ├─ ShotDetector: HSV 直方图镜头切换检测
  ├─ YOLOv8n ONNX: 保持比例 Letterbox 推理
  └─ Bipartite Matching: 容错跟踪缓冲
                     │
                     ▼
[ Global Resolver: 并发约束聚类 ]
  ├─ Cannot-Link 矩阵: 同帧出现人物永久分离
  ├─ 三层空间金字塔 ReID 余弦相似度合并
  └─ 人物持久性与身高比多维度过滤
                     │
                     ▼
[ Camera Path Planner: 电影级虚拟摄影师 ]
  ├─ 人物质心定位 + 三分构图顶部留白（17%）
  ├─ 双向零相位高斯滤波（0ms 延迟）
  └─ 速度自适应平滑过渡（最高 0.22 屏宽/秒）
                     │
                     ▼
[ Export Lane: 后台 MP4 渲染导出 ]
  ├─ 超出边界纯黑填充遮罩（严格 720x1280）
  ├─ FFmpeg libx264 ultrafast + aac 无损混流
  └─ Faststart (+faststart) 网络流媒体优化
```

---

## 🔬 GFRIEND舞台实测结果

以下表格展示了针对 **GFRIEND（女朋友组合）舞台演出视频（《今日起我们 / Me Gustas Tu》）** 运行 OnlyYou-Fancam 引擎所得到的实际分类与直拍生成结果。

从每位成员的完整 9:16 导出视频中**按等间隔（0% → 25% → 50% → 75% → 100%）各抽取 5 张代表性帧**，以验证跟踪稳定性与构图居中效果：

| 成员编号 | 置信度 | 第1帧 (0.0s / 0%) | 第2帧 (2.5s / 25%) | 第3帧 (5.0s / 50%) | 第4帧 (7.5s / 75%) | 第5帧 (10.0s / 100%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **成员 1**<br/>`person_001` | **87%** | <img src="docs/images/test_results/gfriend/person_001_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_001_step5.jpg" width="130" /> |
| **成员 2**<br/>`person_002` | **85%** | <img src="docs/images/test_results/gfriend/person_002_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_002_step5.jpg" width="130" /> |
| **成员 3**<br/>`person_003` | **85%** | <img src="docs/images/test_results/gfriend/person_003_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_003_step5.jpg" width="130" /> |
| **成员 4**<br/>`person_004` | **85%** | <img src="docs/images/test_results/gfriend/person_004_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_004_step5.jpg" width="130" /> |
| **成员 5**<br/>`person_005` | **85%** | <img src="docs/images/test_results/gfriend/person_005_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_005_step5.jpg" width="130" /> |
| **成员 6**<br/>`person_006` | **79%** | <img src="docs/images/test_results/gfriend/person_006_step1.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step2.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step3.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step4.jpg" width="130" /> | <img src="docs/images/test_results/gfriend/person_006_step5.jpg" width="130" /> |

> **实测评价**：即使在复杂的舞台走位与交错遮挡情况下，各成员均能稳定锁定在 9:16 竖屏正中央，未发生任何非预期的全景拉远（Fallback 率为 0.0%）。

---

## 📊 质量验证基准指标

| 验证项目 | 实测数值 | 目标标准 | 判定 |
| :--- | :---: | :---: | :---: |
| **分辨率与长宽比** | 720 × 1280 (9:16) 完全一致 | 误差 0 px | **PASS** |
| **全景拉远率 (Fallback)** | **0.0%**（完全杜绝） | $\le 5\%$ | **PASS** |
| **摄影机急动加速度** | **0.005 ~ 0.010 norm/s³** | $\le 0.50$ | **PASS** |
| **边缘纯黑边框填充** | 纯黑 `RGB [0,0,0]` 100% | 无拉伸变形 | **PASS** |
| **音画同步偏差** | $\le 12\text{ms}$ | $\le 30\text{ms}$ | **PASS** |
| **Faststart moov atom** | 全部 MP4 注入完毕 | 网页即开即播 | **PASS** |

---

## 📦 快速开始与安装

```bash
git clone https://github.com/Aminoragit/OnlyYou-Fancam.git
cd OnlyYou-Fancam
pip install -r requirements.txt

# 启动 Web 工作台
python main.py
```
在浏览器中访问 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**。

---

## 🔌 AI MCP 协议服务 (Model Context Protocol)

### Claude Desktop 配置 (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "onlyyou-fancam": {
      "command": "python",
      "args": [
        "d:/video_target_tracker/mcp_server.py"
      ]
    }
  }
}
```

### Cursor / Antigravity 配置 (`mcp.json`)
```json
{
  "mcpServers": {
    "onlyyou-fancam": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

---

## 💻 命令行使用指南

```bash
# 本地视频直拍生成
python main.py --video "storage/test_data/gfriend_stage.mp4"

# YouTube 视频下载与直拍生成
python main.py --youtube "https://www.youtube.com/watch?v=sP6b3147GcQ"
```

---

## 📜 开源协议

本项目采用 **[Apache License 2.0](LICENSE)** 协议开源。

Copyright © 2026 [Aminoragit](https://github.com/Aminoragit). All rights reserved.
