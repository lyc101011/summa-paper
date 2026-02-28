import json
import os
from datetime import datetime
from typing import Dict, Any, List

from app.utils.logger import logger
from app.core.config import settings

class StorageManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
    def _get_daily_dir(self, date_str: str) -> str:
        d = os.path.join(self.data_dir, date_str)
        os.makedirs(d, exist_ok=True)
        return d
        
    def _get_daily_papers_dir(self, date_str: str) -> str:
        d = os.path.join(self._get_daily_dir(date_str), "papers")
        os.makedirs(d, exist_ok=True)
        return d

    def _get_global_file_path(self) -> str:
        return os.path.join(self.data_dir, "all_papers.json")

    def load_daily_papers(self, date_str: str = None) -> Dict[str, Any]:
        """Load papers from a specific date's papers directory."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        papers_dir = self._get_daily_papers_dir(date_str)
        papers_dict = {}
        for filename in os.listdir(papers_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(papers_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # The real ID is in the data
                        if 'id' in data:
                            papers_dict[data['id']] = data
                except Exception as e:
                    logger.error(f"Failed to load {filename}: {e}")
        return papers_dict

    def save_daily_paper(self, paper_data: Dict[str, Any], date_str: str = None) -> str:
        """Save a single paper to the daily JSON directory and return its path."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        # Replace slashes in arxiv ID so it can be a valid filename (e.g. cs/0101001)
        safe_id = paper_data['id'].replace('/', '_')
        file_path = os.path.join(self._get_daily_papers_dir(date_str), f"{safe_id}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(paper_data, f, ensure_ascii=False, indent=4)
            return file_path
        except Exception as e:
            logger.error(f"Failed to save paper {safe_id} to {file_path}: {e}")
            return ""

    def save_daily_report(self, markdown_content: str, html_content: str, date_str: str = None):
        """Save the summary report and HTML into the daily folder."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        daily_dir = self._get_daily_dir(date_str)
        try:
            with open(os.path.join(daily_dir, "report.md"), 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            with open(os.path.join(daily_dir, "report.html"), 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Saved reports locally to {daily_dir}")
        except Exception as e:
            logger.error(f"Failed to save daily local reports: {e}")

    def load_global_papers(self) -> Dict[str, Any]:
        """Load all historically processed papers mapping paper ID to data."""
        file_path = self._get_global_file_path()
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load global papers from {file_path}: {e}")
                return {}
        return {}

    def save_global_papers(self, papers_dict: Dict[str, Any]):
        """Save a dictionary of all historically processed papers."""
        file_path = self._get_global_file_path()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(papers_dict, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save global papers to {file_path}: {e}")
