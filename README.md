# GitHub 通知转发飞书机器人

这是一个 Python 脚本，它运行一个 FastAPI Web 服务，用于接收来自 GitHub 的 Webhook 通知（例如代码推送），并将格式化后的消息通过指定的飞书应用机器人转发到飞书群聊中。

## 功能特性

- 接收 GitHub Webhook 事件 (目前主要处理 `push` 和 `ping` 事件)。
- 提取关键信息：仓库名称、分支、提交者、提交信息和提交链接。
- 将信息格式化为飞书消息卡片进行发送。
- 通过飞书应用机器人将消息卡片发送到预配置的飞书群聊。
- 自动处理飞书应用 `tenant_access_token` 的获取和缓存。
- 支持通过飞书事件回调自动检测并保存 `chat_id`：监听 `im.chat.member.bot.added_v1` 事件（机器人被添加到新群时），并将新的 `chat_id` 更新到配置文件中。
- 所有配置（包括 App ID, App Secret, 默认 Chat ID, 当前 Chat ID）均存储在 `feishu_config.json` 文件中。
- （可选）包含 `systemd` 服务文件示例，用于在 Linux 上将脚本作为后台服务运行并开机自启。

## 环境准备

- Python 3.8 或更高版本
- pip (Python 包安装器)

## 安装依赖

```bash
# 建议在虚拟环境中安装
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

pip install fastapi uvicorn requests
```

## 配置步骤

1.  **创建飞书应用机器人**:
    *   在飞书开放平台创建一个新的"应用机器人"。
    *   记下其 `App ID` 和 `App Secret`。
    *   确保机器人应用已发布，并具备发送消息到群聊的权限。

2.  **创建并配置 `feishu_config.json` 文件**:
    在项目根目录下创建一个名为 `feishu_config.json` 的文件。该文件用于存储所有必要的配置信息。
    文件内容应如下所示，请将占位符替换为您的实际值：
    ```json
    {
      "app_id": "YOUR_FEISHU_APP_ID_HERE",
      "app_secret": "YOUR_FEISHU_APP_SECRET_HERE",
      "default_chat_id": "YOUR_DEFAULT_FALLBACK_CHAT_ID_HERE",
      "current_chat_id": "YOUR_INITIAL_CURRENT_CHAT_ID_HERE" 
    }
    ```
    *   `app_id`: 您的飞书应用 App ID。
    *   `app_secret`: 您的飞书应用 App Secret。
    *   `default_chat_id`: 一个备用的 Chat ID。如果 `current_chat_id` 因故无法确定，将使用此 ID。
    *   `current_chat_id`: 机器人当前实际发送消息的目标群聊 ID。初始时可以和 `default_chat_id` 相同。当机器人被添加到新群聊并成功处理事件后，此值会自动更新。

3.  **配置飞书事件订阅 (用于自动更新 `current_chat_id`)**:
    *   在您的飞书应用"事件与回调"设置中，找到"事件订阅"部分。
    *   将"请求地址 URL"设置为 `http://<您的服务器IP或域名>:<端口号>/webhook/feishu_events` (例如 `http://your.domain.com:8002/webhook/feishu_events`)。
    *   订阅"机器人进群"事件 (`im.chat.member.bot.added_v1`)。

4.  **配置 GitHub Webhook**:
    *   在您的 GitHub 仓库的 "Settings" -> "Webhooks" 页面，添加一个新的 Webhook。
    *   **Payload URL**: `http://<您的服务器IP或域名>:<端口号>/webhook/github` (例如 `http://your.domain.com:8002/webhook/github`)。
    *   **Content type**: 选择 `application/json`。
    *   **Secret**: (可选，但推荐) 设置一个密钥。脚本目前未校验，如需校验可自行添加逻辑。
    *   **Which events would you like to trigger this webhook?**: 至少选择 "Pushes"。您也可以选择 "Send me everything"。

## 运行服务

```bash
# 确保已在虚拟环境中并安装了依赖
source venv/bin/activate # (如果尚未激活)
python main.py
```
默认情况下，服务将使用 Uvicorn 运行在 `0.0.0.0:8002` (端口号可在 `main.py` 的 `uvicorn.run` 中修改)。

## (可选) Systemd 服务配置 (Linux)

可以将此脚本配置为 `systemd` 服务，以实现开机自启和后台运行。服务文件示例 (`github-webhook.service`) 的创建方法在之前的讨论中已提供。主要配置项包括工作目录、执行命令（使用虚拟环境中的Python）和运行用户。

## 使用说明

配置并启动服务后，当您向已配置 Webhook 的 GitHub 仓库推送代码时，机器人会自动将包含相关更新信息的卡片消息发送到指定的飞书群聊中。
如果机器人被添加到新的群聊，并且飞书事件订阅配置正确，`feishu_config.json` 中的 `current_chat_id` 将会自动更新为新群聊的 ID。 