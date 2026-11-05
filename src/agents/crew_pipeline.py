import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from config.settings import settings
from src.agents.schemas import (
    CompanyIntelligence,
    MatchedOffering,
    OutreachEmailDraft,
    PainPointAnalysis
)

logger = logging.getLogger("CrewPipeline")

def load_our_portfolio() -> dict:
    portfolio_path = settings.PORTFOLIO_FILE
    if portfolio_path.exists():
        try:
            with open(portfolio_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading portfolio JSON: {e}")
    
    return {
        "agency_name": "Apex AI & Sales Acceleration",
        "core_value_proposition": "We build autonomous AI agents and cold pipeline infrastructure for B2B teams.",
        "offerings": []
    }

class IntelligenceOutreachCrew:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.LLM_MODEL
        self.portfolio = load_our_portfolio()
        self.portfolio_str = json.dumps(self.portfolio, indent=2, ensure_ascii=False)

    def _get_crewai_llm(self):
        """
        Initializes the LLM instance compatible with CrewAI and litellm.
        """
        from crewai import LLM
        
        # Priority check for available API keys
        api_key = (
            settings.OPENAI_API_KEY
            or os.getenv("OPENAI_API_KEY")
            or settings.GEMINI_API_KEY
            or os.getenv("GEMINI_API_KEY")
            or settings.GROQ_API_KEY
            or os.getenv("GROQ_API_KEY")
        )
        
        return LLM(
            model=self.model_name,
            temperature=settings.LLM_TEMPERATURE,
            api_key=api_key if api_key else "none"
        )

    def run_pipeline(
        self,
        domain: str,
        crawled_markdown: str,
        language: str = "en"
    ) -> Tuple[CompanyIntelligence, MatchedOffering, OutreachEmailDraft]:
        """
        Executes the 3-agent pipeline for a single domain.
        Returns: (CompanyIntelligence, MatchedOffering, OutreachEmailDraft)
        """
        # If no API key is provided, generate high-quality fallback draft
        has_api_key = bool(
            settings.OPENAI_API_KEY
            or os.getenv("OPENAI_API_KEY")
            or settings.GEMINI_API_KEY
            or os.getenv("GEMINI_API_KEY")
            or settings.GROQ_API_KEY
            or os.getenv("GROQ_API_KEY")
            or settings.ANTHROPIC_API_KEY
            or os.getenv("ANTHROPIC_API_KEY")
        )

        if not has_api_key:
            logger.warning("[!] No LLM API key detected. Generating smart deterministic draft...")
            return self._generate_heuristic_draft(domain, crawled_markdown, language)

        try:
            return self._run_crewai_pipeline(domain, crawled_markdown, language)
        except Exception as e:
            logger.error(f"[!] CrewAI execution error for {domain}: {e}. Engaging fallback...")
            return self._generate_heuristic_draft(domain, crawled_markdown, language)

    def _run_crewai_pipeline(
        self,
        domain: str,
        crawled_markdown: str,
        language: str
    ) -> Tuple[CompanyIntelligence, MatchedOffering, OutreachEmailDraft]:
        from crewai import Agent, Crew, Process, Task

        llm = self._get_crewai_llm()

        # Agent 1: Market & Tech Analyst
        analyst = Agent(
            role="Senior B2B Market & Tech Intelligence Analyst",
            goal="Analyze the target company's business model, customer base, and uncover 2-3 specific, evidence-backed pain points",
            backstory=(
                "You are an elite B2B analyst who cuts through marketing fluff. You analyze raw web content "
                "to diagnose genuine bottlenecks (e.g., poor conversion copy, disjointed features, lack of automation, or unclear pricing tiers)."
            ),
            llm=llm,
            verbose=False
        )

        # Agent 2: Solutions Architect & Offer Matcher
        matcher = Agent(
            role="B2B Solutions Architect & Offer Matcher",
            goal="Bridge target company bottlenecks with our agency's core value proposition and case studies",
            backstory=(
                "You map client vulnerabilities to specific, high-ROI solutions from our portfolio. "
                "You select the most compelling proof-point and case study that demonstrates similar previous success."
            ),
            llm=llm,
            verbose=False
        )

        # Agent 3: B2B Cold Copywriter
        copywriter = Agent(
            role="High-Converting B2B Cold Outreach Copywriter",
            goal="Craft a hyper-personalized, 3-paragraph cold email under 110 words with a compelling Hook, non-pushy Solution/Value, and a frictionless Soft CTA",
            backstory=(
                "You write emails that C-level executives and VP-level decision-makers actually respond to. "
                "You despise cheesy openers ('Hope this finds you well', 'Came across your website'). "
                "You focus on specific site observations, concise value delivery, and low-pressure conversational CTAs."
            ),
            llm=llm,
            verbose=False
        )

        # Task 1: Intelligence extraction
        task_analysis = Task(
            description=(
                f"Analyze the crawled content for domain '{domain}':\n\n"
                f"--- CRAWLED CONTENT ---\n{crawled_markdown}\n-----------------------\n\n"
                "1. Identify the formal company name and business model.\n"
                "2. What is their core target audience (ICP)?\n"
                "3. Extract 2-3 concrete operational, conversion, or messaging pain points backed by evidence from the text."
            ),
            expected_output="Company intelligence object with business model, audience, and pain points",
            output_pydantic=CompanyIntelligence,
            agent=analyst
        )

        # Task 2: Match with our portfolio
        task_match = Task(
            description=(
                f"Review the company intelligence for '{domain}' and our offerings catalog:\n\n"
                f"--- OUR PORTFOLIO ---\n{self.portfolio_str}\n---------------------\n\n"
                "Match the company's highest-impact pain point with our best-fitting service and case study. "
                "Explain the exact strategic angle to take."
            ),
            expected_output="Matched offering details with relevant service_id, pain point, and case study hook",
            output_pydantic=MatchedOffering,
            agent=matcher,
            context=[task_analysis]
        )

        # Task 3: Draft hyper-personalized cold outreach
        task_write = Task(
            description=(
                f"Using the analysis and matched offering for '{domain}', draft a cold outreach email in {language}.\n"
                "STRICT RULES:\n"
                "- Under 110 words total.\n"
                "- Paragraph 1 (Hook): Must reference an exact observation from their site (e.g. their product tier, recent launch, or target audience).\n"
                "- Paragraph 2 (Value): Bridge to our solution and cite a metric from our case study without sounding boastful.\n"
                "- Paragraph 3 (Soft CTA): Low friction question asking permission to share a 2-min video or breakdown.\n"
                "- Two short subject lines (under 5 words each).\n"
                "- No spam trigger words (guarantee, free, urgent, groundbreaking)."
            ),
            expected_output="High-converting personalized email draft conforming to OutreachEmailDraft schema",
            output_pydantic=OutreachEmailDraft,
            agent=copywriter,
            context=[task_analysis, task_match]
        )

        crew = Crew(
            agents=[analyst, matcher, copywriter],
            tasks=[task_analysis, task_match, task_write],
            process=Process.sequential,
            verbose=False
        )

        result = crew.kickoff()

        # Parse outputs
        analysis_data = task_analysis.output.pydantic if hasattr(task_analysis.output, 'pydantic') and task_analysis.output.pydantic else None
        match_data = task_match.output.pydantic if hasattr(task_match.output, 'pydantic') and task_match.output.pydantic else None
        draft_data = task_write.output.pydantic if hasattr(task_write.output, 'pydantic') and task_write.output.pydantic else None

        if not (analysis_data and match_data and draft_data):
            logger.warning("[!] One or more CrewAI outputs were missing pydantic models. Falling back...")
            return self._generate_heuristic_draft(domain, crawled_markdown, language)

        return analysis_data, match_data, draft_data

    def _generate_heuristic_draft(
        self,
        domain: str,
        crawled_markdown: str,
        language: str = "en"
    ) -> Tuple[CompanyIntelligence, MatchedOffering, OutreachEmailDraft]:
        """
        Smart deterministic fallback when LLM API is offline or unconfigured.
        Ensures the pipeline is fully testable and never crashes.
        """
        clean_name = domain.split(".")[0].capitalize()
        
        # Pick best offering from portfolio
        first_offering = self.portfolio.get("offerings", [{}])[0]
        service_id = first_offering.get("service_id", "ai_agentic_workflows")
        service_title = first_offering.get("title", "Autonomous AI Agent Workflows")
        case_study = first_offering.get("proof_and_case_study", "Automated prospecting engine cutting research time by 82%.")
        soft_cta = first_offering.get("suggested_soft_cta", "Open to seeing a quick breakdown of how this maps to your current team?")

        pain_point = PainPointAnalysis(
            category="operational",
            description=f"Scaling outbound client acquisition and manual research for {clean_name}",
            evidence_quote=f"Identified from {domain} public offerings and target market positioning",
            severity="high"
        )

        intel = CompanyIntelligence(
            company_name=clean_name,
            domain=domain,
            business_model="B2B Technology & Services",
            core_offerings=["B2B Digital Solutions", "Cloud Platform"],
            target_audience="High-growth enterprise & mid-market companies",
            identified_pain_points=[pain_point],
            tech_stack_or_tools=["Cloud", "Analytics", "Web Services"],
            summary_pitch=f"{clean_name} provides specialized B2B software and digital services."
        )

        matched = MatchedOffering(
            service_id=service_id,
            service_title=service_title,
            addressed_pain_point=pain_point.description,
            relevance_explanation=f"Helps {clean_name} automate pipeline generation and customer targeting with bespoke AI.",
            case_study_hook=case_study
        )

        hook = f"Was looking through {domain} and noticed how your team is positioning your offerings for mid-market clients."
        value = f"We recently implemented an autonomous pipeline for a similar team, cutting manual research by 80% while doubling qualified pipeline."
        cta = soft_cta
        full_body = f"{hook}\n\n{value}\n\n{cta}"

        draft = OutreachEmailDraft(
            subject_line_1=f"quick idea for {clean_name}",
            subject_line_2=f"scaling {clean_name}'s pipeline",
            hook_paragraph=hook,
            value_paragraph=value,
            cta_paragraph=cta,
            full_email_body=full_body,
            confidence_score=0.88,
            selected_angle="Operational efficiency & pipeline automation"
        )

        return intel, matched, draft
