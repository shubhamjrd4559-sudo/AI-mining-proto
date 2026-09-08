"""
apps.phase8.models — Phase 8 Database Models

Models:
  MineLocation   — 107 verified mines from mining_map_phase8.csv (seeded at startup)
  GSIReport      — 1,075 GSI exploration report catalogue entries
  OcbisBlock     — Coal block records from OCBIS system
"""
from django.db import models


class MineLocation(models.Model):
    """
    A verified mine location from the audited mining_map_phase8.csv dataset.

    Data source: Google Drive / mining_map_phase8.csv
    Audit date: 2026-09-08
    107 mines, coordinates verified within Indian coal-bearing regions.
    Year: 2024-25 (all records)
    """

    mine_name = models.CharField(
        max_length=256,
        db_index=True,
        help_text="Official mine name as recorded in mining_map_phase8.csv",
    )
    latitude = models.FloatField(
        help_text="Decimal latitude (WGS-84). Verified within Indian bounds (6–38°N).",
    )
    longitude = models.FloatField(
        help_text="Decimal longitude (WGS-84). Verified within Indian bounds (68–98°E).",
    )
    state = models.CharField(
        max_length=128,
        db_index=True,
        help_text="State as recorded in dataset.",
    )
    district = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="District as recorded in dataset.",
    )
    coalfield = models.CharField(
        max_length=256,
        db_index=True,
        blank=True,
        help_text="Coalfield name as recorded in dataset.",
    )
    subsidiary = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="CIL subsidiary (e.g. CCL, BCCL, SECL).",
    )
    mine_type = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        help_text="Mine type as recorded (OC=Open-cast, UG=Underground, Mixed).",
    )
    production_mt = models.FloatField(
        null=True,
        blank=True,
        help_text="Production in Million Tonnes for reporting year.",
    )
    year = models.CharField(
        max_length=16,
        blank=True,
        help_text="Financial year of the data (e.g. 2024-25).",
    )

    # NOTE: Star Rating is NOT available in the audited dataset and is NOT stored here.

    class Meta:
        ordering = ["mine_name"]
        verbose_name = "Mine Location"
        verbose_name_plural = "Mine Locations"
        indexes = [
            models.Index(fields=["subsidiary", "state"]),
            models.Index(fields=["coalfield"]),
        ]

    def __str__(self):
        return f"{self.mine_name} ({self.subsidiary}, {self.state})"


class GSIReport(models.Model):
    """
    A GSI exploration report catalogue entry from GSI_Reports.csv.

    Data source: Google Drive / GSI REPORT / GSI Reports.csv
    1,075 entries, covering coal & lignite exploration across India.
    """

    accession_no = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="GSI accession number.",
    )
    fsp_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Field Season Program ID.",
    )
    title = models.TextField(
        help_text="Report title.",
    )
    author = models.CharField(
        max_length=512,
        blank=True,
        help_text="Author(s) of the report.",
    )
    state = models.CharField(
        max_length=256,
        db_index=True,
        blank=True,
        help_text="State(s) covered by this report.",
    )
    toposheet_no = models.CharField(
        max_length=256,
        blank=True,
        help_text="Survey of India Toposheet number(s).",
    )
    year_from = models.CharField(
        max_length=8,
        blank=True,
        help_text="Start year of field season.",
    )
    year_to = models.CharField(
        max_length=8,
        blank=True,
        help_text="End year of field season.",
    )
    region = models.CharField(
        max_length=16,
        db_index=True,
        blank=True,
        help_text="GSI Regional Office code (ER, WR, SR, NR, CR, NER, etc.).",
    )
    mission = models.CharField(
        max_length=128,
        blank=True,
        help_text="GSI Mission code.",
    )
    theme = models.CharField(
        max_length=256,
        db_index=True,
        blank=True,
        help_text="Thematic area (e.g. Coal and Lignite Exploration).",
    )

    class Meta:
        ordering = ["-year_from", "accession_no"]
        verbose_name = "GSI Report"
        verbose_name_plural = "GSI Reports"
        indexes = [
            models.Index(fields=["state", "theme"]),
            models.Index(fields=["region"]),
        ]

    def __str__(self):
        return f"{self.accession_no}: {self.title[:60]}"


class OcbisBlock(models.Model):
    """
    A coal block record from the OCBIS (Online Coal Block Information System).

    Data source: Google Drive / GSI REPORT / OCBIS.html
    Contains block allocation status as of data capture date.

    IMPORTANT: This contains block-level metadata only.
    No borehole intercept, depth, seam, lithology, or quality data is present
    in this source.
    """

    subsidiary_or_state = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="CIL subsidiary or State associated with the block.",
    )
    coalfield = models.CharField(
        max_length=256,
        db_index=True,
        blank=True,
        help_text="Coalfield name.",
    )
    block_name = models.CharField(
        max_length=256,
        db_index=True,
        help_text="Name of the coal block.",
    )
    act_type = models.CharField(
        max_length=64,
        blank=True,
        help_text="Applicable legislation (e.g. MMDR, CIL).",
    )
    allocated_to = models.CharField(
        max_length=256,
        blank=True,
        help_text="Entity to whom block is allocated, or Unallocated.",
    )

    class Meta:
        ordering = ["coalfield", "block_name"]
        verbose_name = "OCBIS Coal Block"
        verbose_name_plural = "OCBIS Coal Blocks"
        indexes = [
            models.Index(fields=["coalfield", "subsidiary_or_state"]),
        ]

    def __str__(self):
        return f"{self.block_name} ({self.coalfield})"
