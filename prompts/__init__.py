"""
Prompt Management
Load and manage AI prompts from external files
"""
import json
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent


def load_system_prompt() -> str:
    """Load the main system prompt"""
    with open(PROMPTS_DIR / "system_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def load_page_analysis_prompt() -> str:
    """Load the page analysis prompt template"""
    with open(PROMPTS_DIR / "page_analysis_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def load_consolidation_prompt() -> str:
    """Load the consolidation prompt template"""
    with open(PROMPTS_DIR / "consolidation_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def load_report_generation_prompt() -> str:
    """Load the report generation prompt"""
    with open(PROMPTS_DIR / "report_generation_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def load_page_json_schema() -> str:
    """Load the page JSON schema"""
    with open(PROMPTS_DIR / "page_json_schema.json", "r", encoding="utf-8") as f:
        return f.read()


def load_final_schema() -> str:
    """Load the final JSON schema"""
    with open(PROMPTS_DIR / "final_schema.json", "r", encoding="utf-8") as f:
        return f.read()


def load_civil_schema() -> str:
    """Load the civil engineering JSON schema"""
    with open(PROMPTS_DIR / "civil_schema.json", "r", encoding="utf-8") as f:
        return f.read()


def load_civil_system_prompt() -> str:
    """Load the civil engineering system prompt"""
    with open(PROMPTS_DIR / "civil_system_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def load_civil_page_analysis_prompt() -> str:
    """Load the civil engineering page analysis prompt template"""
    with open(PROMPTS_DIR / "civil_page_analysis_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def format_civil_page_analysis_prompt(page_index: int, vector_data: str, page_json_schema: str) -> str:
    """Format the civil page analysis prompt with dynamic values"""
    template = load_civil_page_analysis_prompt()
    return template.format(
        page_index=page_index,
        vector_data=vector_data,
        page_json_schema=page_json_schema
    )


def load_civil_final_schema() -> str:
    """Load the civil engineering final JSON schema"""
    with open(PROMPTS_DIR / "civil_final_schema.json", "r", encoding="utf-8") as f:
        return f.read()


def load_civil_consolidation_prompt() -> str:
    """Load the civil engineering consolidation prompt template"""
    with open(PROMPTS_DIR / "civil_consolidation_prompt.md", "r", encoding="utf-8") as f:
        return f.read()


def format_civil_consolidation_prompt(page_results: str, final_schema: str) -> str:
    """Format the civil consolidation prompt with dynamic values"""
    template = load_civil_consolidation_prompt()
    return template.format(
        page_results=page_results,
        final_schema=final_schema
    )


def format_page_analysis_prompt(page_index: int, vector_data: str, page_json_schema: str) -> str:
    """Format the page analysis prompt with dynamic values"""
    template = load_page_analysis_prompt()
    return template.format(
        page_index=page_index,
        vector_data=vector_data,
        page_json_schema=page_json_schema
    )


def format_consolidation_prompt(page_results: str, final_schema: str) -> str:
    """Format the consolidation prompt with dynamic values"""
    template = load_consolidation_prompt()
    return template.format(
        page_results=page_results,
        final_schema=final_schema
    )


__all__ = [
    'load_system_prompt',
    'load_page_analysis_prompt',
    'load_consolidation_prompt',
    'load_report_generation_prompt',
    'load_page_json_schema',
    'load_final_schema',
    'load_civil_schema',
    'load_civil_system_prompt',
    'load_civil_final_schema',
    'load_civil_consolidation_prompt',
    'format_page_analysis_prompt',
    'format_consolidation_prompt',
    'format_civil_page_analysis_prompt',
    'format_civil_consolidation_prompt'
]