import json
from typing import Dict, Any, List

from app.core.config import settings
from app.utils.logger import logger
from app.utils.http_utils import AsyncHTTPClient

class FeishuService:
    def __init__(self):
        self.webhook_url = settings.FEISHU_WEBHOOK_URL

    async def send_markdown(self, title: str, markdown_content: str) -> bool:
        """
        Sends a Markdown message to a Feishu bot webhook.
        """
        if not self.webhook_url or "your_webhook_token_here" in self.webhook_url:
            logger.warning("Feishu webhook URL not configured properly, skipping send.")
            return False

        logger.info(f"Sending report to Feishu: {title}")
        
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [
                            [
                                {
                                    "tag": "text",
                                    "text": markdown_content
                                }
                            ]
                        ]
                    }
                }
            }
        }

        try:
            # We use an interactive card or post to render Markdown
            payload_interactive = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "template": "blue",
                        "title": {
                            "content": title,
                            "tag": "plain_text"
                        }
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": markdown_content
                        }
                    ]
                }
            }
            
            response = await AsyncHTTPClient.post(
                url=self.webhook_url,
                json=payload_interactive
            )
            
            if response.get("code") == 0:
                logger.info("Successfully sent message to Feishu.")
                return True
            else:
                logger.error(f"Feishu return code error: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send message to Feishu: {e}")
            return False
