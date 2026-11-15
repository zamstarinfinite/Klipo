import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional
from backend.db import get_connection, init_db


def seed_if_empty(db_path: Optional[str] = None) -> bool:
    """
    Checks if plans table is empty. If empty, seeds default plans,
    subscribers spanning overdue, due soon, and current states,
    plus demo subscriber and recent charges.
    Returns True if seeded, False if already populated.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM plans;")
        plan_count = cursor.fetchone()[0]
        if plan_count > 0:
            return False

        today = date.today()
        now = datetime.now()

        with conn:
            # 1. Seed Plans
            plans = [
                (
                    "demo",
                    "Demo Hackathon · Prueba Real",
                    0.05,
                    "monthly",
                    "Cobro real de 5 centavos para demostración en vivo",
                    "wallet",
                    15,
                    1,
                    now.isoformat(),
                ),
                (
                    "gym",
                    "Gym Fit",
                    350.00,
                    "monthly",
                    "Acceso total a instalaciones y área de pesas",
                    "gym",
                    28,
                    1,
                    now.isoformat(),
                ),
                (
                    "yoga",
                    "Yoga",
                    250.00,
                    "monthly",
                    "Clases ilimitadas de yoga y meditación",
                    "yoga",
                    30,
                    1,
                    now.isoformat(),
                ),
                (
                    "pilates",
                    "Pilates",
                    400.00,
                    "monthly",
                    "Sesiones de reformer y mat",
                    "pilates",
                    5,
                    1,
                    now.isoformat(),
                ),
            ]

            cursor.executemany(
                """
                INSERT OR IGNORE INTO plans (id, name, price, interval, description, icon, charge_day, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                plans,
            )

            # 2. Seed Subscribers
            # Includes 15 business subscribers from data.ts + 1 demo subscriber
            subscribers = [
                # Demo subscriber (due today, ready for instant demo CoDi charge)
                (
                    "demo_sub",
                    "demo",
                    "Invitado Demo",
                    "5512345678",
                    (today - timedelta(days=30)).isoformat(),
                    today.isoformat(),  # Due today -> 'por_vencer'
                    None,
                    "Vence hoy · Demo en vivo",
                    1,
                    now.isoformat(),
                ),
                # Atrasados (Overdue)
                (
                    "roberto",
                    "gym",
                    "Roberto Gómez",
                    "5512348912",
                    (today - timedelta(days=45)).isoformat(),
                    (today - timedelta(days=14)).isoformat(),
                    None,
                    "Venció 28 oct",
                    1,
                    now.isoformat(),
                ),
                (
                    "luis",
                    "gym",
                    "Luis Morales",
                    "5598762231",
                    (today - timedelta(days=40)).isoformat(),
                    (today - timedelta(days=9)).isoformat(),
                    None,
                    "Venció 2 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "ana",
                    "yoga",
                    "Ana Torres",
                    "5587013318",
                    (today - timedelta(days=44)).isoformat(),
                    (today - timedelta(days=12)).isoformat(),
                    None,
                    "Venció 30 oct",
                    1,
                    now.isoformat(),
                ),
                # Por vencer (Due soon)
                (
                    "mariana",
                    "gym",
                    "Mariana Ortiz",
                    "5523454410",
                    (today - timedelta(days=28)).isoformat(),
                    (today + timedelta(days=2)).isoformat(),
                    None,
                    "Vence 30 nov",
                    1,
                    now.isoformat(),
                ),
                # Al corriente (Current)
                (
                    "carlos",
                    "gym",
                    "Carlos Mendoza",
                    "5534561234",
                    (today - timedelta(days=40)).isoformat(),
                    (today + timedelta(days=20)).isoformat(),
                    (today - timedelta(days=10)).isoformat(),
                    "Pagó 1 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "sofia",
                    "gym",
                    "Sofía Castro",
                    "5545677721",
                    (today - timedelta(days=38)).isoformat(),
                    (today + timedelta(days=22)).isoformat(),
                    (today - timedelta(days=8)).isoformat(),
                    "Pagó 3 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "jorge",
                    "gym",
                    "Jorge Ramírez",
                    "5556783390",
                    (today - timedelta(days=37)).isoformat(),
                    (today + timedelta(days=23)).isoformat(),
                    (today - timedelta(days=7)).isoformat(),
                    "Pagó 4 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "fernanda",
                    "gym",
                    "Fernanda López",
                    "5567891045",
                    (today - timedelta(days=36)).isoformat(),
                    (today + timedelta(days=24)).isoformat(),
                    (today - timedelta(days=6)).isoformat(),
                    "Pagó 5 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "diego",
                    "gym",
                    "Diego Herrera",
                    "5578902276",
                    (today - timedelta(days=35)).isoformat(),
                    (today + timedelta(days=25)).isoformat(),
                    (today - timedelta(days=5)).isoformat(),
                    "Pagó 6 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "lucia",
                    "yoga",
                    "Lucía Vega",
                    "5590124467",
                    (today - timedelta(days=39)).isoformat(),
                    (today + timedelta(days=21)).isoformat(),
                    (today - timedelta(days=9)).isoformat(),
                    "Pagó 2 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "paula",
                    "yoga",
                    "Paula Núñez",
                    "5501235589",
                    (today - timedelta(days=38)).isoformat(),
                    (today + timedelta(days=22)).isoformat(),
                    (today - timedelta(days=8)).isoformat(),
                    "Pagó 3 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "elena",
                    "yoga",
                    "Elena Cruz",
                    "5512346602",
                    (today - timedelta(days=36)).isoformat(),
                    (today + timedelta(days=24)).isoformat(),
                    (today - timedelta(days=6)).isoformat(),
                    "Pagó 5 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "daniela",
                    "yoga",
                    "Daniela Soto",
                    "5523457734",
                    (today - timedelta(days=34)).isoformat(),
                    (today + timedelta(days=26)).isoformat(),
                    (today - timedelta(days=4)).isoformat(),
                    "Pagó 7 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "valeria",
                    "pilates",
                    "Valeria Rivas",
                    "5534568815",
                    (today - timedelta(days=36)).isoformat(),
                    (today + timedelta(days=24)).isoformat(),
                    (today - timedelta(days=6)).isoformat(),
                    "Pagó 5 nov",
                    1,
                    now.isoformat(),
                ),
                (
                    "camila",
                    "pilates",
                    "Camila Reyes",
                    "5545679927",
                    (today - timedelta(days=36)).isoformat(),
                    (today + timedelta(days=24)).isoformat(),
                    (today - timedelta(days=6)).isoformat(),
                    "Pagó 5 nov",
                    1,
                    now.isoformat(),
                ),
            ]

            cursor.executemany(
                """
                INSERT OR IGNORE INTO subscribers (id, plan_id, name, phone, start_date, next_due_date, last_paid_at, note, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                subscribers,
            )

            # 3. Seed Charges matching seedPayments in data.ts
            charges = [
                (
                    "p4",
                    "carlos",
                    "gym",
                    350.00,
                    "Mensualidad Gym Fit",
                    "codi",
                    "paid",
                    (now - timedelta(hours=2)).isoformat(),
                    (now - timedelta(hours=2)).isoformat(),
                ),
                (
                    "p3",
                    "mariana",
                    "gym",
                    350.00,
                    "Mensualidad Gym Fit",
                    "codi",
                    "pending",
                    (now - timedelta(days=1)).isoformat(),
                    None,
                ),
                (
                    "p2",
                    "roberto",
                    "gym",
                    350.00,
                    "Mensualidad Gym Fit",
                    "codi",
                    "expired",
                    (now - timedelta(days=15)).isoformat(),
                    None,
                ),
                (
                    "p1",
                    "valeria",
                    "pilates",
                    400.00,
                    "Mensualidad Pilates",
                    "codi",
                    "failed",
                    (now - timedelta(days=16)).isoformat(),
                    None,
                ),
            ]

            cursor.executemany(
                """
                INSERT OR IGNORE INTO charges (id, subscriber_id, plan_id, amount, concept, method, status, created_at, paid_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                charges,
            )

        return True
    except (sqlite3.IntegrityError, sqlite3.OperationalError):
        return False
    finally:
        conn.close()
