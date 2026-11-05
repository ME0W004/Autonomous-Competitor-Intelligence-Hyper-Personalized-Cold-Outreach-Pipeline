from typing import List, Optional
from pydantic import BaseModel, Field

class PainPointAnalysis(BaseModel):
    category: str = Field(description="Category of pain point: e.g. operational, conversion, messaging, technical")
    description: str = Field(description="Detailed description of the observed pain point or growth bottleneck")
    evidence_quote: str = Field(description="Direct quotation or evidence found on the company's website")
    severity: str = Field(default="high", description="Estimated severity: high, medium, low")

class CompanyIntelligence(BaseModel):
    company_name: str = Field(description="The formal brand/company name identified from the website")
    domain: str = Field(description="Clean domain name of the target company")
    business_model: str = Field(description="Business model: e.g., B2B SaaS, Agency, Marketplace, E-commerce, Consultancy")
    core_offerings: List[str] = Field(default_factory=list, description="List of primary products or services offered")
    target_audience: str = Field(description="Primary ICP or buyers this company serves")
    identified_pain_points: List[PainPointAnalysis] = Field(default_factory=list, description="2 to 3 actionable pain points found on the site")
    tech_stack_or_tools: List[str] = Field(default_factory=list, description="Technologies, integrations or tools mentioned")
    summary_pitch: str = Field(description="One-sentence objective summary of what this company does")

class MatchedOffering(BaseModel):
    service_id: str = Field(description="Identifier of our matched service from the portfolio")
    service_title: str = Field(description="Title of our matching offering")
    addressed_pain_point: str = Field(description="The specific target company pain point being addressed")
    relevance_explanation: str = Field(description="Why this service is the logical solution for their specific bottleneck")
    case_study_hook: str = Field(description="Relevant proof metric or case study snippet to cite")

class OutreachEmailDraft(BaseModel):
    subject_line_1: str = Field(description="Short, casual curiosity subject line (2-5 words, no sales jargon)")
    subject_line_2: str = Field(description="Alternative pain-focused subject line (3-6 words)")
    hook_paragraph: str = Field(description="Specific observation from their site showing genuine research, zero generic compliments")
    value_paragraph: str = Field(description="Pivot to the solution + relevant case study metric without hard-selling")
    cta_paragraph: str = Field(description="Low-friction soft CTA (e.g. asking permission to send a 2-min loom or 1-page breakdown)")
    full_email_body: str = Field(description="Full assembled 3-paragraph clean email body under 110 words")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Match confidence score between 0.0 and 1.0 based on available evidence")
    selected_angle: str = Field(description="Brief label for the strategic angle used")

class CrawlPageResult(BaseModel):
    url: str
    status_code: int = 200
    title: str = ""
    clean_markdown: str = ""
    is_empty: bool = False
    error: Optional[str] = None

class DomainCrawlBundle(BaseModel):
    domain: str
    success: bool
    crawled_pages: List[CrawlPageResult] = Field(default_factory=list)
    combined_markdown: str = ""
    error_message: Optional[str] = None
