"""Tests for extraction validation — entity/relationship schema enforcement."""
from __future__ import annotations

from ingestion.extractor import EntityExtractor


class TestEntityValidation:
    def test_clamp_stance(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "stance": 2.0, "description": "test"}
        )
        assert result["stance"] == 1.0

    def test_clamp_negative_stance(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "stance": -5.0, "description": "test"}
        )
        assert result["stance"] == -1.0

    def test_default_missing_stance(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "description": "test"}
        )
        assert result["stance"] == 0.0

    def test_valid_stance_unchanged(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "stance": 0.5, "description": "test"}
        )
        assert result["stance"] == 0.5

    def test_invalid_object_type_defaults(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "object_type": "Invalid", "description": "test"}
        )
        assert result["object_type"] == "Concept"

    def test_valid_object_types_kept(self):
        for ot in ("Actor", "Artifact", "Event", "Environment", "Concept"):
            result = EntityExtractor._validate_and_fix_entity(
                {"name": "A", "object_type": ot, "description": "test"}
            )
            assert result["object_type"] == ot

    def test_missing_name_returns_none(self):
        result = EntityExtractor._validate_and_fix_entity({"stance": 0.5})
        assert result is None

    def test_empty_name_returns_none(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "", "description": "test"}
        )
        assert result is None

    def test_missing_description_defaults_to_name(self):
        result = EntityExtractor._validate_and_fix_entity({"name": "Test Entity"})
        assert result["description"] == "Test Entity"

    def test_empty_description_defaults_to_name(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "Test Entity", "description": ""}
        )
        assert result["description"] == "Test Entity"

    def test_clamp_volatility(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "volatility": 1.5, "description": "t"}
        )
        assert result["volatility"] == 1.0

    def test_clamp_volatility_negative(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "volatility": -0.1, "description": "t"}
        )
        assert result["volatility"] == 0.0

    def test_clamp_influence(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "influence_score": -0.5, "description": "t"}
        )
        assert result["influence_score"] == 0.0

    def test_clamp_influence_over_one(self):
        result = EntityExtractor._validate_and_fix_entity(
            {"name": "A", "influence_score": 2.5, "description": "t"}
        )
        assert result["influence_score"] == 1.0

    def test_valid_numeric_fields_unchanged(self):
        result = EntityExtractor._validate_and_fix_entity(
            {
                "name": "A",
                "description": "test",
                "stance": 0.3,
                "volatility": 0.4,
                "influence_score": 0.8,
            }
        )
        assert result["stance"] == 0.3
        assert result["volatility"] == 0.4
        assert result["influence_score"] == 0.8


class TestRelationshipValidation:
    def test_valid_relationship(self):
        names = {"미국", "한국"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "미국", "target": "한국", "link_type": "INFLUENCES", "weight": 0.8},
            names,
        )
        assert result is not None
        assert result["weight"] == 0.8

    def test_invalid_source_returns_none(self):
        names = {"미국"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "일본", "target": "미국", "link_type": "INFLUENCES"},
            names,
        )
        assert result is None

    def test_invalid_target_returns_none(self):
        names = {"미국"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "미국", "target": "일본", "link_type": "INFLUENCES"},
            names,
        )
        assert result is None

    def test_case_insensitive_match(self):
        names = {"Samsung"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "samsung", "target": "Samsung", "link_type": "COMPETES_WITH"},
            names,
        )
        assert result is not None
        assert result["source"] == "Samsung"

    def test_fuzzy_match_source(self):
        names = {"삼성전자"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "삼성", "target": "삼성전자", "link_type": "BELONGS_TO"},
            names,
        )
        # "삼성" should fuzzy match to "삼성전자"
        assert result is not None

    def test_fuzzy_match_target(self):
        names = {"삼성전자"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "삼성전자", "target": "삼성", "link_type": "BELONGS_TO"},
            names,
        )
        assert result is not None

    def test_invalid_link_type_defaults(self):
        names = {"A", "B"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "A", "target": "B", "link_type": "FAKE_TYPE"},
            names,
        )
        assert result["link_type"] == "INFLUENCES"

    def test_valid_link_types_kept(self):
        names = {"A", "B"}
        for lt in (
            "INFLUENCES",
            "IMPACTS",
            "BELONGS_TO",
            "CONTAINS",
            "COMPETES_WITH",
            "ALLIED_WITH",
            "DEPENDS_ON",
            "REACTS_TO",
            "SUPPLIES",
            "REGULATES",
            "OPPOSES",
            "LEADS_TO",
        ):
            result = EntityExtractor._validate_and_fix_relationship(
                {"source": "A", "target": "B", "link_type": lt},
                names,
            )
            assert result["link_type"] == lt

    def test_clamp_weight(self):
        names = {"A", "B"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "A", "target": "B", "link_type": "IMPACTS", "weight": 5.0},
            names,
        )
        assert result["weight"] == 1.0

    def test_clamp_weight_negative(self):
        names = {"A", "B"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "A", "target": "B", "link_type": "IMPACTS", "weight": -1.0},
            names,
        )
        assert result["weight"] == 0.0

    def test_missing_weight_defaults(self):
        names = {"A", "B"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "A", "target": "B", "link_type": "IMPACTS"},
            names,
        )
        assert result["weight"] == 0.5

    def test_both_source_target_invalid_returns_none(self):
        names = {"X", "Y"}
        result = EntityExtractor._validate_and_fix_relationship(
            {"source": "에러", "target": "없음", "link_type": "INFLUENCES"},
            names,
        )
        assert result is None
