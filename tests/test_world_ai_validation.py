"""Source eligibility must fail closed before node_connect generation."""

from mindcrafted.generator.world_ai_validation import source_quality


def test_metadata_without_relations_is_not_eligible_for_node_connect():
    result = source_quality(
        "Introducción al aprendizaje automático\n"
        "Redes neuronales y aplicaciones\n"
        "Método de análisis de datos."
    )

    assert result["status"] == "SOURCE_TOO_WEAK_FOR_NODE_CONNECT"
    assert result["usableNodeRelations"] == 0


def test_explicit_academic_relations_are_counted_as_usable():
    result = source_quality(
        "La capa de entrada recibe los datos sin procesar.\n"
        "Las capas ocultas extraen características y patrones.\n"
        "La capa de salida produce las predicciones finales."
    )

    assert result["status"] == "PASS"
    assert result["relationshipCount"] == 3
    assert result["conceptCount"] >= 3
