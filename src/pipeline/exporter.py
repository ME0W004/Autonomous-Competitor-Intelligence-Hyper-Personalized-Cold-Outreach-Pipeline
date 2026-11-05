import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

from config.settings import settings

logger = logging.getLogger("Exporter")

class OutreachDataExporter:
    """
    Exports processed B2B intelligence and cold outreach drafts into industry-standard
    formats directly ingestible by Instantly, Smartlead, Lemlist, and Apollo.
    """

    @staticmethod
    def export(
        records: List[Dict[str, Any]],
        output_name: str = "outreach_campaign",
        formats: List[str] = ["csv", "xlsx", "json"]
    ) -> Dict[str, Path]:
        """
        Exports the list of processed records to specified formats in data/output.
        """
        output_dir = settings.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{output_name}_{timestamp}"
        exported_files = {}

        # Convert to DataFrame
        df = pd.DataFrame(records)

        # Standardize column names for cold outreach platforms
        standard_cols_order = [
            "Domain",
            "Company_Name",
            "Business_Model",
            "Target_Audience",
            "Identified_Pain_Point",
            "Evidence_Snippet",
            "Matched_Service",
            "Personalized_Subject_1",
            "Personalized_Subject_2",
            "Email_Body_Draft",
            "Hook_Sentence",
            "Value_Sentence",
            "Soft_CTA",
            "Confidence_Score",
            "Status",
            "Pages_Crawled",
            "Error_Message"
        ]

        # Reorder existing columns and keep any extra ones
        ordered_cols = [c for c in standard_cols_order if c in df.columns]
        extra_cols = [c for c in df.columns if c not in standard_cols_order]
        df = df[ordered_cols + extra_cols]

        if "csv" in formats:
            csv_path = output_dir / f"{base_filename}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            exported_files["csv"] = csv_path
            logger.info(f"[+] Exported CSV to: {csv_path}")

        if "xlsx" in formats:
            xlsx_path = output_dir / f"{base_filename}.xlsx"
            df.to_excel(xlsx_path, index=False, engine="openpyxl")
            exported_files["xlsx"] = xlsx_path
            logger.info(f"[+] Exported Excel to: {xlsx_path}")

        if "json" in formats:
            json_path = output_dir / f"{base_filename}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            exported_files["json"] = json_path
            logger.info(f"[+] Exported JSON to: {json_path}")

        return exported_files
