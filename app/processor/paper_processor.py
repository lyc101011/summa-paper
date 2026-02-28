import json
from typing import Dict, Any, List

from app.core.prompts import SYSTEM_PROMPT, FILTER_AND_EXTRACT_PROMPT
from app.services.llm_service import LLMService
from app.utils.logger import logger

class PaperProcessor:
    def __init__(self):
        self.llm_service = LLMService()

    async def process_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single paper: filters it and extracts insights.
        """
        title = paper.get('title', 'Unknown Title')
        logger.info(f"Processing paper: {title}")
        
        prompt = FILTER_AND_EXTRACT_PROMPT.format(
            title=title,
            authors=paper.get('authors', 'Unknown Authors'),
            abstract=paper.get('abstract', 'No Abstract'),
            link=paper.get('link', 'No Link'),
            pdf_url=paper.get('pdf_url', 'No PDF Link')
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # We are expecting text output describing the deep review
            response = await self.llm_service.chat_completion(
                model=self.llm_service.llm_model,
                messages=messages
            )
            
            # Parse the strict token required from the Area Chair prompt
            is_worth_reading = "[PASSED]" in response

            return {
                "status": "success",
                "is_worth_reading": is_worth_reading,
                "analysis_text": response
            }
        except Exception as e:
            logger.error(f"Error processing paper '{title}': {e}")
            return {
                "status": "error",
                "is_worth_reading": False,
                "analysis_text": f"Processing Error: {e}"
            }

    async def generate_batch_report(self, summarized_papers: List[Dict[str, Any]]) -> str:
        """
        Takes the filtered papers and their analysis, and calls the LLM to generate a final markdown report.
        """
        if not summarized_papers:
            return "今日没有值得推荐的论文。"
            
        logger.info(f"Generating batch report for {len(summarized_papers)} papers...")
        
        # Format the papers into a long string for the batch prompt
        papers_context = self._format_papers_context(summarized_papers)

        from app.core.prompts import REPORT_GENERATOR_PROMPT
        prompt = REPORT_GENERATOR_PROMPT.format(papers_content=papers_context)
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.llm_service.chat_completion(
                model=self.llm_service.llm_model,
                messages=messages
            )
            return response
        except Exception as e:
            logger.error(f"Error generating batch Feishu report: {e}")
            return f"生成精简日报时发生错误：{e}"

    async def generate_html_report(self, summarized_papers: List[Dict[str, Any]]) -> str:
        """
        Takes the filtered papers and their analysis, and calls the LLM to generate a full static HTML report.
        """
        if not summarized_papers:
            return "<html><body><h1>今日没有值得推荐的论文</h1></body></html>"
            
        logger.info(f"Generating HTML report for {len(summarized_papers)} papers...")
        papers_context = self._format_papers_context(summarized_papers)
        
        from app.core.prompts import HTML_GENERATOR_PROMPT
        prompt = HTML_GENERATOR_PROMPT.format(papers_content=papers_context)
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await self.llm_service.chat_completion(
                model=self.llm_service.llm_model,
                messages=messages
            )
            
            # Clean up potential markdown formatting from LLM response
            if response.startswith("```html"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return f"<html><body><h1>生成 HTML 日报时发生错误：{e}</h1></body></html>"
            
    def _format_papers_context(self, summarized_papers: List[Dict[str, Any]]) -> str:
        papers_context = ""
        for idx, paper in enumerate(summarized_papers, 1):
            papers_context += f"## 候选论文 {idx}\n"
            papers_context += f"标题: {paper.get('title')}\n"
            papers_context += f"Arxiv 链接: {paper.get('link')}\n"
            papers_context += f"PDF 链接: {paper.get('pdf_url')}\n"
            papers_context += f"初步评估结果:\n{paper.get('analysis_text')}\n\n"
            papers_context += "--------------------------------------------------\n"
        return papers_context
