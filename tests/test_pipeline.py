import pytest
from pathlib import Path
from src.crawler.cleaner import normalize_domain_url, clean_markdown_text, assemble_domain_content
from src.agents.schemas import (
    PainPointAnalysis,
    CompanyIntelligence,
    MatchedOffering,
    OutreachEmailDraft
)
from src.agents.crew_pipeline import load_our_portfolio
from src.pipeline.exporter import OutreachDataExporter

def test_normalize_domain_url():
    assert normalize_domain_url("stripe.com") == "https://stripe.com"
    assert normalize_domain_url("http://stripe.com/") == "https://stripe.com"
    assert normalize_domain_url("https://linear.app///") == "https://linear.app"

def test_clean_markdown_text():
    raw_noisy = (
        "# Welcome to Our Site\n\n"
        "![Logo](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...)\n"
        "[Click here to view products](https://example.com/products)\n\n\n\n\n"
        "We help B2B teams automate workflows."
    )
    cleaned = clean_markdown_text(raw_noisy)
    assert "data:image" not in cleaned
    assert "Click here to view products" in cleaned
    assert "https://example.com/products" not in cleaned  # Stripped noisy link URL
    assert "\n\n\n" not in cleaned

def test_assemble_domain_content():
    pages = [
        {"url": "https://test.com", "title": "Home", "clean_markdown": "Homepage text"},
        {"url": "https://test.com/pricing", "title": "Pricing", "clean_markdown": "Plan tiers"}
    ]
    bundle_str = assemble_domain_content("test.com", pages)
    assert "# TARGET COMPANY INTELLIGENCE DOSSIER: test.com" in bundle_str
    assert "PRICING & TIERS" in bundle_str
    assert "Plan tiers" in bundle_str

def test_load_our_portfolio():
    portfolio = load_our_portfolio()
    assert "agency_name" in portfolio
    assert "offerings" in portfolio
    assert len(portfolio["offerings"]) > 0
    assert "service_id" in portfolio["offerings"][0]

def test_pydantic_schemas():
    pain = PainPointAnalysis(
        category="conversion",
        description="Low checkout conversion rate",
        evidence_quote="Sign up forms take 7 steps",
        severity="high"
    )
    intel = CompanyIntelligence(
        company_name="TestCorp",
        domain="testcorp.com",
        business_model="B2B SaaS",
        core_offerings=["CRM"],
        target_audience="Small Businesses",
        identified_pain_points=[pain],
        tech_stack_or_tools=["React", "Postgres"],
        summary_pitch="CRM platform for SMBs."
    )
    assert intel.company_name == "TestCorp"
    assert intel.identified_pain_points[0].category == "conversion"

    draft = OutreachEmailDraft(
        subject_line_1="quick thought on checkout",
        subject_line_2="scaling testcorp signup",
        hook_paragraph="Noticed your 7-step signup process on testcorp.com.",
        value_paragraph="We helped a similar team cut onboarding to 2 steps and lift conversion 34%.",
        cta_paragraph="Open to checking a 2-min breakdown?",
        full_email_body="Noticed your 7-step signup...\n\nOpen to checking?",
        confidence_score=0.92,
        selected_angle="Conversion Rate Optimization"
    )
    assert draft.confidence_score == 0.92

def test_exporter(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.settings.OUTPUT_DIR", tmp_path)
    records = [{
        "Domain": "example.com",
        "Company_Name": "Example Corp",
        "Business_Model": "SaaS",
        "Target_Audience": "Enterprises",
        "Identified_Pain_Point": "High churn",
        "Evidence_Snippet": "Legacy portal",
        "Matched_Service": "AI Agents",
        "Personalized_Subject_1": "quick note",
        "Personalized_Subject_2": "idea for example",
        "Email_Body_Draft": "Hello world email",
        "Hook_Sentence": "Saw your site",
        "Value_Sentence": "We solve churn",
        "Soft_CTA": "Worth a quick chat?",
        "Confidence_Score": 0.85,
        "Status": "SUCCESS",
        "Pages_Crawled": 2,
        "Error_Message": ""
    }]
    exported = OutreachDataExporter.export(records, output_name="test_export", formats=["csv", "xlsx", "json"])
    assert exported["csv"].exists()
    assert exported["xlsx"].exists()
    assert exported["json"].exists()
