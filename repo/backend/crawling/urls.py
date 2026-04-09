"""
crawling/urls.py
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CrawlRuleVersionViewSet, CrawlSourceViewSet, CrawlTaskViewSet

router = DefaultRouter()
router.register(r"sources", CrawlSourceViewSet, basename="crawl-source")
router.register(r"rule-versions", CrawlRuleVersionViewSet, basename="crawl-rule-version")
router.register(r"tasks", CrawlTaskViewSet, basename="crawl-task")

# The router generates:
#   GET/POST /api/crawl/sources/
#   GET/PUT/PATCH /api/crawl/sources/{id}/
#   GET /api/crawl/sources/{id}/rule-versions/
#   POST /api/crawl/sources/{id}/rule-versions/   (create_rule_version action)
#   GET /api/crawl/sources/{id}/debug-log/
#   GET /api/crawl/sources/{id}/quota/
#   GET /api/crawl/rule-versions/{id}/
#   POST /api/crawl/rule-versions/{id}/activate/
#   POST /api/crawl/rule-versions/{id}/canary/
#   POST /api/crawl/rule-versions/{id}/rollback/
#   POST /api/crawl/rule-versions/{id}/test/       — dry-run probe (no task created)
#   GET/POST /api/crawl/tasks/
#   GET /api/crawl/tasks/{id}/
#   POST /api/crawl/tasks/{id}/retry/

urlpatterns = router.urls
