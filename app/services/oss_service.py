import oss2
import os
from app.core.config import settings
from app.utils.logger import logger

class OSSService:
    def __init__(self):
        self.access_key_id = settings.ALIYUN_OSS_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_OSS_ACCESS_KEY_SECRET
        self.endpoint = settings.ALIYUN_OSS_ENDPOINT
        self.bucket_name = settings.ALIYUN_OSS_BUCKET
        
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            logger.warning("ALIYUN_OSS 环境变量未完全配置，上传服务可能不可用")
            self.bucket = None
        else:
            try:
                auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            except Exception as e:
                logger.error(f"Failed to initialize OSS Bucket: {e}")
                self.bucket = None

    def put_object(self, object_name: str, content: str) -> str:
        """
        上传字符内容到 OSS，并返回可以直接访问的该文件的公网 URL 链接（假设 bucket 权限为公有读）
        """
        if not self.bucket:
            logger.error("OSS Bucket 未初始化，取消上传。")
            return ""
            
        try:
            # 根据用户要求，路径应当类似 oss://zhihuishu-meta/prod/html/summa-paper/{object_name}
            # 但是 bucket 级别通常不带前面的协议，只需要相对路径。
            # bucket_name = zhihuishu-meta. 所以 object_name 是 prod/html/summa-paper/...
            result = self.bucket.put_object(object_name, content.encode('utf-8'))
            if result.status == 200:
                # 生成期限为一个月的带签名 URL（因为用户希望尽量长，我们就给 30 天 = 2592000 秒）
                url = self.bucket.sign_url('GET', object_name, 2592000)
                logger.info(f"成功上传文件到 OSS: {url}")
                return url
            else:
                logger.error(f"OSS 上传失败，状态码: {result.status}")
                return ""
        except Exception as e:
            logger.error(f"上传文件到 OSS 时发生异常: {e}")
            return ""
