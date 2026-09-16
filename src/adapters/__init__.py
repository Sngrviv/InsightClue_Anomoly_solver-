"""
InsightClue Dataset Adapters.
Universal seams for ingesting, transforming, and embedding diverse real-world FinTech & Grievance datasets.
"""

from src.adapters.dataset_adapter import DatasetSchemaMapping, UniversalDatasetAdapter, CFPB_MAPPING

__all__ = ["DatasetSchemaMapping", "UniversalDatasetAdapter", "CFPB_MAPPING"]
