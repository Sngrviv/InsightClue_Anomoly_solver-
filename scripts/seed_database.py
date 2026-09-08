"""
Synthetic FinTech Data Generator & Anomaly Seeder for InsightClue.
Generates 90 days of realistic daily spend metrics, gateway health logs,
and customer dispute tickets with 768-dim pgvector embeddings.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
import os
import random
import sys
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from src.database.base import Base
from src.database.session import AsyncSessionFactory, async_engine
from src.models import (
    DailySpendMetric,
    DisputeSupportTicket,
    PaymentGatewayLog,
)
from src.services.embedding_service import generate_embeddings_batch

# Set random seed for deterministic simulation
random.seed(42)

# Simulation Parameters
START_DATE = date.today() - timedelta(days=90)
REGIONS = ["West", "South", "North", "East"]
PRODUCTS = [
    "UPI Instant Pay",
    "Corporate Credit Card",
    "Merchant POS Checkout",
    "Cross-Border Remittance",
    "Personal Line of Credit",
]
CUSTOMER_TIERS = ["Retail", "Priority", "Enterprise"]
MERCHANT_CATEGORIES = [
    "E-commerce",
    "SaaS & Cloud Services",
    "Travel & Hospitality",
    "Utilities & Telecom",
]
PARTNER_BANKS = ["HDFC Gateway Switch", "ICICI Core Switch", "Axis Bank Switch", "SBI Payment Hub"]

# Base Product Metric Profiles
PRODUCT_PROFILES = {
    "UPI Instant Pay": {
        "base_daily_txns": 8000,
        "avg_ticket": 850.0,
        "success_rate": 99.2,
        "latency_ms": 160.0,
        "chargeback_rate": 0.04,
        "fraud_score": 3.5,
    },
    "Corporate Credit Card": {
        "base_daily_txns": 1200,
        "avg_ticket": 38000.0,
        "success_rate": 98.8,
        "latency_ms": 310.0,
        "chargeback_rate": 0.18,
        "fraud_score": 8.0,
    },
    "Merchant POS Checkout": {
        "base_daily_txns": 3500,
        "avg_ticket": 2400.0,
        "success_rate": 98.4,
        "latency_ms": 240.0,
        "chargeback_rate": 0.12,
        "fraud_score": 5.5,
    },
    "Cross-Border Remittance": {
        "base_daily_txns": 450,
        "avg_ticket": 65000.0,
        "success_rate": 97.6,
        "latency_ms": 780.0,
        "chargeback_rate": 0.35,
        "fraud_score": 12.0,
    },
    "Personal Line of Credit": {
        "base_daily_txns": 280,
        "avg_ticket": 42000.0,
        "success_rate": 99.0,
        "latency_ms": 380.0,
        "chargeback_rate": 0.08,
        "fraud_score": 6.0,
    },
}


async def recreate_tables():
    """Drops and recreates all database tables with pgvector extension."""
    print("🛠️ Recreating Database Schema and pgvector extension...")
    async with async_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully.")


def generate_spend_and_gateway_data():
    """Generates 90 days of normal metrics and injects planted anomalies."""
    print("📊 Generating 90 days of FinTech metrics & gateway logs...")
    spend_records = []
    gateway_records = []
    ticket_payloads = []

    for day_idx in range(91):
        current_date = START_DATE + timedelta(days=day_idx)
        # Weekly seasonality: weekends have slightly higher retail, lower corporate
        is_weekend = current_date.weekday() >= 5
        weekend_factor = 0.7 if is_weekend else 1.05

        for region in REGIONS:
            for product in PRODUCTS:
                profile = PRODUCT_PROFILES[product]

                for tier in CUSTOMER_TIERS:
                    for category in MERCHANT_CATEGORIES:
                        # Base calculations with natural Gaussian variance
                        base_txns = profile["base_daily_txns"] / (len(CUSTOMER_TIERS) * len(MERCHANT_CATEGORIES))
                        txns = int(base_txns * weekend_factor * random.uniform(0.92, 1.08))
                        ticket_size = profile["avg_ticket"] * random.uniform(0.95, 1.05)
                        spend = txns * ticket_size

                        success_rate = min(100.0, profile["success_rate"] + random.gauss(0, 0.3))
                        latency = max(50.0, profile["latency_ms"] + random.gauss(0, 15.0))
                        chargeback = max(0.01, profile["chargeback_rate"] + random.gauss(0, 0.03))
                        fraud_score = max(1.0, profile["fraud_score"] + random.gauss(0, 1.0))

                        # =========================================================================
                        # PLANTED ANOMALY 1: Gateway 3DS Failure (South Region, Corporate Card)
                        # Day 65 to Day 72
                        # =========================================================================
                        if (
                            65 <= day_idx <= 72
                            and region == "South"
                            and product == "Corporate Credit Card"
                        ):
                            # Dramatic degradation
                            success_rate = random.uniform(79.0, 81.8)  # Plunge from 98.8% to ~80%
                            spend = spend * 0.68  # 32% drop in spend
                            latency = random.uniform(1650.0, 1950.0)  # Severe timeout latency
                            chargeback = chargeback * 2.5
                            fraud_score = fraud_score * 1.4

                        # =========================================================================
                        # PLANTED ANOMALY 2: FX Remittance Dispute Spike (West Region)
                        # Day 80 to Day 84
                        # =========================================================================
                        if (
                            80 <= day_idx <= 84
                            and region == "West"
                            and product == "Cross-Border Remittance"
                        ):
                            chargeback = random.uniform(7.8, 9.5)  # Spike from 0.35% to ~8.5%
                            fraud_score = random.uniform(58.0, 68.0)  # Compliance flags
                            spend = spend * 0.55

                        spend_records.append(
                            DailySpendMetric(
                                metric_date=current_date,
                                region=region,
                                product_name=product,
                                customer_tier=tier,
                                merchant_category=category,
                                daily_spend_amount=round(spend, 2),
                                transaction_count=txns,
                                avg_ticket_size=round(ticket_size, 2),
                                success_rate_pct=round(success_rate, 2),
                                avg_latency_ms=round(latency, 2),
                                chargeback_rate_pct=round(chargeback, 3),
                                avg_fraud_risk_score=round(fraud_score, 2),
                            )
                        )

            # Gateway logs per partner bank
            for bank in PARTNER_BANKS:
                for product in PRODUCTS:
                    gw_reqs = random.randint(1500, 5000)
                    failed = int(gw_reqs * (1.0 - (PRODUCT_PROFILES[product]["success_rate"] / 100.0)))
                    timeouts = int(failed * random.uniform(0.1, 0.3))
                    errors = failed - timeouts
                    resp_time = PRODUCT_PROFILES[product]["latency_ms"] + random.gauss(0, 20)
                    gw_status = "OPERATIONAL"

                    # Plant Anomaly 1 Gateway Evidence: HDFC Gateway 3DS in South
                    if (
                        65 <= day_idx <= 72
                        and region == "South"
                        and product == "Corporate Credit Card"
                        and bank == "HDFC Gateway Switch"
                    ):
                        failed = int(gw_reqs * random.uniform(0.19, 0.23))
                        timeouts = int(failed * 0.88)  # 88% of failures are HTTP 504 Timeouts
                        errors = failed - timeouts
                        resp_time = random.uniform(1700, 2100)
                        gw_status = "DEGRADED"

                    gateway_records.append(
                        PaymentGatewayLog(
                            log_date=current_date,
                            region=region,
                            partner_bank=bank,
                            product_name=product,
                            gateway_channel="3DS_OTP" if "Card" in product else "DIRECT_API",
                            total_requests=gw_reqs,
                            successful_requests=gw_reqs - failed,
                            failed_requests=failed,
                            timeout_504_count=timeouts,
                            server_error_500_count=errors,
                            avg_response_time_ms=round(resp_time, 2),
                            gateway_status=gw_status,
                        )
                    )

        # Generate Support & Dispute Tickets for the Day
        # Normal baseline tickets
        num_normal_tickets = random.randint(3, 7)
        for _ in range(num_normal_tickets):
            reg = random.choice(REGIONS)
            prod = random.choice(PRODUCTS)
            tier = random.choice(CUSTOMER_TIERS)
            cat = random.choice(["MERCHANT_CHARGEBACK", "ACCOUNT_HOLD", "GENERAL_QUERY"])
            ticket_payloads.append(
                {
                    "created_at": datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(8, 20)),
                    "region": reg,
                    "product_name": prod,
                    "customer_tier": tier,
                    "customer_id": f"CUST-{random.randint(10000, 99999)}",
                    "issue_category": cat,
                    "priority": "NORMAL",
                    "dispute_amount": round(random.uniform(500, 15000), 2),
                    "sentiment_score": round(random.uniform(-0.3, 0.4), 2),
                    "subject": f"Routine inquiry regarding {prod} transaction",
                    "message": f"Customer inquiring about transaction settlement timeline for {prod} in {reg} branch.",
                }
            )

        # Anomaly 1 Support Ticket Wave (Days 65-72 in South, Corporate Cards)
        if 65 <= day_idx <= 72:
            num_incident_tickets = random.randint(15, 25)
            for _ in range(num_incident_tickets):
                dispute_amt = round(random.uniform(75000, 550000), 2)
                ticket_payloads.append(
                    {
                        "created_at": datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(9, 21), minutes=random.randint(0, 59)),
                        "region": "South",
                        "product_name": "Corporate Credit Card",
                        "customer_tier": random.choice(["Priority", "Enterprise"]),
                        "customer_id": f"CORP-{random.randint(2000, 9999)}",
                        "issue_category": random.choice(["3DS_OTP_FAILURE", "DOUBLE_DEBIT"]),
                        "priority": "CRITICAL",
                        "dispute_amount": dispute_amt,
                        "sentiment_score": round(random.uniform(-0.95, -0.75), 2),
                        "subject": "CRITICAL: Corporate Card 3DS OTP timeout on supplier payment",
                        "message": (
                            f"Urgent escalation: Our enterprise payment of INR {dispute_amt:,.2f} timed out "
                            "at the 3DS verification page on HDFC gateway switch. The OTP never arrived on phone/email, "
                            "the session threw HTTP 504 Gateway Timeout, and our corporate vendor subscription has been suspended! "
                            "Please investigate this gateway outage immediately."
                        ),
                    }
                )

        # Anomaly 2 Support Ticket Wave (Days 80-84 in West, Remittance)
        if 80 <= day_idx <= 84:
            num_fx_tickets = random.randint(10, 18)
            for _ in range(num_fx_tickets):
                dispute_amt = round(random.uniform(150000, 950000), 2)
                ticket_payloads.append(
                    {
                        "created_at": datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(10, 18)),
                        "region": "West",
                        "product_name": "Cross-Border Remittance",
                        "customer_tier": random.choice(["Priority", "Enterprise"]),
                        "customer_id": f"CORP-{random.randint(5000, 9999)}",
                        "issue_category": "FX_RATE_DISPUTE",
                        "priority": "HIGH",
                        "dispute_amount": dispute_amt,
                        "sentiment_score": round(random.uniform(-0.88, -0.65), 2),
                        "subject": "Dispute on FX spread and compliance hold for foreign remittance",
                        "message": (
                            f"Our international remittance of INR {dispute_amt:,.2f} to international supplier was unexpectedly "
                            "placed on automated compliance hold due to exchange rate discrepancy. We request immediate clearance "
                            "and fee waiver."
                        ),
                    }
                )

    return spend_records, gateway_records, ticket_payloads


async def seed_all():
    print("=" * 65)
    print("🚀 Starting InsightClue FinTech Synthetic Seeding Engine")
    print("=" * 65)

    await recreate_tables()

    spend_records, gateway_records, ticket_payloads = generate_spend_and_gateway_data()

    print(f"📦 Prepared {len(spend_records):,} DailySpendMetric records.")
    print(f"📦 Prepared {len(gateway_records):,} PaymentGatewayLog records.")
    print(f"📦 Prepared {len(ticket_payloads):,} DisputeSupportTicket records.")

    # 1. Insert Daily Spend Metrics in Batches
    print("\n⏳ Saving DailySpendMetric records to PostgreSQL...")
    async with AsyncSessionFactory() as session:
        batch_size = 1000
        for i in range(0, len(spend_records), batch_size):
            session.add_all(spend_records[i : i + batch_size])
            await session.commit()
            print(f"   - Inserted {min(i + batch_size, len(spend_records)):,}/{len(spend_records):,} spend metrics.")

    # 2. Insert Payment Gateway Logs in Batches
    print("\n⏳ Saving PaymentGatewayLog records to PostgreSQL...")
    async with AsyncSessionFactory() as session:
        batch_size = 1000
        for i in range(0, len(gateway_records), batch_size):
            session.add_all(gateway_records[i : i + batch_size])
            await session.commit()
            print(f"   - Inserted {min(i + batch_size, len(gateway_records)):,}/{len(gateway_records):,} gateway logs.")

    # 3. Generate Vector Embeddings for Support Tickets and Save
    print("\n⏳ Generating 768-dim Vector Embeddings for Support Tickets...")
    ticket_objects = []
    batch_embed_size = 64

    for i in range(0, len(ticket_payloads), batch_embed_size):
        batch = ticket_payloads[i : i + batch_embed_size]
        texts = [f"Subject: {item['subject']} | Category: {item['issue_category']} | Message: {item['message']}" for item in batch]
        embeddings = generate_embeddings_batch(texts)

        for payload, emb in zip(batch, embeddings):
            ticket_objects.append(
                DisputeSupportTicket(
                    ticket_created_at=payload["created_at"],
                    region=payload["region"],
                    product_name=payload["product_name"],
                    customer_tier=payload["customer_tier"],
                    customer_id=payload["customer_id"],
                    issue_category=payload["issue_category"],
                    priority=payload["priority"],
                    dispute_amount=payload["dispute_amount"],
                    sentiment_score=payload["sentiment_score"],
                    subject=payload["subject"],
                    message=payload["message"],
                    embedding=emb,
                )
            )
        print(f"   - Generated embeddings for {len(ticket_objects):,}/{len(ticket_payloads):,} tickets...")

    print("\n⏳ Saving DisputeSupportTicket records with pgvector embeddings...")
    async with AsyncSessionFactory() as session:
        for i in range(0, len(ticket_objects), 500):
            session.add_all(ticket_objects[i : i + 500])
            await session.commit()

    # 4. Verify Counts and Semantic Search
    print("\n" + "=" * 65)
    print("🔍 Verifying Seeded Database & Testing Semantic RAG Query...")
    print("=" * 65)

    async with AsyncSessionFactory() as session:
        spend_count = (await session.execute(text("SELECT count(*) FROM daily_spend_metrics;"))).scalar()
        gw_count = (await session.execute(text("SELECT count(*) FROM payment_gateway_logs;"))).scalar()
        ticket_count = (await session.execute(text("SELECT count(*) FROM dispute_support_tickets;"))).scalar()

        print(f"✅ Total Daily Spend Metrics in DB: {spend_count:,}")
        print(f"✅ Total Gateway Health Logs in DB: {gw_count:,}")
        print(f"✅ Total Dispute Tickets (with pgvector) in DB: {ticket_count:,}")

        # Test Semantic Search on Support Tickets
        test_query = "Why are corporate card OTPs failing with 504 gateway timeout?"
        query_emb = generate_embeddings_batch([test_query])[0]

        sql_semantic_search = text(
            """
            SELECT id, region, product_name, customer_tier, subject, 
                   1 - (embedding <=> :query_vector) AS cosine_similarity
            FROM dispute_support_tickets
            ORDER BY embedding <=> :query_vector ASC
            LIMIT 3;
            """
        )
        res = await session.execute(sql_semantic_search, {"query_vector": str(query_emb)})
        top_matches = res.fetchall()

        print(f"\n🎯 Semantic Search Test for Query: '{test_query}'")
        for match in top_matches:
            print(f"   - [Sim: {match[5]:.4f}] {match[1]} | {match[2]} ({match[3]} Tier): {match[4]}")

    await async_engine.dispose()
    print("\n🎉 PHASE 2 SEEDING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(seed_all())
