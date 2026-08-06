"""Aggregates all v1 routes under the ``/api/v1`` prefix."""

from fastapi import APIRouter

from backend.api.v1 import (
    adaptive,
    analysis,
    approvals,
    autonomous,
    browser_agent,
    chat,
    collaboration,
    datasets,
    distributed,
    execution,
    executive_summary,
    federation,
    file_agent,
    health,
    mcp,
    memory,
    observability,
    operations,
    planner,
    plugins,
    realtime,
    reflection,
    report_agent,
    reports,
    security,
    sessions,
    sql_agent,
    sql_datasource,
    system,
    visualizations,
    workflows,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router, tags=["health"])
router.include_router(sessions.router, tags=["sessions"])
router.include_router(datasets.router, tags=["datasets"])
router.include_router(analysis.router, tags=["analysis"])
router.include_router(visualizations.router, tags=["visualizations"])
router.include_router(planner.router, tags=["planner"])
router.include_router(system.router, tags=["system"])
router.include_router(chat.router, tags=["chat"])
router.include_router(sql_datasource.router, tags=["sql-datasource"])
router.include_router(reports.router, tags=["reports"])
router.include_router(mcp.router, tags=["mcp"])
router.include_router(file_agent.router, tags=["file-agent"])
router.include_router(sql_agent.router, tags=["sql-agent"])
router.include_router(browser_agent.router, tags=["browser-agent"])
router.include_router(report_agent.router, tags=["report-agent"])
router.include_router(executive_summary.router, tags=["executive-summary-agent"])
router.include_router(approvals.router, tags=["approvals"])
router.include_router(observability.router, tags=["observability"])
router.include_router(execution.router, tags=["execution"])
router.include_router(memory.router, tags=["memory"])
router.include_router(collaboration.router, tags=["collaboration"])
router.include_router(reflection.router, tags=["reflection"])
router.include_router(adaptive.router, tags=["adaptive"])
router.include_router(plugins.router, tags=["plugins"])
router.include_router(operations.router, tags=["operations"])
router.include_router(security.router, tags=["security"])
router.include_router(workflows.router, tags=["workflows"])
router.include_router(realtime.router, tags=["realtime"])
router.include_router(distributed.router, tags=["distributed"])
router.include_router(federation.router, tags=["federation"])
router.include_router(autonomous.router, tags=["autonomous"])
