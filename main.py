import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz

from fastapi import FastAPI, BackgroundTasks, Query
from contextlib import asynccontextmanager
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tqdm import tqdm

from app.core.config import settings
from app.utils.logger import logger
from app.utils.storage import StorageManager
from app.fetcher.arxiv_fetcher import ArxivFetcher
from app.processor.paper_processor import PaperProcessor
from app.services.feishu_service import FeishuService
from app.services.oss_service import OSSService

class DailyAgent:
    def __init__(self):
        self.storage = StorageManager()
        self.fetcher = ArxivFetcher()
        self.processor = PaperProcessor()
        self.feishu = FeishuService()
        self.oss = OSSService()
        self.is_running = False

    async def run(self, target_date: Optional[str] = None):
        if self.is_running:
            logger.warning("Agent 任务正在执行中，跳过本次触发。")
            return
        self.is_running = True
        try:
            await self._do_run(target_date)
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise e
        finally:
            self.is_running = False

    async def _do_run(self, target_date: Optional[str] = None):
        logger.info("=== 启动 Daily Arxiv Agent ===")
        
        if not target_date:
            # 默认抓取前一天的论文（取决于当前时间，通常arxiv的更新在 UTC 晚间，这里以当前日期为例）
            # 由于 arXiv API 查的是 past 24-48 hours，用今天或昨天都能做 storage key
            # 用户要求默认前一天，我们在 storage key 里标前一天
            from datetime import timedelta
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%Y-%m-%d")
        else:
            date_str = target_date
        
        # 1. 加载历史所有已处理文献以及今日进度
        global_papers = self.storage.load_global_papers()
        processed_data = self.storage.load_daily_papers(date_str)
        
        # 2. 从 Arxiv 获取新论文
        raw_papers = self.fetcher.fetch_recent_papers(target_date=date_str)
        if not raw_papers:
            logger.info("今日未获取到新论文。")
            empty_msg = "今日 arXiv 未发布相关领域的新论文，或全天无更新。"
            self.storage.save_daily_report(empty_msg, "", date_str)
            await self.feishu.send_markdown(f"Arxiv 每日精选 - {date_str}", empty_msg)
            logger.info("=== Daily Arxiv Agent 查无记录，执行完毕 ===")
            return
            
        high_quality_papers = []
        
        # 3. 处理论文（过滤与提取）
        for paper in tqdm(raw_papers, desc=f"Processing {len(raw_papers)} papers"):
            paper_id = paper['id']
            
            # 检查是否曾在历史中处理过并且成功
            cached_file_path = global_papers.get(paper_id)
            if cached_file_path:
                # 若缓存的路径是之前的日期，说明是历史记录，无需加入今天的报表
                if date_str not in cached_file_path:
                    logger.debug(f"论文 {paper_id} 属于跨日历史记录，直接跳过。")
                    continue
                    
                # Load the specific daily file where this paper was processed
                import os
                if os.path.exists(cached_file_path):
                    with open(cached_file_path, 'r', encoding='utf-8') as f:
                        import json
                        historical_data = json.load(f)
                        
                        # 兼容旧的文件级和新的单文件级缓存
                        if "id" in historical_data and "status" in historical_data:
                            result = historical_data
                        else:
                            result = historical_data.get(paper_id)
                        
                        if result and result.get("status") != "error" and not str(result.get("analysis_text", "")).startswith("Processing Error"):
                            logger.info(f"论文 {paper_id} 已在历史记录 {cached_file_path} 中且处理成功，跳过大模型调用。")
                            processed_data[paper_id] = result
                            
                            if result.get("is_worth_reading", False):
                                high_quality_papers.append(result)
                            continue
            
            # 如果没跳过（没处理过或报错了），则调用大模型处理
            result = await self.processor.process_paper(paper)
            # 记录原始元数据
            result.update({
                "id": paper_id,
                "title": paper["title"],
                "link": paper["link"],
                "pdf_url": paper["pdf_url"],
                "processed_date": date_str
            })
                
            # 更新全局归档记录 (只记文件路径以节省空间)
            # The global dict now points to the individual daily json files.
            saved_path = self.storage.save_daily_paper(result, date_str)
            global_papers[paper_id] = saved_path if saved_path else f"data/{date_str}/papers/{paper_id}.json"
            self.storage.save_global_papers(global_papers)
            
            # 记录今天的处理结果以便后续调用
            processed_data[paper_id] = result
            
            if result.get("is_worth_reading", False):
                high_quality_papers.append(result)
                
        # 4. 生成报告 (Markdown 简版 只含推荐, HTML 完整版含所有已处理的)
        logger.info(f"共有 {len(high_quality_papers)} 篇高质量论文，开始调用大模型生成总结报告。")
        
        # Sort papers for HTML: Passed ones first, then rejected ones
        all_processed_today = list(processed_data.values())
        all_processed_today.sort(key=lambda x: not x.get('is_worth_reading', False))
        
        html_report = await self.processor.generate_html_report(all_processed_today)
        
        # 5. 上传 HTML 报告到阿里云 OSS
        oss_url = ""
        if html_report and "生成 HTML 日报时发生错误" not in html_report:
            # 文件名按日期和时间戳，避免冲突
            timestamp = datetime.now().strftime("%H%M%S")
            object_name = f"prod/html/summa-paper/{date_str}_{timestamp}.html"
            oss_url = self.oss.put_object(object_name, html_report)
            
        # 6. 生成极简版飞书 Markdown 消息，附带 OSS 链接
        papers_context_for_feishu = self.processor._format_papers_context(high_quality_papers)
        # We append the OSS URL context so the LLM knows what link to refer to
        if oss_url:
            papers_context_for_feishu += f"\n\n完整 HTML 深度评测报告链接（请务必在生成文案结尾附上此地址供大家点击阅读）: {oss_url}"
            
        from app.core.prompts import REPORT_GENERATOR_PROMPT
        prompt = REPORT_GENERATOR_PROMPT.format(papers_content=papers_context_for_feishu)
        try:
            markdown_summary = await self.processor.llm_service.chat_completion_stream(
                model=self.processor.llm_service.llm_model,
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as e:
            logger.error(f"Error generating batch Feishu report: {e}")
            markdown_summary = f"生成极简日报时发生错误：{e}\n\n完整报告请查看: {oss_url}"
        
        # 7. 保存生成的报告文件到本地目录中
        self.storage.save_daily_report(markdown_summary, html_report, date_str)
        
        # 8. 发送至飞书
        title = f"Arxiv 每日精选 - {date_str}"
        await self.feishu.send_markdown(title, markdown_summary)
        
        logger.info("=== Daily Arxiv Agent 执行完毕 ===")

agent = DailyAgent()
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Shanghai'))

async def scheduled_job():
    """Timer job for apscheduler to trigger agent run."""
    logger.info("Scheduler triggered daily arXiv extraction.")
    await agent.run()

async def check_daily_task_job():
    """Run every 15 minutes to check if today's task is completed."""
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    
    # 早于 13:00 时暂不执行补偿（主任务设在 12:00，留一小时完成窗口）
    if now.hour < 13:
        return
    
    from datetime import timedelta
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    import os
    daily_dir = agent.storage._get_daily_dir(yesterday_str)
    report_path = os.path.join(daily_dir, "report.md")
    
    if not os.path.exists(report_path):
        if not getattr(agent, "is_running", False):
            logger.info(f"15分钟巡检: 检测到今日报表 {report_path} 未生成，且系统未在运行，已触发补偿执行。")
            await agent.run(yesterday_str)
        else:
            logger.info("15分钟巡检: 任务正在执行中，无需补偿。")
    else:
        logger.debug("15分钟巡检: 今日任务已顺利完成。")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the background scheduler on app startup and shutdown."""
    # Example: Run every day at 12:00 PM Shanghai time
    scheduler.add_job(scheduled_job, 'cron', hour=12, minute=0)
    
    # 增加 15 分钟补偿检查任务
    scheduler.add_job(check_daily_task_job, 'interval', minutes=15)
    
    scheduler.start()
    logger.info("APScheduler started: daily arxiv task scheduled at 12:00 PM, with 15-minute compensation checks.")
    
    # 检查补偿逻辑：如果当前时间大于 13 点且昨天的论文还没处理过，立即触发一次
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    if now.hour >= 13:
        from datetime import timedelta
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 判断昨天的记录是否存在
        import os
        daily_dir = agent.storage._get_daily_dir(yesterday)
        report_path = os.path.join(daily_dir, "report.md")
        if not os.path.exists(report_path):
            logger.info("Startup Check: missed today's 09:00 AM run. Triggering recovery run now for yesterday's papers.")
            asyncio.create_task(agent.run(yesterday))
        else:
            logger.info("Startup Check: today's run was already completed.")
            
    yield
    
    # Shutdown
    scheduler.shutdown()
    logger.info("APScheduler stopped.")

app = FastAPI(title="Arxiv Summary Agent API", lifespan=lifespan)

@app.post("/api/run")
async def trigger_agent(
    background_tasks: BackgroundTasks, 
    target_date: Optional[str] = Query(None, description="目标日期格式: YYYY-MM-DD，默认前一天")
):
    """
    手动触发 Arxiv 论文抓取与分析任务。
    任务会在后台异步执行。
    """
    background_tasks.add_task(agent.run, target_date)
    return {"status": "success", "message": f"任务已在后台启动，目标日期: {target_date or '默认(前一天)'}"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
