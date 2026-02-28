"""
大模型服务封装
纯 LLM 调用层，无业务逻辑
"""
from typing import Optional, Dict, Any
from app.core.config import settings
from app.utils.logger import logger
from app.utils.http_utils import AsyncHTTPClient


class LLMService:
    """大模型服务类（单例模式）- 纯 LLM 调用，无业务逻辑"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.base_url = settings.LLM_SERVICE_BASE_URL
        self.api_key = settings.API_KEY
        self.llm_model = settings.LLM_MODEL
        logger.info(f"[LLM] 初始化完成 | model={self.llm_model} | url={self.base_url}")
        self._initialized = True

    async def chat_completion(
        self,
        model: str,
        messages: list,
        response_format: Optional[Dict[str, Any]] = None,
        timeout: float = 300.0
    ) -> str:
        """
        通用 LLM 调用接口
        
        Args:
            model: 模型名称，如 "Claude Sonnet 4", "Claude Sonnet 4.5"
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            response_format: 响应格式，如 {"type": "json_object"}
            timeout: 超时时间（秒）
            
        Returns:
            str: 模型返回的原始文本内容
            
        Raises:
            Exception: 调用失败时抛出异常
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        if response_format:
            payload["response_format"] = response_format
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response_data = await AsyncHTTPClient.post(
                url=url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            # 解析响应
            if 'choices' in response_data and response_data['choices']:
                choice = response_data['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    content = choice['message']['content']
                    if content and content.strip():
                        return content
                    else:
                        logger.warning(f"[LLM] 返回内容为空字符串 | model={model}")
            
            logger.error(f"[LLM] 响应结构异常 | response_data={response_data}")
            raise Exception("大模型返回内容为空")
            
            raise
        except Exception as e:
            logger.error(f"[LLM] 调用失败 | model={model} | {e}")
            raise

    async def chat_completion_stream(
        self,
        model: str,
        messages: list,
        response_format: Optional[Dict[str, Any]] = None,
        timeout: float = 300.0
    ) -> str:
        """
        流式 LLM 调用接口 (Stream=True, 但一次性返回)
        用于避免长文本生成时的 HTTP 超时问题
        """
        import aiohttp
        import json
        
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True 
        }
        if response_format:
            payload["response_format"] = response_format
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Use aiohttp directly for streaming control
        client_timeout = aiohttp.ClientTimeout(total=timeout, sock_read=timeout)
        
        full_content = []
        
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[LLM] Stream请求失败 | {url} | {response.status}")
                        raise RuntimeError(f"HTTP请求失败: {response.status}, {error_text}")

                    # Process stream
                    async for line in response.content:
                        line = line.strip()
                        if not line:
                            continue
                        
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line.startswith('data:'):
                            data_str = decoded_line[5:].strip() # Removing "data:"
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data_json = json.loads(data_str)
                                if 'choices' in data_json and data_json['choices']:
                                    choice = data_json['choices'][0]
                                    # Try delta (standard) or message (custom/observed)
                                    delta = choice.get('delta', {})
                                    content = delta.get('content')
                                    
                                    if content is None:
                                        message_body = choice.get('message', {})
                                        content = message_body.get('content')

                                    if content:
                                        full_content.append(content)
                            except Exception as e:
                                logger.warning(f"[LLM] Stream解析行失败: {e} | line={data_str}")
                                continue
            
            result_text = "".join(full_content)
            if not result_text:
                 raise Exception("大模型返回内容为空 (Stream)")
            
            return result_text

        except Exception as e:
            logger.error(f"[LLM] Stream调用失败 | model={model} | {e}")
            raise
