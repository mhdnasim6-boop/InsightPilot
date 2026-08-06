"""One worked example plan per prompt category.

Every ``node_name`` here is a real, registered orchestration node
(``file_agent``, ``sql_agent``, ``browser_agent``, ``report_agent``,
``executive_summary_agent``) — these examples exist to show the LLM the
*shape* of a good plan (steps, dependencies, why-explaining descriptions,
inputs), not to hardcode which agents exist; that list always comes from
``PlannerInput.available_services`` at prompt-render time.
"""

from typing import Any

PLAN_EXAMPLES: dict[str, dict[str, Any]] = {
    "csv_analysis": {
        "goal": "Analyze the uploaded sales file and produce an executive-ready summary.",
        "reasoning_summary": (
            "The user uploaded a file and wants it analyzed. FileAgent ingests, cleans, "
            "analyzes, and visualizes it in one pipeline call, and ExecutiveSummaryAgent turns "
            "that pipeline output into a grounded, business-facing summary."
        ),
        "confidence": 0.9,
        "warnings": [],
        "assumptions": ["The most recently uploaded dataset is the one the user means."],
        "estimated_complexity": "low",
        "estimated_duration": 25.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run File Agent",
                "description": "FileAgent selected because the user asked to analyze an uploaded file.",
                "node_name": "file_agent",
                "dependencies": [],
                "inputs": {"dataset_reference": "<uploaded file path>"},
            },
            {
                "step_id": "step_2",
                "name": "Run Executive Summary Agent",
                "description": (
                    "ExecutiveSummaryAgent selected because the user wants an executive-ready "
                    "summary of the analysis, not just raw KPIs and charts."
                ),
                "node_name": "executive_summary_agent",
                "dependencies": ["step_1"],
                "inputs": {},
            },
        ],
    },
    "sql_analysis": {
        "goal": "Analyze the customer table from the SQL database and summarize key findings.",
        "reasoning_summary": (
            "The user wants a SQL-resident table analyzed. SQLAgent imports, cleans, analyzes, "
            "and visualizes it in one pipeline call, and ExecutiveSummaryAgent produces the "
            "business-facing summary from that result."
        ),
        "confidence": 0.88,
        "warnings": [],
        "assumptions": ["The declared SQL connection can reach the named table."],
        "estimated_complexity": "low",
        "estimated_duration": 30.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run SQL Agent",
                "description": "SQLAgent selected because the user requested analysis of a SQL table.",
                "node_name": "sql_agent",
                "dependencies": [],
                "inputs": {"table_name": "customers"},
            },
            {
                "step_id": "step_2",
                "name": "Run Executive Summary Agent",
                "description": (
                    "ExecutiveSummaryAgent selected because the user wants key findings "
                    "summarized, not just the raw analysis."
                ),
                "node_name": "executive_summary_agent",
                "dependencies": ["step_1"],
                "inputs": {},
            },
        ],
    },
    "report_generation": {
        "goal": "Generate a business report from the uploaded data.",
        "reasoning_summary": (
            "The user explicitly asked for a report. FileAgent prepares the underlying data, "
            "ReportAgent builds the formal report document from it, and ExecutiveSummaryAgent "
            "writes the executive summary the user implicitly expects alongside any report."
        ),
        "confidence": 0.85,
        "warnings": [],
        "assumptions": ["The most recently uploaded dataset is the one the report should cover."],
        "estimated_complexity": "medium",
        "estimated_duration": 40.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run File Agent",
                "description": "FileAgent selected to prepare the uploaded data the report will be built from.",
                "node_name": "file_agent",
                "dependencies": [],
                "inputs": {"dataset_reference": "<uploaded file path>"},
            },
            {
                "step_id": "step_2",
                "name": "Run Report Agent",
                "description": "ReportAgent selected because the user requested a report.",
                "node_name": "report_agent",
                "dependencies": ["step_1"],
                "inputs": {},
            },
            {
                "step_id": "step_3",
                "name": "Run Executive Summary Agent",
                "description": "ExecutiveSummaryAgent selected to summarize the generated report's findings.",
                "node_name": "executive_summary_agent",
                "dependencies": ["step_2"],
                "inputs": {},
            },
        ],
    },
    "comparison_request": {
        "goal": "Compare the uploaded CSV with the SQL sales table.",
        "reasoning_summary": (
            "The user wants two data sources compared. FileAgent and SQLAgent each prepare one "
            "side of the comparison independently (neither depends on the other), and "
            "ExecutiveSummaryAgent is selected last to synthesize both into one comparison."
        ),
        "confidence": 0.75,
        "warnings": ["Comparing two independently-prepared datasets is summarized qualitatively, not row-joined."],
        "assumptions": ["The uploaded CSV and the SQL table cover comparable time periods or entities."],
        "estimated_complexity": "medium",
        "estimated_duration": 45.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run File Agent",
                "description": "FileAgent selected because the user's uploaded CSV is one side of the comparison.",
                "node_name": "file_agent",
                "dependencies": [],
                "inputs": {"dataset_reference": "<uploaded file path>"},
            },
            {
                "step_id": "step_2",
                "name": "Run SQL Agent",
                "description": "SQLAgent selected because the SQL sales table is the other side of the comparison.",
                "node_name": "sql_agent",
                "dependencies": [],
                "inputs": {"table_name": "sales"},
            },
            {
                "step_id": "step_3",
                "name": "Run Executive Summary Agent",
                "description": (
                    "ExecutiveSummaryAgent selected because the user wants the comparison itself "
                    "summarized, not just the two datasets prepared."
                ),
                "node_name": "executive_summary_agent",
                "dependencies": ["step_1", "step_2"],
                "inputs": {},
            },
        ],
    },
    "report_with_market_context": {
        "goal": "Generate a report with recent market context included.",
        "reasoning_summary": (
            "The user asked for a report that includes recent market context. FileAgent "
            "prepares the data, BrowserAgent gathers the requested external market context, "
            "ReportAgent builds the report incorporating that context, and "
            "ExecutiveSummaryAgent writes the final executive summary."
        ),
        "confidence": 0.8,
        "warnings": [],
        "assumptions": ["The most recently uploaded dataset is the one the report should cover."],
        "estimated_complexity": "high",
        "estimated_duration": 55.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run File Agent",
                "description": "FileAgent selected to prepare the uploaded data the report will be built from.",
                "node_name": "file_agent",
                "dependencies": [],
                "inputs": {"dataset_reference": "<uploaded file path>"},
            },
            {
                "step_id": "step_2",
                "name": "Run Browser Agent",
                "description": "BrowserAgent selected because the user requested recent market information.",
                "node_name": "browser_agent",
                "dependencies": [],
                "inputs": {"search_request": "<market/industry topic>"},
            },
            {
                "step_id": "step_3",
                "name": "Run Report Agent",
                "description": (
                    "ReportAgent selected because the user requested a report, now incorporating "
                    "the gathered market context."
                ),
                "node_name": "report_agent",
                "dependencies": ["step_1", "step_2"],
                "inputs": {},
            },
            {
                "step_id": "step_4",
                "name": "Run Executive Summary Agent",
                "description": "ExecutiveSummaryAgent selected to summarize the report's findings and market context.",
                "node_name": "executive_summary_agent",
                "dependencies": ["step_3"],
                "inputs": {},
            },
        ],
    },
    "executive_summary_only": {
        "goal": "Produce business recommendations from the existing report.",
        "reasoning_summary": (
            "The user already has a report and only wants recommendations/business judgment "
            "drawn from it, so the plan is a single step: ExecutiveSummaryAgent selected "
            "because the user requested business recommendations, not a new pipeline run."
        ),
        "confidence": 0.9,
        "warnings": [],
        "assumptions": ["An existing report is already available for ExecutiveSummaryAgent to summarize."],
        "estimated_complexity": "low",
        "estimated_duration": 12.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run Executive Summary Agent",
                "description": "ExecutiveSummaryAgent selected because the user requested business recommendations.",
                "node_name": "executive_summary_agent",
                "dependencies": [],
                "inputs": {},
            },
        ],
    },
    "data_cleaning_request": {
        "goal": "Clean the uploaded customer records dataset.",
        "reasoning_summary": (
            "The user explicitly asked for the data to be cleaned. FileAgent's own pipeline "
            "already includes cleaning as part of ingestion, so a single step covers the full "
            "request."
        ),
        "confidence": 0.92,
        "warnings": [],
        "assumptions": [],
        "estimated_complexity": "low",
        "estimated_duration": 15.0,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Run File Agent",
                "description": (
                    "FileAgent selected because the user asked for the uploaded dataset to be "
                    "cleaned, which FileAgent's pipeline performs as part of ingestion."
                ),
                "node_name": "file_agent",
                "dependencies": [],
                "inputs": {"dataset_reference": "<uploaded file path>"},
            },
        ],
    },
}
