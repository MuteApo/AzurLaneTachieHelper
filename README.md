# AzurLane Tachie Helper

碧蓝航线立绘工作台（Tachie Studio），支持 Unity 图集还原、立绘与差分编辑、分层 PSD 导出、头像裁切和设备资源拉取。

## 启动

安装 uv 后，在仓库根目录执行：

```powershell
uv sync --locked
uv run --locked tachie
```

使用 Python 3.14，uv 会按需安装解释器。Windows 也可双击 `launch.bat`；`tachie-next` 保留为同一入口的兼容别名。

主题默认跟随系统，可在外观菜单切换。语言按系统界面语言选择中文或英文，也可在偏好设置覆盖，下次启动生效。应用菜单位于左上角 **T** 图标，包含设置与日志入口。

配置和轮转日志保存在系统应用数据目录；应用标识保留为 `Tachie/TachieNext`，延续已有设置。需要指定位置时使用 `uv run --locked tachie --data-dir .local`。

## 基本用法

1. **打开素材**：选择或拖入资源文件夹，也可打开已保存的编辑进度。文件夹内有多份立绘时会列出候选。
2. **查看与编辑**：左侧选择立绘、表情或头像；预览默认显示单张图片，可切换合成效果。右侧提供图片替换、批量导入、PSD 导出和头像制作。图片或差分目录也可拖入预览区。
3. **调整替换图片**：名称无法唯一匹配时选择目标；尺寸与目标画布不符时，通过参考叠加、拖动、缩放和像素坐标进行对齐。同尺寸差分可共用对齐位置，取消则整批不应用。
4. **保存或导出**：保存编辑进度供下次继续；导出游戏替换文件生成资源补丁。顶部项目名旁的关闭按钮可返回首页，未保存时会提示处理。

画布支持滚轮缩放和拖动平移，透明网格默认开启。头像和未替换的单张表情默认按 1:1 显示，立绘、合成及替换后的表情适应画布。

高级设置中的差分范围支持关闭、自动和自定义。自定义边界以画布像素计，按钮步进为 25；左、下负值及右、上正值向外扩展，也可直接输入精确数值。

“制作头像”支持原头像叠加参考、拖动定位、滚轮缩放、Ctrl＋拖动旋转和方向键逐像素移动。默认应用到当前编辑并支持撤销；“同时另存头像图片到文件夹”默认关闭，需要独立 PNG 时再勾选。

### 保存内容与输出

| 操作 | 结果 |
| --- | --- |
| 保存编辑进度 | `.tachie.json` 与旁边的 `.assets` 图片快照目录；原始 Unity 包仍通过路径引用 |
| 导出游戏替换文件 | 独立时间戳目录中的已修改资源包，保留游戏目录结构；不覆盖源文件、不自动推送到设备 |
| 导出 PSD | 保留图层位置和透明度，表情差分分组默认隐藏；不附带完整合成预览 |
| 另存头像 | 独立子目录中的 PNG；有对应资源时同时应用为可撤销的编辑 |

移动已保存项目时保留 JSON、快照目录及引用的源资源；引用失效时可重新定位。依赖索引沿父目录查找，也可在偏好设置指定。

## 从设备拉取

从首页的手机 / 模拟器入口进入，选择设备、立绘和保存位置后下载：

- 设备列表展示在线设备，“自动选择”使用第一台；支持刷新、手动选择和模拟器地址连接。
- 立绘名称支持片段补全，索引按设备与游戏包名缓存；可主动刷新，实际下载会重新获取索引。
- 保存位置预填到默认 `projects/` 或上次使用的父目录，并避开现有目录；手动编辑后不再自动改动。
- 拉取包括可用的 `_n` 版本、依赖、差分和三类头像，缺失项集中反馈；缺少资源时自动尝试从已安装 APK 及分包恢复。

Windows 的 ADB 由 `adbutils` 依赖提供，无需另备 `3rdparty/`。自定义 ADB 路径在偏好设置调整，游戏包名在连接设置调整。普通本地项目不会连接设备。

## 导入旧配置

通过“编辑 → 导入原版配置…”选择旧 INI 和原版工作目录，预览后合并有效设置，原文件保持不变。工作目录用于解析旧相对路径。

迁入的头像预设、差分范围等默认值在重新打开原始 metadata 时应用；当前会话不变，已保存项目优先使用自身设置。图片匹配兼容原版 PSD 的“节点名 [纹理名]”命名。

## 快捷键与终端

| 操作 | 快捷键 |
| --- | --- |
| 应用菜单 | F10 |
| 打开 / 关闭项目 | Ctrl+O / Ctrl+W |
| 保存 / 另存为 | Ctrl+S / Ctrl+Shift+S |
| 撤销 / 重做 | Ctrl+Z / 系统标准重做快捷键 |
| 批量导入 | Ctrl+I |
| 导出资源 / PSD | Ctrl+E / Ctrl+Shift+E |
| 制作头像 | Ctrl+K |
| 适应画布 / 实际像素 | Ctrl+0 / Ctrl+1 |

终端支持直接打开 metadata 或已保存项目，以及不显示窗口的检查和导出：

```powershell
uv run --locked tachie projects\u2501\u2501
uv run --locked tachie projects\u2501\u2501 --inspect
uv run --locked tachie projects\u2501\u2501 --psd .artifacts\u2501.psd
uv run --locked tachie editing.tachie.json --export .artifacts\exports
```

示例路径需替换为本地文件。可用 `--manifest` 指定依赖索引，`--verbose` 开启详细日志。终端 PSD 导出要求目标文件尚不存在；界面导出由文件对话框处理覆盖选择。

## 本地开发

代码位于 `src/`。模块职责和设计依据见 [ARCHITECTURE.md](ARCHITECTURE.md)，协作约定见 [AGENTS.md](AGENTS.md)。依赖由 `pyproject.toml` 和 `uv.lock` 管理；当前使用清华 PyPI 镜像，不建设 CI/CD、Git hooks 或发布流程。

```powershell
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked pyright
uv run --locked pytest -q
```

Qt 测试默认离屏运行。真实资源回归读取本地 `2b_2`、`u2501`、`yunxian_2`、`aijier_3` 及 `dependencies`，缺少素材时跳过；输出写入临时目录，不修改源资源。ADB 测试使用模拟接口，不访问设备。实际设备、游戏加载和 Photoshop 兼容性需单独实测。

Windows 标题栏检查需要原生窗口：

```powershell
$env:QT_QPA_PLATFORM="windows"
uv run --locked pytest -q tests/test_chrome.py
Remove-Item Env:QT_QPA_PLATFORM
```

### 更新翻译

英文文案写在源码中，中文译文位于 `src/ui/translations/zh_CN.ts`。修改文案后提取条目：

```powershell
$sources = Get-ChildItem src -Recurse -Filter *.py | ForEach-Object { $_.FullName }
uv run --locked pyside6-lupdate $sources -source-language en -target-language zh_CN -ts src/ui/translations/zh_CN.ts
```

补充译文后编译，并同时保留 `.ts` 与 `.qm` 的更新；普通启动不需要翻译工具：

```powershell
uv run --locked pyside6-lrelease src/ui/translations/zh_CN.ts -qm src/ui/translations/zh_CN.qm
```
