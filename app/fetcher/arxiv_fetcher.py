import arxiv
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any

from app.core.config import settings
from app.utils.logger import logger

class ArxivFetcher:
    def __init__(self):
        self.query = settings.ARXIV_QUERY
        self.max_results = settings.ARXIV_MAX_RESULTS
        self.client = arxiv.Client()

    def fetch_recent_papers(self) -> List[Dict[str, Any]]:
        """Fetch papers from the last 24-48 hours."""
        logger.info(f"Fetching recent papers for query: {self.query}")
        search = arxiv.Search(
            query=self.query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        papers = []
        try:
            results = list(self.client.results(search))
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
            logger.info(f"Successfully fetched {len(papers)} papers.")
        except Exception as e:
            logger.error(f"Failed to fetch papers: {e}")
            
        return papers
