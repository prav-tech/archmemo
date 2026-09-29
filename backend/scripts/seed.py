"""
Seed script – loads 26 realistic architecture decisions + 15 outcomes.

Usage:
    cd backend
    python scripts/seed.py

What it does:
1. Creates SQLite tables (if not already created).
2. Inserts 26 Decision records into SQL.
3. Attaches outcomes to 15 of them (the other 11 exercise the 'missing outcomes' view).
4. Retains all decisions and outcomes to Hindsight.

This gives the briefing agent rich institutional memory from the very
first run, so the demo story works immediately.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend root to path so app imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import track
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.memory.client import get_memory_client
from app.models.decision import Decision, Outcome

console = Console()
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────
# Seed Data – 26 realistic architecture decisions
# ─────────────────────────────────────────────────────────────────────────

SEED_DECISIONS: list[dict] = [
    {
        "decision_id": "DEC-2022-001",
        "title": "Adopt Kafka for inter-service event streaming",
        "date": "2022-02-10",
        "authors": "Priya Nair, Dev Team Platform",
        "domain": "platform",
        "services": ["order-service", "inventory-service", "notifications", "analytics"],
        "context": "Our microservices were communicating via synchronous REST calls, causing tight coupling and cascading failures. During peak load (Black Friday 2021), the order-service timeout caused a full inventory cascade failure affecting 40% of orders. We needed an asynchronous, durable messaging backbone.",
        "forces": "High throughput requirements (50k msg/sec peak). Existing RabbitMQ cluster was losing messages during restarts. Need for message replay. Team already had partial Kafka familiarity from a data pipeline project.",
        "options": ["Keep RabbitMQ and add persistence", "Adopt Apache Kafka", "Use AWS SQS/SNS", "Adopt NATS JetStream"],
        "chosen_option": "Adopt Apache Kafka",
        "rationale": "Kafka's durable log and consumer group model solved our replay and multi-consumer needs. The team had existing familiarity reducing ramp time. SQS was ruled out due to vendor lock-in concerns and 256KB message size limit.",
        "expected_outcomes": "Eliminate cascading failures. Sub-100ms event delivery p99. Enable event replay for audit. Reduce service coupling.",
        "tags": ["messaging", "kafka", "event-streaming", "platform"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-002",
        "title": "Migrate authentication service to JWT with Redis token store",
        "date": "2022-04-05",
        "authors": "Sarah Chen, Security Team",
        "domain": "security",
        "services": ["auth-service", "api-gateway", "user-service"],
        "context": "Stateful session-based auth was preventing horizontal scaling of the API gateway. Session affinity on the load balancer was causing uneven traffic distribution and single-node failure risks. 3 outages in Q1 2022 were traced to session store unavailability.",
        "forces": "Need for stateless authentication to enable auto-scaling. Compliance requirement for token revocation within 60 seconds. Existing session DB was a single PostgreSQL instance.",
        "options": ["JWT stateless (no revocation)", "JWT with Redis token blacklist", "OAuth2 / OIDC with external provider", "Keep sessions but replicate store"],
        "chosen_option": "JWT with Redis token blacklist",
        "rationale": "Pure stateless JWT could not meet the 60-second revocation requirement. Redis cluster provides fast token invalidation lookups with TTL-based expiry matching JWT lifetime.",
        "expected_outcomes": "Eliminate session-related outages. Enable gateway horizontal scaling. Meet compliance token revocation SLA.",
        "tags": ["auth", "jwt", "redis", "security", "scaling"],
        "related_decisions": ["DEC-2022-004"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-003",
        "title": "Adopt PostgreSQL JSONB over MongoDB for product catalogue",
        "date": "2022-05-20",
        "authors": "Marcus Webb, Data Team",
        "domain": "data",
        "services": ["catalogue-service", "search-service"],
        "context": "Product catalogue needed flexible schema for varying product attributes (electronics have specs, clothing has sizes/colours) while maintaining ACID transactions for inventory counts. MongoDB was proposed for schema flexibility.",
        "forces": "Schema flexibility for 200+ product categories. Transactional integrity for stock counts. Team expertise was stronger in PostgreSQL. MongoDB licensing changed in 2018.",
        "options": ["MongoDB Atlas", "PostgreSQL with JSONB columns", "PostgreSQL with EAV pattern", "Separate databases per product type"],
        "chosen_option": "PostgreSQL with JSONB columns",
        "rationale": "JSONB provides document-style flexibility within a relational model, preserving ACID semantics for inventory transactions. GIN indexes on JSONB match MongoDB query performance for our use case. Avoided MongoDB SSPL licensing concerns.",
        "expected_outcomes": "Flexible product attributes without schema migrations. ACID inventory transactions. Single database technology for team to maintain.",
        "tags": ["database", "postgresql", "jsonb", "schema-design"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-004",
        "title": "Deploy Redis Cluster for distributed caching and session storage",
        "date": "2022-06-01",
        "authors": "Sarah Chen, Ops Team",
        "domain": "platform",
        "services": ["auth-service", "api-gateway", "catalogue-service", "rate-limiter"],
        "context": "Multiple services independently implemented in-process caches, causing cache stampede during deployments and inconsistent invalidation. Auth service needed shared token blacklist.",
        "forces": "Shared state across multiple service instances. Sub-millisecond cache reads required. Existing Memcached cluster had no persistence and no pub/sub.",
        "options": ["Memcached cluster", "Redis Cluster (3+3 shards)", "Redis Sentinel (single shard)", "Embedded Hazelcast"],
        "chosen_option": "Redis Cluster (3+3 shards)",
        "rationale": "Redis Cluster provides automatic failover, horizontal scaling across shards, and supports pub/sub for cache invalidation events. Redis Sentinel rejected for single-shard throughput ceiling.",
        "expected_outcomes": "Eliminate cache stampede. Sub-1ms p99 cache reads. Enable token blacklisting for auth service.",
        "tags": ["caching", "redis", "platform", "performance"],
        "related_decisions": ["DEC-2022-002"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-005",
        "title": "Adopt gRPC for internal service-to-service communication",
        "date": "2022-07-14",
        "authors": "Dev Team Platform, James Liu",
        "domain": "platform",
        "services": ["all internal services"],
        "context": "Internal REST APIs were generating excessive JSON serialisation overhead measured at 15-20% of CPU time in profiling. Services calling each other required manual client SDK maintenance.",
        "forces": "Performance-sensitive internal calls (e.g., price calculation service called 200x/sec). Desire for strongly-typed contracts between teams. Mobile clients must remain REST/JSON.",
        "options": ["Keep REST/JSON", "Adopt gRPC with protobuf", "GraphQL federation", "Thrift"],
        "chosen_option": "Adopt gRPC with protobuf",
        "rationale": "gRPC with protobuf reduces serialisation CPU by ~60% in benchmarks and auto-generates type-safe clients. External-facing REST APIs retained via an Envoy gRPC-Web proxy.",
        "expected_outcomes": "60% reduction in internal serialisation overhead. Auto-generated, type-safe client SDKs. Eliminate REST client SDK maintenance burden.",
        "tags": ["grpc", "protobuf", "performance", "internal-api"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-006",
        "title": "Adopt feature flags via LaunchDarkly for controlled rollouts",
        "date": "2022-08-30",
        "authors": "Product Engineering, Ananya Rajan",
        "domain": "delivery",
        "services": ["all product-facing services"],
        "context": "Deployments were all-or-nothing, preventing gradual rollouts. A pricing bug in August 2022 affected 100% of users before it was caught because there was no mechanism to roll back to a subset.",
        "forces": "Need for percentage rollouts. Requirement to target specific user segments. Ops team needed kill-switch without code deployment.",
        "options": ["Build internal feature flag service", "LaunchDarkly", "Unleash (self-hosted)", "Simple environment variable flags"],
        "chosen_option": "LaunchDarkly",
        "rationale": "LaunchDarkly's SDK ecosystem covered all our languages (Python, Go, TypeScript). Self-hosted Unleash required operational overhead we couldn't sustain. Building internally would delay 3 months.",
        "expected_outcomes": "Canary deployments for all major features. Kill-switch capability in <1 minute. Reduce blast radius of future bugs.",
        "tags": ["feature-flags", "launchdarkly", "delivery", "rollout"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2022-007",
        "title": "Migrate from EC2-based deployments to Kubernetes on EKS",
        "date": "2022-10-03",
        "authors": "Ops Team, Sofia Martinez",
        "domain": "platform",
        "services": ["all services"],
        "context": "EC2-based deployment required 45 minutes for a full cluster roll-out and had no automated recovery for node failures. Services were hand-crafted AMIs with configuration drift between environments.",
        "forces": "Team of 3 SREs managing 40+ services. Need for automated self-healing. Staging/prod environment parity. Container image already used for local dev.",
        "options": ["EC2 with Ansible + ASG", "AWS ECS", "Kubernetes on EKS", "AWS Lambda for all services"],
        "chosen_option": "Kubernetes on EKS",
        "rationale": "EKS reduces operational overhead of control plane management. Kubernetes' declarative model resolved environment drift. Helm charts enabled reproducible releases. ECS rejected due to weaker ecosystem and future portability concerns.",
        "expected_outcomes": "Deployment time from 45min to under 5min. Self-healing for node failures. Eliminate staging/prod configuration drift.",
        "tags": ["kubernetes", "eks", "infrastructure", "containers"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-001",
        "title": "Adopt dbt for analytics data transformation pipeline",
        "date": "2023-01-12",
        "authors": "Data Team, Marcus Webb",
        "domain": "data",
        "services": ["analytics", "data-warehouse"],
        "context": "Analytics SQL transformations were maintained as ad-hoc Python scripts with no lineage tracking, no testing, and no documentation. Multiple analysts had conflicting definitions of 'active user' and 'revenue'. An audit in December 2022 found 3 inconsistent revenue figures across dashboards.",
        "forces": "Need for transformation lineage tracking. Analysts should own SQL without engineering support. Data tests required for metrics used in board reporting.",
        "options": ["Apache Airflow with SQL operators", "dbt Core (self-hosted)", "dbt Cloud", "Dagster with embedded SQL"],
        "chosen_option": "dbt Core (self-hosted)",
        "rationale": "dbt provides lineage, testing, and documentation in a SQL-native workflow analysts already know. dbt Cloud rejected due to cost at our data volume. Airflow overengineered for pure transformation logic.",
        "expected_outcomes": "Single source of truth for all business metrics. Lineage graph for impact analysis. Automated data tests catching regressions.",
        "tags": ["dbt", "data", "analytics", "data-quality"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-002",
        "title": "Adopt OpenTelemetry for unified observability across all services",
        "date": "2023-02-28",
        "authors": "Platform Team, James Liu",
        "domain": "observability",
        "services": ["all services"],
        "context": "Three different observability tools (Datadog agents, Jaeger, Prometheus) were sending partially overlapping telemetry. Correlation across traces, metrics, and logs required manual effort. Datadog costs were $180k/year and growing at 40% annually.",
        "forces": "Vendor-neutral telemetry collection. Cost reduction. Unified correlation across signals. Engineering time wasted on multi-tool troubleshooting.",
        "options": ["All-in on Datadog", "OpenTelemetry + Grafana Stack", "OpenTelemetry + Honeycomb", "AWS X-Ray + CloudWatch"],
        "chosen_option": "OpenTelemetry + Grafana Stack (Tempo, Loki, Prometheus)",
        "rationale": "OpenTelemetry auto-instrumentation libraries cover all our languages. Grafana stack provides unified UI with no per-seat or per-data licensing. Self-hosted total cost modelled at $24k/year vs $180k Datadog.",
        "expected_outcomes": "85% reduction in observability costs. Unified trace-to-log correlation. Vendor portability for future backend changes.",
        "tags": ["observability", "opentelemetry", "grafana", "cost-reduction"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-003",
        "title": "Adopt read replicas and connection pooling for PostgreSQL scaling",
        "date": "2023-04-10",
        "authors": "Data Team, Backend Team",
        "domain": "data",
        "services": ["order-service", "catalogue-service", "reporting"],
        "context": "Primary PostgreSQL instance was at 85% CPU during business hours, with read queries from reporting and analytics competing with write traffic from order processing. Two P1 incidents in Q1 2023 were caused by long-running analytical queries blocking writes.",
        "forces": "Cannot afford primary DB downtime. Reporting queries must not impact OLTP. Budget constraints prevent immediate migration to managed Aurora.",
        "options": ["Read replicas + PgBouncer pooling", "Migrate to Amazon Aurora", "Separate OLAP database immediately", "Query optimisation only"],
        "chosen_option": "Read replicas + PgBouncer connection pooling",
        "rationale": "Fastest path to isolating read load from writes. PgBouncer transaction-mode pooling reduces connection overhead. Aurora migration deferred to Q4 as a separate initiative.",
        "expected_outcomes": "Eliminate reporting-caused write blocks. Reduce primary CPU from 85% to under 50%. P99 write latency under 20ms.",
        "tags": ["postgresql", "database", "scaling", "read-replica", "pgbouncer"],
        "related_decisions": ["DEC-2022-003"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-004",
        "title": "Replace server-side rendering with Next.js App Router",
        "date": "2023-05-22",
        "authors": "Frontend Team, Kenji Watanabe",
        "domain": "frontend",
        "services": ["web-app", "marketing-site"],
        "context": "Legacy React SPA had poor Core Web Vitals (LCP 4.2s, CLS 0.22) hurting SEO and conversion. Server-side rendering with Pages Router was explored but React Server Components in App Router offered better data-fetching patterns.",
        "forces": "SEO requirements for marketing pages. Performance budget of LCP under 2.5s. Team had existing Next.js expertise.",
        "options": ["Next.js Pages Router (SSR)", "Next.js App Router (RSC)", "Remix", "Astro for marketing + SPA for app"],
        "chosen_option": "Next.js App Router with React Server Components",
        "rationale": "App Router's React Server Components enable zero-JS by default for static content. Streaming with Suspense improved TTFB. Vercel deployment provides edge caching without custom infra.",
        "expected_outcomes": "LCP under 2.5s. CLS under 0.1. Improved SEO organic traffic within 3 months.",
        "tags": ["frontend", "nextjs", "react", "performance", "seo"],
        "related_decisions": [],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-005",
        "title": "Adopt Terraform for infrastructure as code",
        "date": "2023-06-15",
        "authors": "Ops Team, Sofia Martinez",
        "domain": "platform",
        "services": ["all infrastructure"],
        "context": "AWS infrastructure was managed via ClickOps (console) with partial Ansible coverage. Staging environment diverged from production, causing 2 incidents where staging-passing code failed in production due to infrastructure differences.",
        "forces": "Infrastructure reproducibility. Audit trail for all infra changes. Staging/prod parity. Team of 3 must manage 12 AWS accounts.",
        "options": ["Terraform", "AWS CDK", "Pulumi", "Continue with Ansible + CloudFormation"],
        "chosen_option": "Terraform with Terragrunt",
        "rationale": "Terraform has the largest community and provider ecosystem. Terragrunt reduces module duplication across environments. CDK rejected due to dependency on AWS specifically. Team had prior Terraform exposure.",
        "expected_outcomes": "100% infrastructure defined as code within 6 months. Zero staging/prod drift. Infra review process via pull requests.",
        "tags": ["terraform", "iac", "infrastructure", "devops"],
        "related_decisions": ["DEC-2022-007"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-006",
        "title": "Adopt Elasticsearch for product search",
        "date": "2023-07-18",
        "authors": "Search Team, Priya Nair",
        "domain": "data",
        "services": ["search-service", "catalogue-service"],
        "context": "PostgreSQL full-text search was returning poor quality results for product searches with typos and synonyms. Conversion rate on search was 2.1% vs 4.8% industry benchmark. Customer complaints about search quality were the top support ticket category.",
        "forces": "Relevance tuning without full reindex. Near-real-time index updates (product updates must appear in search within 30 seconds). Faceted search for filter UI.",
        "options": ["PostgreSQL full-text search (current)", "Elasticsearch", "Typesense", "Algolia"],
        "chosen_option": "Elasticsearch (self-hosted on EKS)",
        "rationale": "Elasticsearch's BM25+vector hybrid search, faceted aggregations, and typo tolerance met all requirements. Algolia cost-prohibitive at our query volume (8M searches/month). Typesense lacked enterprise features.",
        "expected_outcomes": "Search conversion rate above 4%. Typo tolerance for top 1000 product terms. Real-time indexing within 30 seconds.",
        "tags": ["elasticsearch", "search", "data"],
        "related_decisions": ["DEC-2022-003"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-007",
        "title": "Adopt SLO-based alerting and error budget policy",
        "date": "2023-08-07",
        "authors": "SRE Team, James Liu",
        "domain": "observability",
        "services": ["all production services"],
        "context": "Alert fatigue was severe: 850+ alerts per week, engineers ignoring pages after hours because most were false positives. Mean time to response for real incidents was 45 minutes because alerts didn't indicate severity.",
        "forces": "On-call rotation was burning out engineers (2 left in Q2). Alerts must indicate customer impact. Error budgets needed to gate feature work.",
        "options": ["Tune existing threshold alerts", "Adopt SLO-based alerting (burn rate)", "Implement AIOps alert correlation", "Reduce alert count manually"],
        "chosen_option": "SLO-based alerting with burn rate alerts and error budget policy",
        "rationale": "Burn rate alerts fire only when SLO is being consumed too fast to survive the window, directly correlating to customer impact. Error budget policy formalises the trade-off between reliability and feature velocity.",
        "expected_outcomes": "Reduce weekly alert count from 850 to under 50. Eliminate on-call burnout. MTTR from 45min to under 15min.",
        "tags": ["sre", "slo", "alerting", "observability", "reliability"],
        "related_decisions": ["DEC-2023-002"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-008",
        "title": "Adopt event sourcing for the Order aggregate",
        "date": "2023-09-20",
        "authors": "Backend Team, Marcus Webb",
        "domain": "data",
        "services": ["order-service"],
        "context": "Order service had complex state machine (pending, confirmed, picking, shipped, delivered, cancelled) with race conditions detected in production causing orders to skip states. Audit trail was incomplete because state overwriting lost intermediate states.",
        "forces": "Full audit trail required for regulatory compliance. Race condition elimination. Ability to replay and rebuild order projections. High write volume (5000 orders/hour peak).",
        "options": ["Event sourcing with EventStoreDB", "Event sourcing with PostgreSQL append-only table", "Saga pattern with compensation", "Optimistic locking on current model"],
        "chosen_option": "Event sourcing with PostgreSQL append-only event table",
        "rationale": "Using PostgreSQL for the event store avoided introducing a new database technology. Append-only table with sequence numbers provides ordering guarantees. EventStoreDB rejected due to operational overhead.",
        "expected_outcomes": "Zero lost state transitions. Complete audit trail for all order events. Ability to rebuild read models by replaying events.",
        "tags": ["event-sourcing", "orders", "data", "reliability"],
        "related_decisions": ["DEC-2022-001", "DEC-2022-003"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2023-009",
        "title": "Adopt CQRS for the reporting read side",
        "date": "2023-11-05",
        "authors": "Backend Team",
        "domain": "data",
        "services": ["order-service", "reporting"],
        "context": "After adopting event sourcing (DEC-2023-008), the write model projections were too slow for reporting queries which needed aggregations across millions of orders. Read model needed different optimisation than write model.",
        "forces": "Report generation must complete within 5 seconds. Write model must not be impacted by read query load. Read model can tolerate up to 30 seconds eventual consistency.",
        "options": ["CQRS with separate read DB (Elasticsearch)", "CQRS with materialised views in PostgreSQL", "Keep single model with better indexes", "Pre-compute reports as batch jobs"],
        "chosen_option": "CQRS with materialised PostgreSQL views refreshed from event stream",
        "rationale": "Materialised views provided familiar tooling for the team. Refreshed asynchronously from Kafka (DEC-2022-001) event stream. Elasticsearch considered but added operational complexity for structured aggregations.",
        "expected_outcomes": "Report queries under 5 seconds. Zero read query impact on write throughput. Acceptable 30-second staleness for reporting.",
        "tags": ["cqrs", "event-sourcing", "orders", "data"],
        "related_decisions": ["DEC-2023-008", "DEC-2022-001"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-001",
        "title": "Adopt Vector Database (Weaviate) for semantic product recommendations",
        "date": "2024-01-08",
        "authors": "ML Team, Ananya Rajan",
        "domain": "ml",
        "services": ["recommendation-service", "catalogue-service"],
        "context": "Rule-based product recommendations had a 1.2% click-through rate. Collaborative filtering was attempted but cold-start problem for new products and new users degraded quality. ML team proposed embedding-based semantic similarity.",
        "forces": "Cold-start tolerance required. Under 50ms recommendation latency at p99. Embedding models already trained on product descriptions. Budget for managed service limited.",
        "options": ["Weaviate self-hosted", "Pinecone managed", "pgvector (PostgreSQL extension)", "Qdrant self-hosted"],
        "chosen_option": "Weaviate self-hosted on EKS",
        "rationale": "Weaviate's multi-tenancy and hybrid BM25+vector search aligned with our search strategy. pgvector rejected due to performance degradation at 10M+ vectors. Pinecone cost at our vector count would be $8k/month.",
        "expected_outcomes": "CTR above 3.5%. Cold-start handled via text embeddings. Sub-50ms p99 recommendation latency.",
        "tags": ["vector-db", "weaviate", "ml", "recommendations", "embeddings"],
        "related_decisions": ["DEC-2023-006"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-002",
        "title": "Migrate from REST to GraphQL for the Partner API",
        "date": "2024-02-14",
        "authors": "API Team, Kenji Watanabe",
        "domain": "api",
        "services": ["partner-api", "catalogue-service", "order-service"],
        "context": "Partner API was serving 12 external partner integrations. Each partner requested custom response shapes requiring backend changes. 40% of partner API calls were over-fetching (loading full product objects for a name lookup).",
        "forces": "Partners must not require backend changes for field selection. Schema introspection for partner developer experience. Existing REST clients must have migration path.",
        "options": ["GraphQL (Hot Chocolate .NET)", "GraphQL (Strawberry Python)", "REST + sparse fieldsets (JSON:API)", "gRPC with partner SDK generation"],
        "chosen_option": "GraphQL with Strawberry Python",
        "rationale": "Strawberry's Python-native schema definition aligned with team expertise. Schema introspection dramatically improved partner onboarding. Existing REST endpoints retained for 12-month deprecation window.",
        "expected_outcomes": "Partners self-serve field selection without backend changes. Reduce over-fetching by 50%. New partner onboarding under 2 days.",
        "tags": ["graphql", "api", "partners", "developer-experience"],
        "related_decisions": ["DEC-2022-005"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-003",
        "title": "Adopt Temporal for distributed workflow orchestration",
        "date": "2024-03-20",
        "authors": "Backend Team, Priya Nair",
        "domain": "platform",
        "services": ["fulfillment-service", "notification-service", "order-service"],
        "context": "Fulfillment workflows (pick → pack → ship → notify) were implemented as Kafka consumers with custom retry logic. A network partition in February 2024 caused 1,200 orders to be stuck in intermediate states because retry state was in-process memory lost during pod restarts.",
        "forces": "Workflow state must survive pod restarts. Long-running workflows (up to 48 hours for backorder). Visibility into workflow state for customer support. Existing Kafka usage must be preserved.",
        "options": ["Temporal.io (managed cloud)", "Apache Airflow", "AWS Step Functions", "Custom saga with persistent compensation log"],
        "chosen_option": "Temporal.io (self-hosted)",
        "rationale": "Temporal's durable execution model means workflow state is persisted automatically. Unlike Airflow, Temporal is designed for latency-sensitive operational workflows not just batch ETL. AWS Step Functions rejected for vendor lock-in.",
        "expected_outcomes": "Zero stuck orders from pod restarts. Workflow state visible to support in real-time. Long-running backorder workflows handled natively.",
        "tags": ["temporal", "workflow", "distributed-systems", "fulfillment"],
        "related_decisions": ["DEC-2022-001", "DEC-2023-008"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-004",
        "title": "Adopt AI-powered fraud detection with online learning",
        "date": "2024-04-15",
        "authors": "ML Team, Security Team",
        "domain": "security",
        "services": ["payment-service", "fraud-detection"],
        "context": "Rule-based fraud detection had an 8.2% false positive rate blocking legitimate transactions, and was missing 12% of actual fraud (fn rate). Fraudsters were adapting faster than rules could be updated (average rule update cycle was 3 weeks).",
        "forces": "False positive rate must be below 2% to avoid customer friction. Real-time decision in under 100ms. Model must adapt to new fraud patterns without full retraining.",
        "options": ["Online gradient boosting (River library)", "Batch ML with weekly retraining", "External fraud API (Sift)", "Improved rule engine"],
        "chosen_option": "Online learning gradient boosting with River, deployed on Kubernetes",
        "rationale": "River's online learning model updates incrementally with each transaction, adapting to new patterns without scheduled retraining. Sift cost was $120k/year with limited model transparency.",
        "expected_outcomes": "False positive rate under 2%. Fraud catch rate above 92%. Model adaptation within hours of new pattern emergence.",
        "tags": ["ml", "fraud", "security", "online-learning"],
        "related_decisions": ["DEC-2022-002"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-005",
        "title": "Adopt CDN edge caching for API responses (Cloudflare Workers)",
        "date": "2024-05-10",
        "authors": "Platform Team, Kenji Watanabe",
        "domain": "platform",
        "services": ["api-gateway", "catalogue-service"],
        "context": "Product catalogue API was handling 80% cache-eligible read requests hitting origin. During a marketing campaign in April 2024, origin received 150k rpm causing p99 latency to spike to 2.3 seconds. CDN caching for API responses was blocked by over-aggressive Cache-Control headers.",
        "forces": "Cache invalidation must be per-product (not full cache flush). Personalised responses must bypass cache. Maximum acceptable staleness is 60 seconds for product data.",
        "options": ["Cloudflare Workers with KV cache", "Cloudflare CDN with cache rules", "AWS CloudFront with Lambda@Edge", "Varnish cache in-cluster"],
        "chosen_option": "Cloudflare Workers with surrogate key invalidation",
        "rationale": "Surrogate keys (Cache-Tag headers) enable per-product invalidation without a full cache purge. Cloudflare Workers allow personalisation bypass logic at the edge. AWS CloudFront Lambda@Edge rejected due to cold-start latency.",
        "expected_outcomes": "Origin request reduction by 80% for catalogue reads. P99 latency under 200ms during campaigns. Sub-5-second per-product cache invalidation.",
        "tags": ["cdn", "caching", "cloudflare", "performance", "api"],
        "related_decisions": ["DEC-2022-004"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-006",
        "title": "Adopt LLM-powered customer support chat with RAG",
        "date": "2024-06-20",
        "authors": "Product Team, ML Team",
        "domain": "ml",
        "services": ["support-service", "knowledge-base"],
        "context": "Customer support was handling 12,000 tickets/week with 60% being answerable from existing documentation. Support team of 40 was at capacity. Average first response time was 8 hours.",
        "forces": "Must not hallucinate policy information. Must escalate confidently to human agent when uncertain. Response quality must be measurable.",
        "options": ["Fine-tuned open-source LLM", "GPT-4 with RAG over knowledge base", "Rule-based chatbot", "Outsource to third-party chat provider"],
        "chosen_option": "GPT-4o with RAG over internal knowledge base using Weaviate",
        "rationale": "RAG grounds responses in verified documentation, reducing hallucination risk. Weaviate already deployed (DEC-2024-001) reduced implementation cost. Fine-tuning rejected due to retraining cost for policy updates.",
        "expected_outcomes": "Deflect 50% of tier-1 tickets. Average first response time under 30 seconds for bot-handled tickets. Human escalation accuracy above 95%.",
        "tags": ["llm", "rag", "support", "ml", "gpt-4"],
        "related_decisions": ["DEC-2024-001"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-007",
        "title": "Adopt DuckDB for embedded analytics in reporting service",
        "date": "2024-07-30",
        "authors": "Data Team",
        "domain": "data",
        "services": ["reporting", "analytics"],
        "context": "Self-serve analytics queries from product managers were running directly against the PostgreSQL read replica (DEC-2023-003), causing 40-minute timeouts for complex cohort analysis. Data team was bottlenecked reviewing and optimising every ad-hoc query.",
        "forces": "Ad-hoc queries must not impact read replica. Analytical query results in under 60 seconds for datasets up to 500GB. Minimal operational overhead.",
        "options": ["ClickHouse (self-hosted)", "DuckDB (embedded in reporting service)", "Snowflake", "BigQuery"],
        "chosen_option": "DuckDB embedded in reporting service against S3 Parquet exports",
        "rationale": "DuckDB's embedded columnar engine requires zero additional infrastructure. Parquet exports from the event stream provide a clean separation between OLTP and analytical workloads. Snowflake and BigQuery costs at our data volume were $35k/year.",
        "expected_outcomes": "Ad-hoc queries complete in under 60 seconds. Zero impact on PostgreSQL read replica. Data team no longer bottlenecked on query reviews.",
        "tags": ["duckdb", "analytics", "data", "olap"],
        "related_decisions": ["DEC-2023-003", "DEC-2023-001"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-008",
        "title": "Adopt Rust for latency-critical payment processing hot path",
        "date": "2024-08-22",
        "authors": "Backend Team, Platform Team",
        "domain": "platform",
        "services": ["payment-service"],
        "context": "Payment authorisation service had P99 latency of 280ms against a required SLA of 150ms. Python GIL prevented true CPU parallelism. Profiling showed 60% of time in cryptographic operations and serialisation, both CPU-bound.",
        "forces": "P99 latency must be under 150ms. Zero GC pauses acceptable. Existing team has Python expertise but only one Rust engineer. Interface must remain gRPC.",
        "options": ["Rust (full rewrite)", "Python with C extension for hot path", "Go rewrite", "JVM (Java/Kotlin)"],
        "chosen_option": "Rust for hot path, Python wrapper preserved for non-critical paths",
        "rationale": "Rust's zero-cost abstractions and lack of GC eliminated latency spikes. gRPC interface via tonic. Python wrapper preserved existing operational tooling. Go considered but rejected due to GC pauses in latency measurements.",
        "expected_outcomes": "P99 latency under 150ms. Zero GC pause events. Throughput increase from 8k to 25k TPS.",
        "tags": ["rust", "performance", "payment", "latency"],
        "related_decisions": ["DEC-2022-005"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-009",
        "title": "Adopt Blue/Green deployment strategy for database migrations",
        "date": "2024-09-10",
        "authors": "Ops Team, Backend Team",
        "domain": "delivery",
        "services": ["all services with PostgreSQL dependencies"],
        "context": "A poorly executed schema migration in August 2024 caused 22 minutes of downtime by adding a NOT NULL column to the orders table without a default value while the old code was still running. Zero-downtime migrations were not standardised.",
        "forces": "Zero downtime migrations required (orders cannot stop). Rollback must be possible within 5 minutes. Team of 8 backend engineers at varying experience levels.",
        "options": ["Expand/contract pattern (manual)", "Blue/green deployment with dual-schema support", "Flyway with expand/contract plugin", "Ghost for online schema changes"],
        "chosen_option": "Expand/contract pattern enforced via migration linting and blue/green Kubernetes deployment",
        "rationale": "Expand/contract pattern (backward-compatible migrations only) is the minimal-tooling approach. Migration linter added to CI to reject dangerous migrations. Blue/green deployment via Kubernetes allows both schema versions to serve simultaneously during transition.",
        "expected_outcomes": "Zero downtime migrations. Rollback capability within 5 minutes. All engineers trained on expand/contract by end of Q4.",
        "tags": ["deployment", "database", "zero-downtime", "migrations"],
        "related_decisions": ["DEC-2022-003", "DEC-2022-007"],
        "status": "active",
    },
    {
        "decision_id": "DEC-2024-010",
        "title": "Adopt Apache Iceberg for data lake table format",
        "date": "2024-10-14",
        "authors": "Data Team, Marcus Webb",
        "domain": "data",
        "services": ["data-lake", "analytics", "ml-platform"],
        "context": "S3 data lake had no ACID guarantees, causing analysts to read partially-written datasets. Table schema evolution required rewriting entire partitions. Concurrent writes from multiple pipelines caused silent data corruption twice in Q3 2024.",
        "forces": "ACID transactions on S3. Schema evolution without full rewrites. Time-travel queries for point-in-time analysis. Compatible with DuckDB (DEC-2024-007) and Spark.",
        "options": ["Apache Iceberg", "Delta Lake", "Apache Hudi", "Continue with raw Parquet + Glue catalog"],
        "chosen_option": "Apache Iceberg with AWS Glue catalog",
        "rationale": "Iceberg's open specification (no Databricks dependency unlike Delta Lake) and strong DuckDB integration aligned with existing stack. AWS Glue catalog provides serverless metadata management. Hudi rejected due to smaller community.",
        "expected_outcomes": "Zero silent data corruption from concurrent writes. Schema evolution without partition rewrites. Point-in-time query capability for ML training reproducibility.",
        "tags": ["iceberg", "data-lake", "data", "s3"],
        "related_decisions": ["DEC-2023-001", "DEC-2024-007"],
        "status": "active",
    },
]


SEED_OUTCOMES: list[dict] = [
    {
        "decision_id": "DEC-2022-001",
        "actual_results": "Kafka adoption was highly successful. Cascading failure rate dropped from 3 per quarter to zero in the 12 months following adoption. P99 event delivery is consistently under 80ms. Consumer groups enabled 4 new analytics pipelines to be added without touching producers. Event replay was used twice to recover from downstream consumer bugs.",
        "regret_score": 1,
        "lessons": "Kafka is operationally heavy for a team our size. Schema registry (Confluent) added later was essential but should have been planned from day 1. Recommend starting with schema registry for any future Kafka adoption.",
        "would_repeat": True,
        "metrics": {"p99_latency_ms": 78, "cascading_failures_per_quarter": 0, "consumer_groups": 12, "messages_per_second_peak": 48000},
        "incidents": "One Kafka broker disk-full incident in month 3, resolved in 40 minutes. Added disk usage alerting as corrective action.",
        "recorded_by": "Priya Nair",
    },
    {
        "decision_id": "DEC-2022-002",
        "actual_results": "JWT with Redis blacklist completely eliminated session-related outages. API gateway scaled horizontally from 3 to 12 instances during peak season without any issues. Token revocation SLA met at 45 seconds average. No auth-related outages in 18 months post-migration.",
        "regret_score": 1,
        "lessons": "Redis cluster needs careful capacity planning for the blacklist TTL window. We over-provisioned by 3x initially. JWT secret rotation procedure was not documented and caused a 6-hour incident when we needed to rotate for a security event. Document key rotation procedures before go-live.",
        "would_repeat": True,
        "metrics": {"auth_outages_in_18mo": 0, "gateway_instances_at_peak": 12, "avg_token_revocation_seconds": 45, "redis_blacklist_memory_mb": 340},
        "incidents": "JWT secret rotation incident (6 hours). Added to runbook. Redis OOM scare (resolved by increasing memory).",
        "recorded_by": "Sarah Chen",
    },
    {
        "decision_id": "DEC-2022-003",
        "actual_results": "PostgreSQL JSONB met all requirements. GIN indexes on JSONB attributes perform on par with MongoDB for our query patterns (tested via shadow reads). Zero ACID issues. Team velocity higher due to single DB technology. SSPL licensing would have been an issue had we chosen MongoDB as they tightened terms in 2023.",
        "regret_score": 1,
        "lessons": "JSONB query complexity for deeply nested documents is high. Defined a rule: max 3 nesting levels for JSONB. Deeper structures should use separate tables. GIN indexes bloat significantly on high-cardinality JSONB writes – monitor index bloat.",
        "would_repeat": True,
        "metrics": {"query_p99_ms": 12, "index_size_gb": 8.4, "product_categories_supported": 340, "transaction_conflicts": 0},
        "incidents": "Index bloat incident at 18-month mark required REINDEX CONCURRENTLY (4-hour maintenance window). Added autovacuum tuning.",
        "recorded_by": "Marcus Webb",
    },
    {
        "decision_id": "DEC-2022-007",
        "actual_results": "Kubernetes migration took 6 months (2x longer than planned). Deployment time reduced from 45 minutes to 4 minutes. Staging/production configuration drift eliminated. However, Kubernetes operational complexity consumed 60% of the ops team's capacity for the first year. Two engineers required full-time Kubernetes specialisation.",
        "regret_score": 2,
        "lessons": "Kubernetes is powerful but carries enormous operational complexity for small teams. Should have invested in a platform engineering team first. Recommend starting with a service mesh before adding Kubernetes for teams under 10 engineers. GitOps (Argo CD) added 3 months in was the missing piece – should have been planned from day 1.",
        "would_repeat": True,
        "metrics": {"deployment_time_minutes": 4, "config_drift_incidents": 0, "migration_duration_months": 6, "ops_capacity_consumed_percent": 60},
        "incidents": "etcd compaction issue month 8 caused 40-minute control plane disruption. Node auto-scaler misconfiguration caused $12k unexpected cloud bill in month 4.",
        "recorded_by": "Sofia Martinez",
    },
    {
        "decision_id": "DEC-2023-001",
        "actual_results": "dbt transformed the data team's workflow. Single source of truth achieved within 4 months. Data tests caught 3 upstream data quality regressions before they reached dashboards. Analyst autonomy increased – engineers no longer bottlenecked for SQL transformations. Board reporting now uses dbt-modelled metrics exclusively.",
        "regret_score": 1,
        "lessons": "dbt documentation (dbt docs generate) should be mandatory from day 1 – we neglected it and lost context when 2 analysts left. dbt Cloud worth reconsidering at current team size as self-hosted CI runs have become a maintenance burden.",
        "would_repeat": True,
        "metrics": {"models_in_production": 180, "data_tests_passing": 420, "regressions_caught_before_dashboard": 3, "analyst_pr_without_eng_review_percent": 85},
        "incidents": "dbt run failure caused 6-hour dashboard outage in month 2 (circular dependency introduced by analyst). Added dbt compile check to CI.",
        "recorded_by": "Marcus Webb",
    },
    {
        "decision_id": "DEC-2023-002",
        "actual_results": "OpenTelemetry migration reduced observability costs from $180k to $31k/year (83% reduction). Unified trace-to-log correlation reduced MTTR from 45 minutes to 12 minutes. However, auto-instrumentation for Python services introduced 8ms latency overhead – had to switch to manual instrumentation for latency-sensitive paths.",
        "regret_score": 1,
        "lessons": "OTel auto-instrumentation has non-trivial overhead for latency-sensitive Python services. Profile before deploying to hot paths. Grafana stack operational complexity is lower than expected. Loki log querying is slower than Elasticsearch for complex queries – acceptable tradeoff for our use case.",
        "would_repeat": True,
        "metrics": {"cost_per_year_before": 180000, "cost_per_year_after": 31000, "mttr_minutes_before": 45, "mttr_minutes_after": 12, "otel_latency_overhead_ms": 8},
        "incidents": "Loki disk full incident month 6 (log retention policy not set). Added retention policy.",
        "recorded_by": "James Liu",
    },
    {
        "decision_id": "DEC-2023-004",
        "actual_results": "Next.js App Router migration achieved LCP of 1.9s (target 2.5s). CLS dropped to 0.04. Organic search traffic increased 28% over 6 months. However, React Server Components learning curve was steeper than anticipated – 2-month productivity dip during migration. Several third-party libraries incompatible with RSC required workarounds.",
        "regret_score": 2,
        "lessons": "RSC mental model shift is significant. Budget at least 2 months for team proficiency. Audit all third-party libraries for RSC compatibility before committing. App Router's aggressive caching defaults caused stale data bugs in 3 features – cache invalidation strategy must be planned upfront.",
        "would_repeat": True,
        "metrics": {"lcp_seconds": 1.9, "cls": 0.04, "organic_search_growth_percent": 28, "migration_duration_months": 4},
        "incidents": "Stale cache caused incorrect pricing shown to users for 2 hours. Added cache revalidation on price update events.",
        "recorded_by": "Kenji Watanabe",
    },
    {
        "decision_id": "DEC-2023-006",
        "actual_results": "Elasticsearch improved search conversion rate from 2.1% to 4.3% within 3 months. Typo tolerance and synonym handling were immediate improvements. Real-time indexing achieved under 15 seconds. However, Elasticsearch operational overhead was significantly underestimated – JVM tuning, shard management, and upgrade complexity consumed 20% of a senior engineer's time.",
        "regret_score": 2,
        "lessons": "Elasticsearch is powerful but operationally expensive. Should have evaluated Typesense more seriously – its simpler operations model may have been sufficient. Shard count planning is critical – we over-sharded initially and had to reindex. Consider managed Elastic Cloud for teams without dedicated search expertise.",
        "would_repeat": True,
        "metrics": {"search_conversion_rate_before": 2.1, "search_conversion_rate_after": 4.3, "indexing_latency_seconds": 14, "jvm_tuning_hours_per_month": 8},
        "incidents": "Split-brain incident month 5 (network partition during ES upgrade). 2-hour search degradation. Added proper quorum configuration.",
        "recorded_by": "Priya Nair",
    },
    {
        "decision_id": "DEC-2023-007",
        "actual_results": "SLO-based alerting reduced weekly alert volume from 850 to 38 – an 96% reduction. On-call burnout eliminated – zero engineer departures attributed to on-call in the following year. MTTR improved to 11 minutes. Error budget policy successfully blocked 2 feature launches that would have exhausted the error budget.",
        "regret_score": 1,
        "lessons": "SLO definition workshop took 3 weeks and required significant stakeholder alignment – budget time for this. Error budget policy creates healthy tension between product and engineering but requires exec sponsorship to be enforced. Multi-burn-rate alerts are the right default – simpler approaches miss slow burns.",
        "would_repeat": True,
        "metrics": {"weekly_alerts_before": 850, "weekly_alerts_after": 38, "mttr_minutes": 11, "engineer_attrition_post_impl": 0},
        "incidents": "None attributed to alerting system post-implementation.",
        "recorded_by": "James Liu",
    },
    {
        "decision_id": "DEC-2023-008",
        "actual_results": "Event sourcing eliminated race conditions completely. Full audit trail satisfied regulatory audit. Replaying events twice for read model rebuilds was straightforward. However, implementation took 4 months vs 6-week estimate due to unexpected complexity in snapshot management and event schema evolution.",
        "regret_score": 3,
        "lessons": "Event sourcing complexity is routinely underestimated. Snapshot management, event versioning (upcasting), and debugging (no mutable state to inspect) are significant ongoing costs. Only adopt for aggregates with genuine auditability requirements. For simpler workflows, consider append-only tables with soft deletes instead.",
        "would_repeat": False,
        "metrics": {"race_conditions_post_impl": 0, "implementation_weeks_actual": 16, "implementation_weeks_estimated": 6, "event_types_in_production": 24},
        "incidents": "Event schema evolution broke downstream consumer in month 7 (missing upcaster). 90-minute order processing degradation.",
        "recorded_by": "Marcus Webb",
    },
    {
        "decision_id": "DEC-2024-001",
        "actual_results": "Weaviate deployment achieved 3.8% recommendation CTR (target 3.5%). Cold-start problem solved for products with descriptions. P99 recommendation latency is 34ms. However, Weaviate upgrades between minor versions broke the schema twice, requiring manual migration scripts.",
        "regret_score": 2,
        "lessons": "Weaviate schema migrations are not automatic across minor versions – pin versions strictly and test upgrades in staging. Vector dimensionality choice (1536 for OpenAI embeddings) is expensive at scale – evaluate quantisation early. Hybrid BM25+vector search requires careful weight tuning; default weights performed poorly.",
        "would_repeat": True,
        "metrics": {"ctr_percent": 3.8, "p99_latency_ms": 34, "vectors_indexed": 2400000, "schema_breaking_upgrades": 2},
        "incidents": "Schema migration failure during Weaviate 1.19 → 1.21 upgrade caused 4-hour recommendation service degradation.",
        "recorded_by": "Ananya Rajan",
    },
    {
        "decision_id": "DEC-2024-002",
        "actual_results": "GraphQL partner API reduced backend change requests from partners by 70%. Partner onboarding time dropped from 8 days to 1.5 days. However, N+1 query problem appeared immediately and required DataLoader implementation adding 3 weeks of unexpected work. Over-fetching reduced by 45% (target 50%).",
        "regret_score": 2,
        "lessons": "Plan for DataLoader (batching) from day 1 – N+1 queries are guaranteed in GraphQL without it. GraphQL schema design requires discipline; our initial schema was over-general and hard to deprecate fields from. Partner adoption of schema introspection was slower than expected – GraphQL tooling not as universal as assumed.",
        "would_repeat": True,
        "metrics": {"backend_change_requests_reduction_percent": 70, "partner_onboarding_days": 1.5, "over_fetch_reduction_percent": 45, "dataloader_implementation_weeks": 3},
        "incidents": "N+1 query spike caused 8-minute partner API degradation. Fixed with DataLoader caching.",
        "recorded_by": "Kenji Watanabe",
    },
    {
        "decision_id": "DEC-2024-004",
        "actual_results": "Online ML fraud detection reduced false positive rate to 1.4% (target 2%) and raised fraud catch rate to 94% (target 92%). Model adapted to a new fraud pattern within 6 hours vs previous 3-week rule update cycle. Revenue recovered from false-positive blocks: estimated $840k in the first year.",
        "regret_score": 1,
        "lessons": "River's online learning model requires careful feature engineering – the initial feature set was insufficient and required 6 weeks of iteration. Model explainability for fraud disputes with customers was harder than expected (black box). Recommend building explainability from day 1 using SHAP values.",
        "would_repeat": True,
        "metrics": {"false_positive_rate_percent": 1.4, "fraud_catch_rate_percent": 94, "pattern_adaptation_hours": 6, "revenue_recovered_year1_usd": 840000},
        "incidents": "Feature drift caused model accuracy degradation in month 4 (holiday season, distribution shift). Added drift detection monitoring.",
        "recorded_by": "ML Team",
    },
    {
        "decision_id": "DEC-2024-006",
        "actual_results": "LLM support chat deflected 47% of tier-1 tickets (target 50%). First response time for bot-handled tickets: 8 seconds. Human escalation accuracy: 93% (just below 95% target). Customer satisfaction for bot interactions: 3.9/5 vs 4.3/5 for human agents. Cost per ticket reduced by 62%.",
        "regret_score": 2,
        "lessons": "RAG quality is highly dependent on knowledge base quality – we had significant gaps in documentation coverage discovered post-launch. Invest in documentation before deploying RAG. Hallucination rate was 2.3% even with RAG; adversarial testing is essential before launch. GPT-4o cost at volume is non-trivial; evaluate smaller models for simple intents.",
        "would_repeat": True,
        "metrics": {"ticket_deflection_percent": 47, "bot_response_seconds": 8, "escalation_accuracy_percent": 93, "csat_bot": 3.9, "cost_per_ticket_reduction_percent": 62},
        "incidents": "Hallucination incident: bot incorrectly quoted return policy causing 34 invalid return approvals. Added output guardrails.",
        "recorded_by": "Product Team",
    },
    {
        "decision_id": "DEC-2024-008",
        "actual_results": "Rust hot path reduced P99 payment latency from 280ms to 89ms (target 150ms – exceeded). Throughput increased from 8k to 31k TPS. Zero GC-related latency spikes. However, the single Rust engineer became a bus factor risk – the service is difficult for the rest of the team to maintain and debug.",
        "regret_score": 3,
        "lessons": "Never let a critical service be maintainable by only one person. Rust skills must be built across at least 3 engineers before adopting for a core service. Rust's compile times significantly slowed CI from 4 minutes to 18 minutes. Hire Rust expertise before deciding, not after. Consider Go if team can't commit to Rust upskilling.",
        "would_repeat": False,
        "metrics": {"p99_latency_ms_before": 280, "p99_latency_ms_after": 89, "tps_before": 8000, "tps_after": 31000, "ci_build_minutes": 18, "rust_engineers": 1},
        "incidents": "Rust engineer on leave caused 3-week delay in a critical security patch. No other engineer could review or deploy safely.",
        "recorded_by": "Backend Team",
    },
]


# ─────────────────────────────────────────────────────────────────────────
async def seed(drop_existing: bool = False) -> None:
    cfg = get_settings()

    # ── Setup DB
    engine = create_async_engine(cfg.database_url, echo=False)
    async with engine.begin() as conn:
        if drop_existing:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore
    mem = get_memory_client()

    # ── Insert decisions
    console.rule("[bold blue]Seeding Architecture Decisions")
    async with async_session() as session:
        for dec_data in track(SEED_DECISIONS, description="Inserting decisions..."):
            existing = await session.get(Decision, dec_data["decision_id"])
            if existing:
                console.print(f"  [yellow]SKIP[/yellow] {dec_data['decision_id']} (already exists)")
                continue

            dec = Decision(**dec_data)
            session.add(dec)
            await session.commit()
            await session.refresh(dec)

            # Retain to Hindsight
            try:
                await mem.retain_decision(dec)
                dec.memory_synced = True
                session.add(dec)
                await session.commit()
                console.print(f"  [green]✓[/green] {dec.decision_id}: {dec.title[:60]}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {dec.decision_id}: Hindsight retain failed: {e}")

    # ── Insert outcomes
    console.rule("[bold blue]Seeding Outcomes")
    async with async_session() as session:
        for out_data in track(SEED_OUTCOMES, description="Inserting outcomes..."):
            dec_id = out_data["decision_id"]
            dec = await session.get(Decision, dec_id)
            if not dec:
                console.print(f"  [red]SKIP[/red] outcome for {dec_id} – decision not found")
                continue

            # Check if outcome already exists
            from sqlmodel import select as sel
            existing_out = await session.exec(
                sel(Outcome).where(Outcome.decision_id == dec_id).limit(1)
            )
            if existing_out.first():
                console.print(f"  [yellow]SKIP[/yellow] outcome for {dec_id} (already exists)")
                continue

            outcome = Outcome(
                decision_id=dec_id,
                actual_results=out_data["actual_results"],
                regret_score=out_data["regret_score"],
                lessons=out_data["lessons"],
                would_repeat=out_data["would_repeat"],
                metrics=out_data.get("metrics"),
                incidents=out_data.get("incidents"),
                recorded_by=out_data.get("recorded_by"),
                recorded_at=datetime.now(timezone.utc),
            )
            session.add(outcome)
            await session.commit()
            await session.refresh(outcome)

            try:
                await mem.retain_outcome(dec, outcome)
                outcome.memory_synced = True
                session.add(outcome)
                await session.commit()
                console.print(f"  [green]✓[/green] Outcome for {dec_id} (regret={out_data['regret_score']})")
            except Exception as e:
                console.print(f"  [red]✗[/red] Outcome for {dec_id}: Hindsight retain failed: {e}")

    console.rule("[bold green]Seed Complete")
    console.print(f"  Decisions inserted: {len(SEED_DECISIONS)}")
    console.print(f"  Outcomes inserted:  {len(SEED_OUTCOMES)}")
    console.print("\n[bold]The memory agent is ready. Run the briefing endpoint to see grounded results.[/bold]")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed ArchMemory with historical decisions")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    args = parser.parse_args()
    asyncio.run(seed(drop_existing=args.reset))
