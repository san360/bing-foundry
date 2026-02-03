"""
Pre-baked prompts for company risk analysis
"""
from typing import Optional
from config import RISK_CATEGORIES


def get_company_risk_analysis_prompt(company_name: str, market: Optional[str] = None) -> str:
    """
    Generate the comprehensive company risk analysis prompt.
    
    Args:
        company_name: Name of the company to analyze
        market: Optional market code (e.g., 'de-CH', 'en-US')
        
    Returns:
        The formatted prompt string
    """
    
    market_context = ""
    if market:
        market_context = f"""
## Market Context
You are performing this analysis with a focus on the **{market}** market. 
Please prioritize news sources, legal databases, and regulatory information 
relevant to this market region when available.
"""

    risk_categories_list = "\n".join([f"- {cat}" for cat in RISK_CATEGORIES])
    
    prompt = f"""# Company Risk Analysis Request

## Company Under Analysis
**Company Name:** {company_name}

{market_context}
## Analysis Scope

You are an expert insurance risk analyst. Perform a comprehensive due diligence 
analysis on the specified company. Use the Bing Search grounding tool to gather 
real-time, up-to-date information from the web.

## Required Analysis Sections

### 1. Company Overview
- Full legal name and common aliases
- Headquarters location and key operational regions
- Industry sector and primary business activities
- Company size (employees, revenue if available)
- Key leadership and ownership structure
- Stock ticker (if publicly traded)

### 2. Litigation & Legal Issues
Search for and analyze:
- Current and recent lawsuits (plaintiff or defendant)
- Class action lawsuits
- Regulatory enforcement actions
- Settlement agreements
- Criminal investigations or charges
- Patent/IP disputes

### 3. Negative News & Controversies
Search for news coverage related to:
{risk_categories_list}

For each finding, provide:
- Source and date
- Brief summary
- Potential insurance implications

### 4. Regulatory Compliance Status
- Industry-specific regulatory standing
- Recent regulatory filings or violations
- License status in key jurisdictions
- ESG ratings and sustainability reports

### 5. Financial Health Indicators
- Credit ratings (if available)
- Recent financial news
- Bankruptcy or restructuring history
- Major shareholder changes

### 6. Risk Assessment Summary

Provide an overall risk rating using this scale:
- **CRITICAL**: Immediate and severe risk factors present
- **HIGH**: Significant risk factors requiring close attention
- **MODERATE**: Some risk factors but manageable
- **LOW**: Minimal risk factors identified
- **INSUFFICIENT DATA**: Unable to assess due to limited information

Include:
- Top 3 risk factors
- Top 3 risk mitigating factors
- Recommended actions for insurers

## Output Format

Structure your response with clear headers and bullet points. 
Include citations with URLs for all factual claims.
Note any information gaps or areas requiring further investigation.

**IMPORTANT**: Always cite your sources with the actual URLs from Bing search results.
"""
    return prompt


def get_focused_search_prompt(company_name: str, focus_area: str) -> str:
    """
    Generate a focused search prompt for specific risk areas.
    
    Args:
        company_name: Name of the company
        focus_area: Specific area to focus on (e.g., 'litigation', 'environmental')
        
    Returns:
        The formatted prompt string
    """
    
    prompts = {
        "litigation": f"""
Search for all litigation and legal cases involving {company_name}:
- Active lawsuits where they are plaintiff or defendant
- Class action lawsuits
- Regulatory enforcement actions
- Recent settlements
- Criminal investigations

Provide case names, courts, dates, and current status for each.
""",
        "environmental": f"""
Search for environmental issues and ESG concerns related to {company_name}:
- Environmental violations or fines
- Pollution incidents
- Climate-related lawsuits
- ESG ratings and controversies
- Sustainability report findings

Provide sources and dates for all findings.
""",
        "labor": f"""
Search for labor and workplace issues involving {company_name}:
- Child labor allegations or findings
- Workplace safety violations
- Labor disputes and strikes
- Discrimination lawsuits
- Wage and hour violations

Provide sources and dates for all findings.
""",
        "financial": f"""
Search for financial health and compliance issues for {company_name}:
- Credit rating changes
- Fraud allegations
- SEC investigations
- Bankruptcy or restructuring
- Major executive departures

Provide sources and dates for all findings.
""",
    }
    
    return prompts.get(focus_area, prompts["litigation"])


# System instruction for the agent
AGENT_SYSTEM_INSTRUCTION = """You are an expert insurance risk analyst specializing in corporate due diligence. 

Your role is to:
1. Gather comprehensive information about companies using Bing Search
2. Analyze findings from an insurance risk perspective
3. Identify potential liabilities and risk factors
4. Provide actionable insights for insurance underwriting decisions

Guidelines:
- Always cite sources with URLs
- Be objective and factual
- Note when information is uncertain or requires verification
- Flag critical findings prominently
- Consider both historical issues and current status
- Account for the geographic market context when specified

You have access to Bing Search for real-time web information. Use it extensively 
to gather the most current data available."""
