import arxiv
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any

from app.core.config import settings
from app.utils.logger import logger

class ArxivFetcher:
    def __init__(self):
        self.query = settings.ARXIV_QUERY
        self.client = arxiv.Client()

    def fetch_recent_papers(self, target_date: str = None) -> List[Dict[str, Any]]:
        """Fetch papers submitted on a specific date, or exactly 'yesterday' if no date provided.
        (Dates are matched according to arXiv's native timezone EST/EDT).
        """
        tz_arxiv = pytz.timezone('America/New_York')
        now_arxiv = datetime.now(tz_arxiv)
        
        if target_date:
            # Parse user-requested target date (e.g., "2026-02-27")
            target_start = tz_arxiv.localize(datetime.strptime(target_date, "%Y-%m-%d"))
        else:
            # Midnight today in arXiv time
            today_midnight = now_arxiv.replace(hour=0, minute=0, second=0, microsecond=0)
            target_start = today_midnight - timedelta(days=1)
            
        target_end_arxiv = target_start + timedelta(days=1)
        
        # Convert arXiv EST/EDT midnight boundaries to UTC for the query
        start_utc = target_start.astimezone(pytz.utc)
        end_utc = target_end_arxiv.astimezone(pytz.utc) - timedelta(minutes=1)
        
        start_date_str = start_utc.strftime("%Y%m%d%H%M")
        end_date_str = end_utc.strftime("%Y%m%d%H%M")
        
        date_query = f" AND submittedDate:[{start_date_str} TO {end_date_str}]"
        final_query = f"({self.query}){date_query}"
        
        target_display_str = target_start.strftime('%Y-%m-%d')
        logger.info(f"Checking arXiv date {target_display_str} with query: {final_query}")

        search = arxiv.Search(
            query=final_query,
            max_results=None,  
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        papers = []
        try:
            results = self.client.results(search)
            for r in results:
                paper_info = {
                    "id": r.entry_id.split('/')[-1],
                    "title": r.title,
                    "authors": ", ".join([a.name for a in r.authors]),
                    "abstract": r.summary.replace('\n', ' '),
                    "link": r.entry_id,
                    "pdf_url": r.pdf_url,
                    "published": r.published.isoformat()
                }
                papers.append(paper_info)
                
            logger.info(f"Found {len(papers)} papers on {target_display_str}.")
        except Exception as e:
            logger.error(f"Failed to fetch papers for {target_display_str}: {e}")
            
        return papers
