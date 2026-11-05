import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any
import pandas as pd

from config.settings import settings
from src.crawler.engine import ResilientCrawlerEngine
from src.agents.crew_pipeline import IntelligenceOutreachCrew
from src.pipeline.exporter import OutreachDataExporter

logger = logging.getLogger("BatchProcessor")

class BatchPipelineRunner:
    def __init__(
        self,
        concurrency: int = settings.CRAWLER_CONCURRENCY,
        rate_limit_delay: float = settings.RATE_LIMIT_DELAY_SECONDS,
        language: str = settings.DEFAULT_OUTREACH_LANGUAGE
    ):
        self.concurrency = concurrency
        self.rate_limit_delay = rate_limit_delay
        self.language = language
        self.crawler = ResilientCrawlerEngine(concurrency=concurrency)
        self.crew_pipeline = IntelligenceOutreachCrew()
        self.logs_dir = settings.LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def load_domains_from_csv(self, csv_file_path: Path) -> List[str]:
        """
        Loads and auto-detects the domain column in any user-supplied CSV.
        """
        df = pd.read_csv(csv_file_path)
        possible_cols = ["domain", "url", "website", "company_domain", "site", "target"]
        
        target_col = None
        for col in df.columns:
            if col.strip().lower() in possible_cols:
                target_col = col
                break

        if not target_col:
            # Fallback to the first column
            target_col = df.columns[0]
            logger.warning(f"Could not find standard domain column. Defaulting to first column: '{target_col}'")

        domains = df[target_col].dropna().astype(str).str.strip().tolist()
        # Filter empty lines
        domains = [d for d in domains if d and not d.startswith("#")]
        return list(dict.fromkeys(domains))  # Deduplicate while preserving order

    async def process_single_domain(self, domain: str) -> Dict[str, Any]:
        """
        Runs the full end-to-end pipeline for one domain:
        Crawling -> Multi-page Aggregation -> Multi-Agent Analysis & Copywriting -> Result Record.
        """
        record: Dict[str, Any] = {
            "Domain": domain,
            "Company_Name": "",
            "Business_Model": "",
            "Target_Audience": "",
            "Identified_Pain_Point": "",
            "Evidence_Snippet": "",
            "Matched_Service": "",
            "Personalized_Subject_1": "",
            "Personalized_Subject_2": "",
            "Email_Body_Draft": "",
            "Hook_Sentence": "",
            "Value_Sentence": "",
            "Soft_CTA": "",
            "Confidence_Score": 0.0,
            "Status": "PENDING",
            "Pages_Crawled": 0,
            "Error_Message": ""
        }

        try:
            # Step 1: Resilient Crawl
            crawl_bundle = await self.crawler.crawl_domain(domain)
            record["Pages_Crawled"] = len(crawl_bundle.crawled_pages)

            if not crawl_bundle.success or not crawl_bundle.combined_markdown.strip():
                record["Status"] = "FAILED"
                record["Error_Message"] = crawl_bundle.error_message or "Crawling yielded no semantic content."
                self._log_error(domain, record["Error_Message"])
                return record

            # Step 2: Multi-Agent Crew
            intel, matched, draft = self.crew_pipeline.run_pipeline(
                domain=domain,
                crawled_markdown=crawl_bundle.combined_markdown,
                language=self.language
            )

            # Step 3: Populate flat record
            record["Company_Name"] = intel.company_name
            record["Business_Model"] = intel.business_model
            record["Target_Audience"] = intel.target_audience
            
            if intel.identified_pain_points:
                primary_pain = intel.identified_pain_points[0]
                record["Identified_Pain_Point"] = primary_pain.description
                record["Evidence_Snippet"] = primary_pain.evidence_quote
            else:
                record["Identified_Pain_Point"] = "Operational & pipeline scalability"

            record["Matched_Service"] = matched.service_title
            record["Personalized_Subject_1"] = draft.subject_line_1
            record["Personalized_Subject_2"] = draft.subject_line_2
            record["Email_Body_Draft"] = draft.full_email_body
            record["Hook_Sentence"] = draft.hook_paragraph
            record["Value_Sentence"] = draft.value_paragraph
            record["Soft_CTA"] = draft.cta_paragraph
            record["Confidence_Score"] = draft.confidence_score
            record["Status"] = "SUCCESS"

        except Exception as e:
            record["Status"] = "FAILED"
            record["Error_Message"] = f"Pipeline unhandled error: {str(e)}"
            self._log_error(domain, record["Error_Message"])

        return record

    async def run_batch(
        self,
        domains: List[str],
        output_name: str = "batch_campaign",
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Processes a list of domains concurrently up to `self.concurrency`
        with rate-limiting and live progress updates.
        """
        results: List[Dict[str, Any]] = []
        total = len(domains)
        completed = 0
        success_count = 0
        failed_count = 0

        semaphore = asyncio.Semaphore(self.concurrency)

        async def worker(dom: str):
            nonlocal completed, success_count, failed_count
            async with semaphore:
                rec = await self.process_single_domain(dom)
                results.append(rec)
                completed += 1
                if rec["Status"] == "SUCCESS":
                    success_count += 1
                else:
                    failed_count += 1

                if progress_callback:
                    progress_callback(completed, total, rec)

                # Rate-limiting pause between domains
                if self.rate_limit_delay > 0:
                    await asyncio.sleep(self.rate_limit_delay)

        tasks = [asyncio.create_task(worker(d)) for d in domains]
        await asyncio.gather(*tasks)

        # Export results
        export_files = OutreachDataExporter.export(
            records=results,
            output_name=output_name,
            formats=["csv", "xlsx", "json"]
        )

        return {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "exported_files": export_files,
            "results": results
        }

    def _log_error(self, domain: str, error_msg: str):
        error_file = self.logs_dir / "failed_domains.jsonl"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "domain": domain,
            "error": error_msg
        }
        with open(error_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
