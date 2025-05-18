import uvicorn
from fastapi import FastAPI, Request, HTTPException
import requests
import logging
import json
import os
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 应用配置变量 - 将从 feishu_config.json 加载
FEISHU_APP_ID = None
FEISHU_APP_SECRET = None
FEISHU_CHAT_ID = None # 这是实际操作中使用的 current_chat_id
# DEFAULT_FEISHU_CHAT_ID 将从配置文件读取，不再硬编码

APP_CONFIG_FILE = "feishu_config.json" # 统一的配置文件

def load_app_config():
    global FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID
    config_loaded_successfully = False
    required_keys = ["feishu_app_id", "feishu_app_secret", "default_chat_id"]
    default_chat_id_from_config = None

    if os.path.exists(APP_CONFIG_FILE):
        try:
            with open(APP_CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            
            missing_keys = [key for key in required_keys if not config_data.get(key)]
            if missing_keys:
                logger.error(f"{APP_CONFIG_FILE} is missing required keys: {', '.join(missing_keys)}. Please check the file content.")
                return False

            FEISHU_APP_ID = config_data.get("feishu_app_id")
            FEISHU_APP_SECRET = config_data.get("feishu_app_secret")
            default_chat_id_from_config = config_data.get("default_chat_id")
            current_chat_id_from_file = config_data.get("feishu_chat_id")

            if current_chat_id_from_file:
                FEISHU_CHAT_ID = current_chat_id_from_file
                logger.info(f"Loaded feishu_chat_id from {APP_CONFIG_FILE}: {FEISHU_CHAT_ID}")
            elif default_chat_id_from_config:
                FEISHU_CHAT_ID = default_chat_id_from_config
                logger.info(f"feishu_chat_id not found in {APP_CONFIG_FILE}. Using default_chat_id: {FEISHU_CHAT_ID}. Saving it as feishu_chat_id.")
                config_data["feishu_chat_id"] = default_chat_id_from_config
                try:
                    with open(APP_CONFIG_FILE, 'w') as f_write:
                        json.dump(config_data, f_write, indent=2)
                    logger.info(f"Updated {APP_CONFIG_FILE} with feishu_chat_id set to default_chat_id.")
                except IOError as e_write:
                    logger.error(f"Error writing updated config to {APP_CONFIG_FILE}: {e_write}")
            else:
                logger.error(f"default_chat_id is also missing. Cannot determine chat_id.")
                return False

            logger.info(f"Successfully loaded App ID, App Secret, and Chat ID from {APP_CONFIG_FILE}.")
            config_loaded_successfully = True
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading {APP_CONFIG_FILE}: {e}. Please ensure it is valid JSON and contains required keys.")
    else:
        logger.error(f"{APP_CONFIG_FILE} not found. Please create it with feishu_app_id, feishu_app_secret, default_chat_id, and optionally feishu_chat_id.")
    
    return config_loaded_successfully

def save_current_chat_id_to_config(new_chat_id):
    global FEISHU_CHAT_ID
    current_config = {}
    if os.path.exists(APP_CONFIG_FILE):
        try:
            with open(APP_CONFIG_FILE, 'r') as f_read:
                current_config = json.load(f_read)
        except (json.JSONDecodeError, IOError) as e_read:
            logger.error(f"Error reading {APP_CONFIG_FILE} before saving new chat_id: {e_read}. Proceeding with new data.")
            current_config["feishu_app_id"] = FEISHU_APP_ID
            current_config["feishu_app_secret"] = FEISHU_APP_SECRET
    
    current_config["feishu_chat_id"] = new_chat_id
    if "feishu_app_id" not in current_config and FEISHU_APP_ID: current_config["feishu_app_id"] = FEISHU_APP_ID
    if "feishu_app_secret" not in current_config and FEISHU_APP_SECRET: current_config["feishu_app_secret"] = FEISHU_APP_SECRET
    if "default_chat_id" not in current_config and current_config.get("default_chat_id"):
        pass
    elif "default_chat_id" not in current_config:
        pass

    try:
        with open(APP_CONFIG_FILE, 'w') as f_write:
            json.dump(current_config, f_write, indent=2)
        FEISHU_CHAT_ID = new_chat_id
        logger.info(f"Saved new feishu_chat_id to {APP_CONFIG_FILE}: {FEISHU_CHAT_ID}")
    except IOError as e_write:
        logger.error(f"Error saving new feishu_chat_id to {APP_CONFIG_FILE}: {e_write}")

# Load all app configurations at startup
CONFIG_SUCCESSFULLY_LOADED = load_app_config()

# 缓存 tenant_access_token 及其过期时间
tenant_access_token_cache = {
    "token": None,
    "expires_at": 0
}

app = FastAPI()

async def get_tenant_access_token():
    """获取或刷新 tenant_access_token"""
    current_time = time.time()
    if tenant_access_token_cache["token"] and tenant_access_token_cache["expires_at"] > current_time:
        return tenant_access_token_cache["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 0:
            tenant_access_token_cache["token"] = data["tenant_access_token"]
            tenant_access_token_cache["expires_at"] = current_time + data.get("expire", 7200) - 300
            logger.info("成功获取 tenant_access_token")
            return data["tenant_access_token"]
        else:
            logger.error(f"获取 tenant_access_token 失败: {data.get('msg')}")
            return None
    except requests.RequestException as e:
        logger.error(f"请求 tenant_access_token 时发生网络错误: {e}")
        return None
    except Exception as e:
        logger.error(f"获取 tenant_access_token 时发生未知错误: {e}")
        return None

# async def list_bot_chats(): # <-- 函数 list_bot_chats 已注释掉
#     logger.info(\"开始尝试获取机器人所在的群聊列表...\")
#     access_token = await get_tenant_access_token()
#     if not access_token:
#         logger.error(\"无法获取 access_token，无法列出群聊。\")
#         return
# 
#     list_chats_url = \"https://open.feishu.cn/open-apis/im/v1/chats\"
#     headers = {
#         \"Authorization\": f\"Bearer {access_token}\",
#         \"Content-Type\": \"application/json; charset=utf-8\"
#     }
#     
#     params = {
#         \"page_size\": 100 # 您可以根据需要调整每页数量
#     }
# 
#     try:
#         response = requests.get(list_chats_url, headers=headers, params=params, timeout=10)
#         logger.debug(f\"飞书API响应状态码: {response.status_code}\")
#         logger.debug(f\"飞书API响应内容: {response.text}\") # 打印原始响应体
#         response.raise_for_status() # 如果状态码是 4xx 或 5xx，则抛出异常
#         data = response.json()
# 
#         if data.get(\"code\") == 0:
#             chats = data.get(\"data\", {}).get(\"items\", [])
#             if not chats:
#                 logger.info(\"机器人目前未加入任何群聊，或者API未能返回群聊列表。\")
#             else:
#                 logger.info(\"机器人所在的群聊列表：\")
#                 for chat in chats:
#                     chat_id = chat.get(\"chat_id\")
#                     chat_name = chat.get(\"name\", \"未知群名\")
#                     logger.info(f\"  群名: {chat_name}, Chat ID: {chat_id}\")
#             if data.get(\"data\", {}).get(\"has_more\"):
#                 logger.info(\"注意：群聊列表可能分页，当前只显示了第一页。如果未找到目标群聊，可能需要处理分页逻辑。\")
#         else:
#             logger.error(f\"获取群聊列表失败: {data.get('msg')}, code: {data.get('code')}\")
#             logger.error(f\"完整响应: {data}\")
# 
#     except requests.RequestException as e:
#         logger.error(f\"请求群聊列表时发生网络错误: {e}\")
#     except Exception as e:
#         logger.error(f\"处理群聊列表时发生未知错误: {e}\", exc_info=True)

@app.post("/webhook/feishu_events")
async def feishu_events_receiver(request: Request):
    global FEISHU_CHAT_ID
    try:
        payload = await request.json()
        logger.info(f"Received Feishu event on /webhook/feishu_events: {payload.get('header', {}).get('event_type')}")
    except Exception as e:
        logger.error(f"Cannot parse JSON from Feishu event: {e}")
        # Try to read body for challenge request even if JSON parsing fails initially for some reason
        try:
            raw_body = await request.body()
            body_str = raw_body.decode()
            logger.debug(f"Raw body for Feishu event: {body_str}")
            if 'challenge' in body_str: # Simplified check for challenge
                 payload_check = json.loads(body_str) # Attempt to parse again
                 if payload_check.get("type") == "url_verification":
                    logger.info("Received Feishu URL Verification (raw body parse)")
                    return {"challenge": payload_check.get("challenge")}
        except Exception as raw_e:
            logger.error(f"Error processing raw body for Feishu event: {raw_e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Handle URL Verification Challenge
    if payload.get("type") == "url_verification":
        logger.info("Received Feishu URL Verification for /webhook/feishu_events")
        challenge = payload.get("challenge")
        return {"challenge": challenge}

    # Handle Bot Added to Chat Event
    event_header = payload.get("header", {})
    if event_header.get("event_type") == "im.chat.member.bot.added_v1":
        event_data = payload.get("event", {})
        event_chat_id = event_data.get("chat_id")
        if event_chat_id:
            logger.info(f"Bot added to chat event received. Chat ID: {event_chat_id}")
            save_current_chat_id_to_config(event_chat_id) # 使用新的保存函数
            return {"status": "success", "message": f"FEISHU_CHAT_ID set to {event_chat_id} and saved."}
        else:
            logger.warning("Received 'im.chat.member.bot.added_v1' event but chat_id was missing.")
            return {"status": "warning", "message": "Chat ID missing in event."}
    
    logger.info(f"Ignored Feishu event type: {event_header.get('event_type')}")
    return {"status": "ignored", "message": "Event type not handled by this endpoint."}

@app.post("/webhook/github")
async def github_webhook_receiver(request: Request):
    if (not FEISHU_APP_ID or FEISHU_APP_ID.startswith("YOUR_") or
            not FEISHU_APP_SECRET or FEISHU_APP_SECRET.startswith("YOUR_")):
        logger.error("Feishu App ID or App Secret not configured properly.")
        raise HTTPException(status_code=500, detail="Feishu App ID or App Secret not configured properly.")

    if not FEISHU_CHAT_ID: # Check if CHAT_ID is set (either from config, event, or default load)
        logger.error("FEISHU_CHAT_ID is not set. Bot may need to be added to a chat, or config (feishu_config.json) is problematic.")
        raise HTTPException(status_code=500, detail="FEISHU_CHAT_ID is not set. Check configuration or bot events.")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"无法解析JSON负载: {e}")
        raise HTTPException(status_code=400, detail="无法解析JSON负载")

    event_type = request.headers.get("X-GitHub-Event")
    logger.info(f"接收到GitHub事件: {event_type}")

    if event_type == "push":
        try:
            repo_name = payload.get("repository", {}).get("full_name", "未知仓库")
            ref = payload.get("ref", "未知分支") 
            branch_name = ref.split("/")[-1] if ref else "未知分支"
            
            pusher_name = payload.get("pusher", {}).get("name", "未知推送者")
            
            commits = payload.get("commits", [])
            if not commits: 
                head_commit = payload.get("head_commit")
                if head_commit:
                    commit_message = head_commit.get("message", "无提交信息 (可能为创建/删除分支)")
                    commit_url = head_commit.get("url", "#")
                    commit_author = head_commit.get("author", {}).get("name", pusher_name)
                else:
                    commit_message = "无具体代码变更 (例如：分支创建/删除)"
                    commit_url = payload.get("compare", "#") 
                    commit_author = pusher_name
            else: 
                latest_commit = commits[-1] 
                commit_message = latest_commit.get("message", "无提交信息")
                commit_url = latest_commit.get("url", "#")
                commit_author = latest_commit.get("author", {}).get("name", "未知作者")

            message_lines = [
                f"📦 **仓库**: {repo_name}",
                f"🌿 **分支**: {branch_name}",
                f"👤 **提交者**: {commit_author} (推送者: {pusher_name})",
                f"💬 **信息**: {commit_message}",
                f"🔗 **详情**: {commit_url}"
            ]
            
            if len(commits) > 1:
                message_lines.append(f"✨ **总提交数**: {len(commits)}")
                compare_url = payload.get("compare")
                if compare_url:
                    message_lines.append(f"🔍 **查看所有变更**: {compare_url}")

            # --- 构建消息卡片 --- 
            card_elements = [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"📦 **仓库**: {repo_name}"}
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"🌿 **分支**: {branch_name}"}
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"👤 **提交者**: {commit_author}"}
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"💬 **信息**: {commit_message}"}
                },
                {
                    "tag": "action", # 使用 action 布局来放置链接按钮
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🔗 查看提交详情"},
                            "type": "default",
                            "url": commit_url
                        }
                    ]
                }
            ]

            if len(commits) > 1:
                card_elements.insert(4, { # 在提交信息和详情链接之间插入总提交数
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"✨ **总提交数**: {len(commits)}"}
                })
                compare_url_from_payload = payload.get("compare")
                if compare_url_from_payload:
                    card_elements.append({
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "🔍 查看所有变更"},
                                "type": "default",
                                "url": compare_url_from_payload
                            }
                        ]
                    })
            
            card_elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "💾 请及时拉取最新数据 git pull origin main"}
            })
            
            # 完整的消息卡片JSON对象 (content部分)
            feishu_card_content_obj = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "GitHub 项目更新通知"},
                    "template": "blue" # 可以尝试其他颜色如 green, orange, red, etc.
                },
                "elements": card_elements
            }
            # --- 消息卡片构建结束 ---
            
            access_token = await get_tenant_access_token()
            if not access_token:
                logger.error("Failed to get tenant_access_token for sending message.")
                raise HTTPException(status_code=500, detail="无法获取飞书 access_token")

            send_message_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8"
            }
            
            # Correctly create the JSON payload for Feishu API
            feishu_api_payload = {
                "receive_id": FEISHU_CHAT_ID,
                "msg_type": "interactive", # <--- 改为 interactive
                "content": json.dumps(feishu_card_content_obj) # <--- content 是卡片对象的JSON字符串
            }

            logger.info(f"准备通过API发送到飞书的消息 (卡片): {feishu_api_payload}")
            
            response = requests.post(send_message_url, headers=headers, json=feishu_api_payload, timeout=10)
            response.raise_for_status() # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
            response_data = response.json()

            if response_data.get("code") == 0:
                logger.info(f"成功通过API转发到飞书: {response.status_code} - {response_data}")
            else:
                logger.error(f"通过API发送到飞书失败: {response_data.get('msg')}, code: {response_data.get('code')}")
                raise HTTPException(status_code=500, detail=f"通过API发送到飞书失败: {response_data.get('msg')}")

            return {"status": "success", "message": "已成功通过API转发到飞书"}

        except HTTPException: # Re-raise HTTPException
            raise
        except Exception as e: # Catch other exceptions
            logger.error(f"处理push事件并发送到飞书时出错: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"处理并发送到飞书时出错: {str(e)}")

    elif event_type == "ping":
        logger.info("接收到GitHub Ping事件，测试连接成功。")
        return {"status": "success", "message": "Ping event received successfully"}
        
    else:
        logger.info(f"忽略非push事件: {event_type}")
        return {"status": "ignored", "message": f"已忽略事件类型: {event_type}"}

if __name__ == "__main__":
    if not CONFIG_SUCCESSFULLY_LOADED:
        logger.error("Application configuration failed to load. Please check feishu_config.json. Service will not start.")
    else:
        uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info") 