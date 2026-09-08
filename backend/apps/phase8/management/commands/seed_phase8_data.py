"""
Management command: seed_phase8_data

Seeds Phase 8 database tables from bundled JSON data files:
  - MineLocation   — 107 verified mines from mining_map_phase8.csv
  - GSIReport      — 1,075 GSI exploration reports from GSI_Reports.csv
  - OcbisBlock     — 2,226 coal blocks from OCBIS.html

Data source: Google Drive audit files, captured 2026-09-08.

Usage:
    python manage.py seed_phase8_data
    python manage.py seed_phase8_data --clear    # wipe and re-seed
    python manage.py seed_phase8_data --mines-only
    python manage.py seed_phase8_data --gsi-only
    python manage.py seed_phase8_data --ocbis-only

Safe to run multiple times — idempotent by default (skips if data already present).
Use --clear to force a full re-seed.
"""

import json
import logging
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

MINES_JSON = DATA_DIR / "mines.json"
GSI_JSON = DATA_DIR / "gsi_reports.json"
OCBIS_JSON = DATA_DIR / "ocbis_blocks.json"


class Command(BaseCommand):
    help = (
        "Seed Phase 8 database tables (MineLocation, GSIReport, OcbisBlock) "
        "from bundled audited data files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Delete existing records before seeding (full re-seed).",
        )
        parser.add_argument(
            "--mines-only",
            action="store_true",
            default=False,
            help="Seed only MineLocation data.",
        )
        parser.add_argument(
            "--gsi-only",
            action="store_true",
            default=False,
            help="Seed only GSIReport data.",
        )
        parser.add_argument(
            "--ocbis-only",
            action="store_true",
            default=False,
            help="Seed only OcbisBlock data.",
        )

    def handle(self, *args, **options):
        from apps.phase8.models import MineLocation, GSIReport, OcbisBlock

        do_mines = options["mines_only"] or not (options["gsi_only"] or options["ocbis_only"] or options["mines_only"])
        do_gsi = options["gsi_only"] or not (options["mines_only"] or options["ocbis_only"] or options["gsi_only"])
        do_ocbis = options["ocbis_only"] or not (options["mines_only"] or options["gsi_only"] or options["ocbis_only"])

        # If any --*-only flag was set, re-derive
        if options["mines_only"]:
            do_mines, do_gsi, do_ocbis = True, False, False
        elif options["gsi_only"]:
            do_mines, do_gsi, do_ocbis = False, True, False
        elif options["ocbis_only"]:
            do_mines, do_gsi, do_ocbis = False, False, True
        else:
            do_mines = do_gsi = do_ocbis = True

        clear = options["clear"]

        # ── Mines ──────────────────────────────────────────────────────────────
        if do_mines:
            self._seed_mines(MineLocation, clear)

        # ── GSI Reports ────────────────────────────────────────────────────────
        if do_gsi:
            self._seed_gsi(GSIReport, clear)

        # ── OCBIS Blocks ───────────────────────────────────────────────────────
        if do_ocbis:
            self._seed_ocbis(OcbisBlock, clear)

        self.stdout.write(self.style.SUCCESS("[seed_phase8_data] Done."))

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load_json(self, path: Path) -> list:
        if not path.exists():
            raise CommandError(f"Data file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _seed_mines(self, MineLocation, clear: bool):
        count = MineLocation.objects.count()
        if count > 0 and not clear:
            self.stdout.write(
                self.style.WARNING(
                    f"[seed_phase8_data] MineLocation already has {count} records — skipping. "
                    "Use --clear to force re-seed."
                )
            )
            return

        if clear:
            deleted, _ = MineLocation.objects.all().delete()
            self.stdout.write(f"  Cleared {deleted} existing MineLocation records.")

        data = self._load_json(MINES_JSON)

        with transaction.atomic():
            objs = [
                MineLocation(
                    mine_name=row["mine_name"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    state=row["state"],
                    district=row.get("district", ""),
                    coalfield=row.get("coalfield", ""),
                    subsidiary=row.get("subsidiary", ""),
                    mine_type=row.get("mine_type", ""),
                    production_mt=row.get("production_mt"),
                    year=row.get("year", "2024-25"),
                )
                for row in data
            ]
            MineLocation.objects.bulk_create(objs)

        self.stdout.write(
            self.style.SUCCESS(f"  [OK] Seeded {len(objs)} MineLocation records.")
        )

    def _seed_gsi(self, GSIReport, clear: bool):
        count = GSIReport.objects.count()
        if count > 0 and not clear:
            self.stdout.write(
                self.style.WARNING(
                    f"[seed_phase8_data] GSIReport already has {count} records — skipping. "
                    "Use --clear to force re-seed."
                )
            )
            return

        if clear:
            deleted, _ = GSIReport.objects.all().delete()
            self.stdout.write(f"  Cleared {deleted} existing GSIReport records.")

        data = self._load_json(GSI_JSON)

        with transaction.atomic():
            objs = [
                GSIReport(
                    accession_no=row.get("accession_no", ""),
                    fsp_id=row.get("fsp_id", ""),
                    title=row.get("title", ""),
                    author=row.get("author", ""),
                    state=row.get("state", ""),
                    toposheet_no=row.get("toposheet_no", ""),
                    year_from=row.get("year_from", ""),
                    year_to=row.get("year_to", ""),
                    region=row.get("region", ""),
                    mission=row.get("mission", ""),
                    theme=row.get("theme", ""),
                )
                for row in data
            ]
            GSIReport.objects.bulk_create(objs)

        self.stdout.write(
            self.style.SUCCESS(f"  [OK] Seeded {len(objs)} GSIReport records.")
        )

    def _seed_ocbis(self, OcbisBlock, clear: bool):
        count = OcbisBlock.objects.count()
        if count > 0 and not clear:
            self.stdout.write(
                self.style.WARNING(
                    f"[seed_phase8_data] OcbisBlock already has {count} records — skipping. "
                    "Use --clear to force re-seed."
                )
            )
            return

        if clear:
            deleted, _ = OcbisBlock.objects.all().delete()
            self.stdout.write(f"  Cleared {deleted} existing OcbisBlock records.")

        data = self._load_json(OCBIS_JSON)

        with transaction.atomic():
            objs = [
                OcbisBlock(
                    subsidiary_or_state=row.get("subsidiary_or_state", ""),
                    coalfield=row.get("coalfield", ""),
                    block_name=row.get("block_name", ""),
                    act_type=row.get("act_type", ""),
                    allocated_to=row.get("allocated_to", ""),
                )
                for row in data
            ]
            OcbisBlock.objects.bulk_create(objs)

        self.stdout.write(
            self.style.SUCCESS(f"  [OK] Seeded {len(objs)} OcbisBlock records.")
        )

